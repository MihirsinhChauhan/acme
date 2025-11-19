"""CSV upload endpoint with validation and task enqueueing."""
from __future__ import annotations

import logging
import shutil
from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.services.csv_validator import CSVValidator
from app.services.import_service import ImportService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/upload", tags=["upload"])


class UploadResponse(BaseModel):
    """Response payload after successful CSV upload."""

    job_id: str
    sse_url: str
    message: str


@router.post(
    "",
    response_model=UploadResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Upload CSV file for import",
    description=(
        "Accepts a CSV file, validates structure and content, creates an import job, "
        "and enqueues a background task for processing. Returns immediately with job_id "
        "and SSE URL for progress tracking."
    ),
)
async def upload_csv(
    file: UploadFile = File(..., description="CSV file to import"),
    session: Session = Depends(get_session),
) -> UploadResponse:
    """
    Handle CSV file upload and initiate async import processing.

    Steps:
    1. Validate file type and size
    2. Save to temporary directory
    3. Run pre-import validation (headers, schema, sample rows)
    4. Create import job record in database
    5. Enqueue Celery task for background processing
    6. Return job_id and SSE URL for progress tracking

    Args:
        file: Uploaded CSV file
        session: Database session (injected)

    Returns:
        UploadResponse with job_id and sse_url

    Raises:
        HTTPException: 400 if validation fails, 413 if file too large, 500 on unexpected errors
    """
    # Ensure upload directory exists
    upload_dir = Path(settings.upload_tmp_dir)
    upload_dir.mkdir(parents=True, exist_ok=True)

    # Generate unique job ID and file path
    job_id = uuid4()
    temp_file_path = upload_dir / f"{job_id}.csv"

    try:
        # Step 1: Validate file metadata
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Filename is required",
            )

        if not file.filename.lower().endswith(".csv"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid file type. Expected .csv, got {file.filename}",
            )

        # Step 2: Check file size (read in chunks to avoid loading entire file into memory)
        file_size_mb = 0
        if file.size:
            file_size_mb = file.size / (1024 * 1024)
        else:
            # If size not provided by client, we'll check as we save
            pass

        if file_size_mb > settings.max_upload_size_mb:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({file_size_mb:.2f} MB) exceeds maximum allowed size ({settings.max_upload_size_mb} MB)",
            )

        # Step 3: Save uploaded file to temp directory
        logger.info(f"Saving uploaded file to {temp_file_path}")
        with open(temp_file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Double-check file size after saving (in case client didn't provide size)
        actual_size_mb = temp_file_path.stat().st_size / (1024 * 1024)
        if actual_size_mb > settings.max_upload_size_mb:
            temp_file_path.unlink()  # Clean up
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"File size ({actual_size_mb:.2f} MB) exceeds maximum allowed size ({settings.max_upload_size_mb} MB)",
            )

        logger.info(f"File saved successfully: {temp_file_path} ({actual_size_mb:.2f} MB)")

        # Step 4: Run CSV validation (structure, headers, sample rows)
        logger.info(f"Validating CSV file: {temp_file_path}")
        validation_result = CSVValidator.validate_file(temp_file_path)

        if not validation_result.is_valid:
            # Clean up temp file on validation failure
            temp_file_path.unlink()
            logger.warning(f"CSV validation failed: {validation_result.errors}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "message": "CSV validation failed",
                    "errors": validation_result.errors,
                },
            )

        # Log warnings if any (e.g., unknown headers)
        if validation_result.errors:
            logger.info(f"CSV validation warnings: {validation_result.errors}")

        # Step 5: Create import job record in database
        logger.info(f"Creating import job for file: {file.filename}")
        import_service = ImportService(session)
        job_response = import_service.create_import_job(
            filename=file.filename,
            total_rows=validation_result.total_rows,
        )

        logger.info(f"Import job created: {job_response.id}")

        # Step 6: Enqueue Celery task for background processing
        logger.info(f"Enqueueing import task for job_id: {job_response.id}")
        task_id = import_service.enqueue_import_task(
            job_id=job_response.id,
            file_path=str(temp_file_path),
        )

        logger.info(
            f"Task enqueued successfully - job_id: {job_response.id}, task_id: {task_id}"
        )

        # Step 7: Return response with job_id and SSE URL
        sse_url = f"{settings.api_prefix}/progress/{job_response.id}"
        return UploadResponse(
            job_id=str(job_response.id),
            sse_url=sse_url,
            message=f"CSV upload accepted. Processing {validation_result.total_rows} rows in background.",
        )

    except HTTPException:
        # Re-raise FastAPI HTTP exceptions
        raise

    except FileNotFoundError as e:
        # This shouldn't happen, but handle gracefully
        logger.error(f"File not found after upload: {e}")
        if temp_file_path.exists():
            temp_file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal error: file not found after upload",
        )

    except Exception as e:
        # Clean up temp file on any unexpected error
        logger.exception(f"Unexpected error during CSV upload: {e}")
        if temp_file_path.exists():
            temp_file_path.unlink()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to process upload: {str(e)}",
        )

    finally:
        # Ensure file handle is closed
        if file.file:
            file.file.close()

