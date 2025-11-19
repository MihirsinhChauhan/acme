"""Celery tasks for CSV import processing.

This module implements the background worker task for processing CSV imports
with batch upserts, progress tracking, and proper ACK/NACK handling.
"""
from __future__ import annotations

import csv
import logging
import time
from pathlib import Path
from typing import Any, Sequence
from uuid import UUID

from redis import Redis
from celery.exceptions import Retry

from app.core.config import get_settings
from app.core.db import session_scope
from app.models.import_job import ImportStatus
from app.schemas.product import ProductCreate
from app.services.import_service import ImportRepository
from app.services.product_repository import ProductRepository
from app.tasks.celery_app import celery_app

# Configure logging
logger = logging.getLogger(__name__)

# Constants
BATCH_SIZE = 10_000  # Process 10k rows per batch
PROGRESS_UPDATE_INTERVAL = 2.0  # Update progress every 2 seconds


class ProgressTracker:
    """Helper class to track and publish import progress to Redis."""

    def __init__(self, redis_client: Redis, job_id: str, total_rows: int):
        """Initialize progress tracker.
        
        Args:
            redis_client: Synchronous Redis client instance
            job_id: Import job UUID
            total_rows: Total number of rows to process
        """
        self._redis = redis_client
        self._job_id = job_id
        self._total_rows = total_rows
        self._last_update_time = time.time()
        self._namespace = "import_progress"

    def _hash_key(self) -> str:
        """Return Redis hash key for this job."""
        return f"{self._namespace}:hash:{self._job_id}"

    def _channel(self) -> str:
        """Return Redis pub/sub channel for this job."""
        return f"{self._namespace}:channel:{self._job_id}"

    def update(
        self,
        status: str,
        processed_rows: int,
        *,
        stage: str | None = None,
        error_message: str | None = None,
        force: bool = False,
    ) -> None:
        """Update progress in Redis hash and publish to pub/sub if enough time has passed.
        
        Args:
            status: Current import status (parsing, importing, done, failed)
            processed_rows: Number of rows processed so far
            stage: Optional stage description (e.g., "batch_5")
            error_message: Optional error message if failed
            force: Force update even if interval hasn't elapsed
        """
        current_time = time.time()
        elapsed = current_time - self._last_update_time

        # Only update if enough time has passed or force=True (final update)
        if not force and elapsed < PROGRESS_UPDATE_INTERVAL:
            return

        # Calculate progress percentage
        progress_pct = (processed_rows / self._total_rows * 100) if self._total_rows > 0 else 0

        # Build progress payload
        payload = {
            "status": status,
            "processed_rows": processed_rows,
            "total_rows": self._total_rows,
            "progress": round(progress_pct, 2),
            "updated_at": time.time(),
        }

        if stage:
            payload["stage"] = stage
        if error_message:
            payload["error_message"] = error_message

        try:
            # Store in Redis hash
            hash_key = self._hash_key()
            # Convert all values to strings for Redis hash storage
            serialized = {k: str(v) for k, v in payload.items()}
            self._redis.hset(hash_key, mapping=serialized)
            self._redis.expire(hash_key, 3600)  # 1 hour TTL

            # Publish to pub/sub channel
            import json
            channel = self._channel()
            message = json.dumps(payload)
            self._redis.publish(channel, message)

            self._last_update_time = current_time
            logger.debug(
                f"Progress update published for job {self._job_id}: {progress_pct:.2f}% ({processed_rows}/{self._total_rows})"
            )

        except Exception as e:
            # Don't fail the import if Redis updates fail - just log it
            logger.warning(f"Failed to publish progress update for job {self._job_id}: {e}")


def _parse_csv_row(row: dict[str, Any]) -> ProductCreate | None:
    """Parse a CSV row dict into a ProductCreate schema.
    
    Args:
        row: Dictionary representing a CSV row
        
    Returns:
        ProductCreate instance if valid, None if row should be skipped
    """
    # Skip empty rows
    if not row.get("sku") or not row.get("name"):
        return None

    # Parse active field if present
    active = True  # Default
    if "active" in row and row["active"]:
        active_str = str(row["active"]).strip().lower()
        if active_str in ("false", "no", "0", "f", "n"):
            active = False

    return ProductCreate(
        sku=row["sku"].strip(),
        name=row["name"].strip(),
        description=row.get("description", "").strip() or None,
        active=active,
    )


@celery_app.task(
    name="process_csv_import",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=600,
)
def process_csv_import(self, job_id: str, file_path: str) -> dict:
    """Process a CSV import job in the background.
    
    Task Flow:
    1. Celery worker receives task from RabbitMQ (message RESERVED, not ACKed yet)
    2. Update status → "parsing", publish progress to Redis
    3. Stream CSV in chunks (10k rows per batch)
    4. For each batch:
       - Parse rows into Product objects
       - Bulk upsert via ProductRepository.batch_upsert()
       - Update processed_rows in DB
       - Publish progress to Redis (every 2-3s or per batch)
    5. On Success:
       - Set status → "done"
       - Publish final progress
       - Clean up temp file
       - Return success (Celery sends ACK to RabbitMQ automatically with acks_late=True)
    6. On Error:
       - Set status → "failed" + error_message
       - Log error with context
       - Raise exception (Celery handles NACK/requeue based on retry settings)
    
    Args:
        job_id: UUID string of the import job
        file_path: Absolute path to the uploaded CSV file
        
    Returns:
        dict with job completion details
        
    Raises:
        Exception: Any error during processing (will trigger retry via autoretry_for)
    """
    settings = get_settings()
    file_path_obj = Path(file_path)
    
    # Initialize Redis client (synchronous for Celery worker)
    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=False,
        socket_keepalive=True,
    )
    
    logger.info(
        f"Starting CSV import task for job {job_id} (attempt {self.request.retries + 1}/{self.max_retries + 1})"
    )

    try:
        # Validate file exists
        if not file_path_obj.exists():
            error_msg = f"CSV file not found at {file_path}"
            logger.error(f"Job {job_id}: {error_msg}")
            _update_job_failed(job_id, error_msg)
            return {"status": "failed", "error": error_msg}

        # Get total row count from database (should be set during validation)
        with session_scope() as session:
            repo = ImportRepository(session)
            job = repo.get_by_id(UUID(job_id))
            if not job:
                error_msg = f"Import job {job_id} not found in database"
                logger.error(error_msg)
                return {"status": "failed", "error": error_msg}
            
            total_rows = job.total_rows or 0

        # Initialize progress tracker
        tracker = ProgressTracker(redis_client, job_id, total_rows)

        # Update status to PARSING
        with session_scope() as session:
            repo = ImportRepository(session)
            repo.update_status(UUID(job_id), ImportStatus.PARSING)
        
        tracker.update(status="parsing", processed_rows=0, stage="starting", force=True)
        logger.info(f"Job {job_id}: Status updated to PARSING")

        # Process CSV in batches
        processed_rows = 0
        batch_num = 0

        with open(file_path_obj, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            batch: list[ProductCreate] = []

            # Update status to IMPORTING before processing rows
            with session_scope() as session:
                repo = ImportRepository(session)
                repo.update_status(UUID(job_id), ImportStatus.IMPORTING)
            
            tracker.update(status="importing", processed_rows=0, stage="batch_0", force=True)
            logger.info(f"Job {job_id}: Status updated to IMPORTING")

            for row_num, row in enumerate(reader, start=1):
                try:
                    product = _parse_csv_row(row)
                    if product:
                        batch.append(product)
                except Exception as e:
                    logger.warning(f"Job {job_id}: Failed to parse row {row_num}: {e}")
                    # Continue processing other rows
                    continue

                # Process batch when it reaches BATCH_SIZE
                if len(batch) >= BATCH_SIZE:
                    batch_num += 1
                    _process_batch(job_id, batch, batch_num)
                    processed_rows += len(batch)
                    
                    # Update database
                    with session_scope() as session:
                        repo = ImportRepository(session)
                        repo.update_status(
                            UUID(job_id),
                            ImportStatus.IMPORTING,
                            processed_rows=processed_rows,
                        )
                    
                    # Update progress in Redis
                    tracker.update(
                        status="importing",
                        processed_rows=processed_rows,
                        stage=f"batch_{batch_num}",
                        force=True,
                    )
                    
                    logger.info(
                        f"Job {job_id}: Processed batch {batch_num} ({len(batch)} rows, "
                        f"total: {processed_rows}/{total_rows})"
                    )
                    
                    # Clear batch for next iteration
                    batch.clear()

            # Process remaining rows (final partial batch)
            if batch:
                batch_num += 1
                _process_batch(job_id, batch, batch_num)
                processed_rows += len(batch)
                
                with session_scope() as session:
                    repo = ImportRepository(session)
                    repo.update_status(
                        UUID(job_id),
                        ImportStatus.IMPORTING,
                        processed_rows=processed_rows,
                    )
                
                tracker.update(
                    status="importing",
                    processed_rows=processed_rows,
                    stage=f"batch_{batch_num}_final",
                    force=True,
                )
                
                logger.info(
                    f"Job {job_id}: Processed final batch {batch_num} ({len(batch)} rows, "
                    f"total: {processed_rows}/{total_rows})"
                )

        # Success! Update status to DONE
        with session_scope() as session:
            repo = ImportRepository(session)
            repo.update_status(
                UUID(job_id),
                ImportStatus.DONE,
                processed_rows=processed_rows,
            )
        
        tracker.update(
            status="done",
            processed_rows=processed_rows,
            stage="completed",
            force=True,
        )
        
        logger.info(f"Job {job_id}: Import completed successfully ({processed_rows} rows processed)")

        # Publish webhook event for import completion
        try:
            with session_scope() as session:
                from app.services.webhook_service import WebhookService
                webhook_service = WebhookService(session)
                payload = {
                    "job_id": job_id,
                    "status": "done",
                    "processed_rows": processed_rows,
                    "total_rows": total_rows,
                }
                webhook_service.publish_event("import.completed", payload)
        except Exception as webhook_err:
            logger.warning(f"Failed to publish webhook event for import.completed: {webhook_err}")

        # Clean up temporary file
        try:
            file_path_obj.unlink()
            logger.info(f"Job {job_id}: Cleaned up temporary file {file_path}")
        except Exception as e:
            logger.warning(f"Job {job_id}: Failed to delete temp file {file_path}: {e}")

        # Close Redis connection
        redis_client.close()

        return {
            "status": "done",
            "job_id": job_id,
            "processed_rows": processed_rows,
            "total_rows": total_rows,
        }

    except Retry:
        # This is a Celery retry - re-raise to let Celery handle it
        # Don't delete the file yet - it will be needed for retry
        raise

    except Exception as e:
        # Log error with context
        logger.error(
            f"Job {job_id}: Import failed on attempt {self.request.retries + 1}: {e}",
            exc_info=True,
        )

        # Update job status to FAILED
        error_message = f"{type(e).__name__}: {str(e)}"
        
        # Only update to FAILED if this is the final retry attempt
        if self.request.retries >= self.max_retries:
            _update_job_failed(job_id, error_message)
            
            # Publish webhook event for import failure
            try:
                with session_scope() as session:
                    from app.services.webhook_service import WebhookService
                    webhook_service = WebhookService(session)
                    payload = {
                        "job_id": job_id,
                        "status": "failed",
                        "error_message": error_message,
                        "processed_rows": processed_rows if 'processed_rows' in locals() else 0,
                    }
                    webhook_service.publish_event("import.failed", payload)
            except Exception as webhook_err:
                logger.warning(f"Failed to publish webhook event for import.failed: {webhook_err}")
            
            # Only delete file on final failure
            try:
                if file_path_obj.exists():
                    file_path_obj.unlink()
                    logger.info(f"Job {job_id}: Cleaned up temporary file after final failure")
            except Exception as cleanup_err:
                logger.warning(f"Job {job_id}: Failed to delete temp file on error: {cleanup_err}")

        # Update Redis progress
        try:
            tracker.update(
                status="failed" if self.request.retries >= self.max_retries else "importing",
                processed_rows=processed_rows if 'processed_rows' in locals() else 0,
                error_message=error_message,
                force=True,
            )
        except Exception as redis_err:
            logger.warning(f"Job {job_id}: Failed to update Redis on error: {redis_err}")

        # Close Redis connection
        try:
            redis_client.close()
        except Exception:
            pass

        # Re-raise exception to trigger Celery retry mechanism
        # Celery will handle NACK/requeue based on autoretry_for and retry_kwargs
        raise


def _process_batch(job_id: str, batch: list[ProductCreate], batch_num: int) -> None:
    """Process a batch of products with bulk upsert.
    
    Args:
        job_id: Import job UUID for logging
        batch: List of ProductCreate schemas to insert/update (will be copied)
        batch_num: Batch number for logging
        
    Raises:
        Exception: Any database error during batch processing
    """
    # Create a copy to avoid issues with list mutations
    batch_copy = list(batch)
    
    with session_scope() as session:
        product_repo = ProductRepository(session)
        rows_affected = product_repo.batch_upsert(batch_copy)
        logger.debug(f"Job {job_id}: Batch {batch_num} upserted {rows_affected} rows")


def _update_job_failed(job_id: str, error_message: str) -> None:
    """Update import job status to FAILED with error message.
    
    Args:
        job_id: Import job UUID
        error_message: Error description to store
    """
    try:
        with session_scope() as session:
            repo = ImportRepository(session)
            repo.update_status(
                UUID(job_id),
                ImportStatus.FAILED,
                error_message=error_message,
            )
    except Exception as e:
        logger.error(f"Job {job_id}: Failed to update job status to FAILED: {e}")

