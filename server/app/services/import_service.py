"""Service layer for managing CSV import lifecycle."""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from sqlalchemy.orm import Session

from app.models.import_job import ImportJob, ImportStatus
from app.schemas.import_job import ImportJobCreate, ImportJobResponse


class ImportRepository:
    """Handles CRUD operations for ImportJob entities."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with a SQLAlchemy session.
        
        Args:
            session: Active database session for executing queries
        """
        self._session = session

    def create(self, job_data: ImportJobCreate) -> ImportJob:
        """Create a new import job record in the database.
        
        Args:
            job_data: Import job creation payload
            
        Returns:
            Newly created ImportJob instance with generated ID
        """
        job = ImportJob(
            filename=job_data.filename,
            total_rows=job_data.total_rows,
            status=ImportStatus.QUEUED,
            processed_rows=0,
        )
        self._session.add(job)
        self._session.commit()
        self._session.refresh(job)
        return job

    def get_by_id(self, job_id: UUID) -> ImportJob | None:
        """Fetch an import job by its UUID.
        
        Args:
            job_id: Import job identifier
            
        Returns:
            ImportJob instance if found, None otherwise
        """
        return self._session.get(ImportJob, job_id)

    def update_status(
        self,
        job_id: UUID,
        status: ImportStatus,
        *,
        processed_rows: int | None = None,
        error_message: str | None = None,
    ) -> ImportJob | None:
        """Update import job status and optional fields.
        
        Args:
            job_id: Import job identifier
            status: New status value
            processed_rows: Optional number of rows processed so far
            error_message: Optional error message if job failed
            
        Returns:
            Updated ImportJob instance, or None if not found
        """
        job = self.get_by_id(job_id)
        if not job:
            return None

        job.status = status
        if processed_rows is not None:
            job.processed_rows = processed_rows
        if error_message is not None:
            job.error_message = error_message

        job.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(job)
        return job

    def increment_processed_rows(self, job_id: UUID, count: int) -> ImportJob | None:
        """Atomically increment the processed_rows counter.
        
        Args:
            job_id: Import job identifier
            count: Number of rows to add to the counter
            
        Returns:
            Updated ImportJob instance, or None if not found
        """
        job = self.get_by_id(job_id)
        if not job:
            return None

        job.processed_rows += count
        job.updated_at = datetime.now(timezone.utc)
        self._session.commit()
        self._session.refresh(job)
        return job

    def get_recent(self, limit: int = 50) -> list[ImportJob]:
        """Fetch recent import jobs ordered by creation time.
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List of ImportJob instances
        """
        return (
            self._session.query(ImportJob)
            .order_by(ImportJob.created_at.desc())
            .limit(limit)
            .all()
        )


class ImportService:
    """High-level service coordinating import job creation and task enqueueing."""

    def __init__(self, session: Session) -> None:
        """Initialize service with a database session.
        
        Args:
            session: Active database session
        """
        self._session = session
        self._repository = ImportRepository(session)

    def create_import_job(self, filename: str, total_rows: int | None = None) -> ImportJobResponse:
        """Create a new import job record in the database.
        
        This is typically called after file upload and validation, before enqueueing
        the background task.
        
        Args:
            filename: Original filename of the uploaded CSV
            total_rows: Optional hint about CSV row count (from validation phase)
            
        Returns:
            ImportJobResponse schema with the created job details
        """
        job_data = ImportJobCreate(filename=filename, total_rows=total_rows)
        job = self._repository.create(job_data)
        return ImportJobResponse.model_validate(job)

    def enqueue_import_task(self, job_id: UUID, file_path: str | Path) -> str:
        """Publish a Celery task to RabbitMQ for async CSV processing.
        
        This delegates the heavy lifting to a Celery worker, allowing the API
        to return immediately.
        
        Args:
            job_id: Import job UUID to process
            file_path: Absolute path to the uploaded CSV file
            
        Returns:
            Celery task ID for tracking/debugging
            
        Raises:
            ImportError: If Celery tasks are not properly configured
            FileNotFoundError: If file_path does not exist
        """
        # Lazy import to avoid circular dependencies and allow testing without full setup
        from app.tasks.import_tasks import process_csv_import

        # Validate file exists before enqueueing
        path = Path(file_path)
        if not path.exists():
            msg = f"CSV file not found at {file_path}"
            raise FileNotFoundError(msg)

        # Send task to RabbitMQ via Celery
        # The worker will receive it and begin processing
        task = process_csv_import.apply_async(
            args=[str(job_id), str(path)],
            task_id=str(job_id),  # Use job_id as task_id for easier correlation
        )

        return task.id

    def get_job(self, job_id: UUID) -> ImportJobResponse | None:
        """Fetch an import job by ID.
        
        Args:
            job_id: Import job identifier
            
        Returns:
            ImportJobResponse if found, None otherwise
        """
        job = self._repository.get_by_id(job_id)
        if not job:
            return None
        return ImportJobResponse.model_validate(job)

    def list_recent_jobs(self, limit: int = 50) -> list[ImportJobResponse]:
        """Fetch recent import jobs.
        
        Args:
            limit: Maximum number of jobs to return
            
        Returns:
            List of ImportJobResponse schemas
        """
        jobs = self._repository.get_recent(limit=limit)
        return [ImportJobResponse.model_validate(job) for job in jobs]

