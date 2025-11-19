"""Tests for ImportService and ImportRepository."""
from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from sqlalchemy.orm import Session

from app.models.import_job import ImportJob, ImportStatus
from app.schemas.import_job import ImportJobCreate
from app.services.import_service import ImportRepository, ImportService

if TYPE_CHECKING:
    from _pytest.tmpdir import TempPathFactory


@pytest.fixture
def temp_csv_file(tmp_path_factory: TempPathFactory) -> Path:
    """Create a temporary CSV file for testing."""
    csv_dir = tmp_path_factory.mktemp("csv_files")
    csv_file = csv_dir / "test.csv"
    csv_file.write_text("sku,name\nSKU-001,Product 1\n")
    return csv_file


class TestImportRepository:
    """Test suite for ImportRepository."""

    def test_create_import_job(self, db_session: Session) -> None:
        """Test creating a new import job."""
        repo = ImportRepository(db_session)
        
        job_data = ImportJobCreate(filename="test.csv", total_rows=100)
        job = repo.create(job_data)
        
        assert isinstance(job.id, UUID)
        assert job.filename == "test.csv"
        assert job.total_rows == 100
        assert job.status == ImportStatus.QUEUED
        assert job.processed_rows == 0
        assert job.error_message is None
        assert job.created_at is not None

    def test_create_import_job_without_total_rows(self, db_session: Session) -> None:
        """Test creating import job without total_rows hint."""
        repo = ImportRepository(db_session)
        
        job_data = ImportJobCreate(filename="test.csv", total_rows=None)
        job = repo.create(job_data)
        
        assert job.filename == "test.csv"
        assert job.total_rows is None

    def test_get_by_id(self, db_session: Session) -> None:
        """Test fetching import job by ID."""
        repo = ImportRepository(db_session)
        
        job_data = ImportJobCreate(filename="test.csv", total_rows=50)
        created_job = repo.create(job_data)
        
        fetched_job = repo.get_by_id(created_job.id)
        assert fetched_job is not None
        assert fetched_job.id == created_job.id
        assert fetched_job.filename == "test.csv"

    def test_get_by_id_not_found(self, db_session: Session) -> None:
        """Test get_by_id returns None when job doesn't exist."""
        repo = ImportRepository(db_session)
        
        import uuid
        job = repo.get_by_id(uuid.uuid4())
        assert job is None

    def test_update_status(self, db_session: Session) -> None:
        """Test updating import job status."""
        repo = ImportRepository(db_session)
        
        # Create job
        job_data = ImportJobCreate(filename="test.csv", total_rows=100)
        job = repo.create(job_data)
        
        # Update to parsing
        updated = repo.update_status(job.id, ImportStatus.PARSING)
        assert updated is not None
        assert updated.status == ImportStatus.PARSING
        
        # Update to importing with processed rows
        updated = repo.update_status(job.id, ImportStatus.IMPORTING, processed_rows=50)
        assert updated.status == ImportStatus.IMPORTING
        assert updated.processed_rows == 50

    def test_update_status_with_error_message(self, db_session: Session) -> None:
        """Test updating status with error message."""
        repo = ImportRepository(db_session)
        
        job_data = ImportJobCreate(filename="test.csv", total_rows=100)
        job = repo.create(job_data)
        
        updated = repo.update_status(
            job.id,
            ImportStatus.FAILED,
            error_message="Database connection failed",
        )
        assert updated.status == ImportStatus.FAILED
        assert updated.error_message == "Database connection failed"

    def test_update_status_not_found(self, db_session: Session) -> None:
        """Test update_status returns None when job doesn't exist."""
        repo = ImportRepository(db_session)
        
        import uuid
        result = repo.update_status(uuid.uuid4(), ImportStatus.DONE)
        assert result is None

    def test_increment_processed_rows(self, db_session: Session) -> None:
        """Test incrementing processed rows counter."""
        repo = ImportRepository(db_session)
        
        job_data = ImportJobCreate(filename="test.csv", total_rows=1000)
        job = repo.create(job_data)
        
        # Increment by 100
        updated = repo.increment_processed_rows(job.id, 100)
        assert updated.processed_rows == 100
        
        # Increment by 250
        updated = repo.increment_processed_rows(job.id, 250)
        assert updated.processed_rows == 350
        
        # Increment by 650
        updated = repo.increment_processed_rows(job.id, 650)
        assert updated.processed_rows == 1000

    def test_increment_processed_rows_not_found(self, db_session: Session) -> None:
        """Test increment_processed_rows returns None when job doesn't exist."""
        repo = ImportRepository(db_session)
        
        import uuid
        result = repo.increment_processed_rows(uuid.uuid4(), 100)
        assert result is None

    def test_get_recent(self, db_session: Session) -> None:
        """Test fetching recent import jobs."""
        repo = ImportRepository(db_session)
        
        # Create multiple jobs
        for i in range(10):
            job_data = ImportJobCreate(filename=f"file{i}.csv", total_rows=100)
            repo.create(job_data)
        
        recent_jobs = repo.get_recent(limit=5)
        assert len(recent_jobs) == 5
        # Should be ordered by created_at descending (but might have same timestamp)
        filenames = {job.filename for job in recent_jobs}
        assert len(filenames) == 5  # All unique
        assert all(f"file{i}.csv" in [j.filename for j in repo.get_recent(limit=10)] for i in range(10))

    def test_get_recent_empty(self, db_session: Session) -> None:
        """Test get_recent returns empty list when no jobs exist."""
        repo = ImportRepository(db_session)
        
        recent_jobs = repo.get_recent()
        assert recent_jobs == []


class TestImportService:
    """Test suite for ImportService."""

    def test_create_import_job(self, db_session: Session) -> None:
        """Test creating import job through service."""
        service = ImportService(db_session)
        
        response = service.create_import_job("test.csv", total_rows=500)
        
        assert isinstance(response.id, UUID)
        assert response.filename == "test.csv"
        assert response.total_rows == 500
        assert response.status == ImportStatus.QUEUED
        assert response.processed_rows == 0

    def test_create_import_job_without_total_rows(self, db_session: Session) -> None:
        """Test creating import job without total_rows."""
        service = ImportService(db_session)
        
        response = service.create_import_job("test.csv")
        
        assert response.filename == "test.csv"
        assert response.total_rows is None

    def test_enqueue_import_task(self, db_session: Session, temp_csv_file: Path) -> None:
        """Test enqueueing import task."""
        service = ImportService(db_session)
        
        response = service.create_import_job("test.csv", total_rows=10)
        
        # Mock the Celery task to avoid Redis connection
        # Patch where it's imported in import_service, not where it's defined
        with patch("app.tasks.import_tasks.process_csv_import") as mock_task:
            mock_result = MagicMock()
            mock_result.id = str(response.id)
            mock_task.apply_async.return_value = mock_result
            
            task_id = service.enqueue_import_task(response.id, temp_csv_file)
            
            assert task_id == str(response.id)
            mock_task.apply_async.assert_called_once_with(
                args=[str(response.id), str(temp_csv_file)],
                task_id=str(response.id),
            )

    def test_enqueue_import_task_file_not_found(self, db_session: Session) -> None:
        """Test enqueueing task with non-existent file."""
        service = ImportService(db_session)
        
        response = service.create_import_job("test.csv")
        nonexistent_file = Path("/tmp/nonexistent_file_12345.csv")
        
        with pytest.raises(FileNotFoundError, match="CSV file not found"):
            service.enqueue_import_task(response.id, nonexistent_file)

    def test_get_job(self, db_session: Session) -> None:
        """Test fetching job by ID through service."""
        service = ImportService(db_session)
        
        created = service.create_import_job("test.csv", total_rows=100)
        
        fetched = service.get_job(created.id)
        assert fetched is not None
        assert fetched.id == created.id
        assert fetched.filename == "test.csv"

    def test_get_job_not_found(self, db_session: Session) -> None:
        """Test get_job returns None when job doesn't exist."""
        service = ImportService(db_session)
        
        import uuid
        job = service.get_job(uuid.uuid4())
        assert job is None

    def test_list_recent_jobs(self, db_session: Session) -> None:
        """Test listing recent jobs through service."""
        service = ImportService(db_session)
        
        # Create multiple jobs
        for i in range(5):
            service.create_import_job(f"file{i}.csv", total_rows=100 * i)
        
        recent = service.list_recent_jobs(limit=3)
        assert len(recent) == 3
        # All 5 jobs should exist
        all_jobs = service.list_recent_jobs(limit=10)
        filenames = {job.filename for job in all_jobs}
        assert filenames == {f"file{i}.csv" for i in range(5)}

    def test_list_recent_jobs_empty(self, db_session: Session) -> None:
        """Test listing recent jobs when none exist."""
        service = ImportService(db_session)
        
        recent = service.list_recent_jobs()
        assert recent == []

    def test_full_workflow(self, db_session: Session) -> None:
        """Test complete workflow: create job, update status, check progress."""
        service = ImportService(db_session)
        repo = ImportRepository(db_session)
        
        # Create job
        job_response = service.create_import_job("workflow_test.csv", total_rows=1000)
        job_id = job_response.id
        
        # Simulate worker updating status
        repo.update_status(job_id, ImportStatus.PARSING)
        job = service.get_job(job_id)
        assert job.status == ImportStatus.PARSING
        
        # Simulate processing batches
        repo.update_status(job_id, ImportStatus.IMPORTING)
        repo.increment_processed_rows(job_id, 500)
        job = service.get_job(job_id)
        assert job.status == ImportStatus.IMPORTING
        assert job.processed_rows == 500
        
        # Complete
        repo.update_status(job_id, ImportStatus.DONE, processed_rows=1000)
        job = service.get_job(job_id)
        assert job.status == ImportStatus.DONE
        assert job.processed_rows == 1000

    def test_error_workflow(self, db_session: Session) -> None:
        """Test error handling workflow."""
        service = ImportService(db_session)
        repo = ImportRepository(db_session)
        
        # Create job
        job_response = service.create_import_job("error_test.csv", total_rows=500)
        job_id = job_response.id
        
        # Start processing
        repo.update_status(job_id, ImportStatus.IMPORTING)
        repo.increment_processed_rows(job_id, 100)
        
        # Fail with error
        repo.update_status(
            job_id,
            ImportStatus.FAILED,
            error_message="Unexpected column format at row 123",
        )
        
        job = service.get_job(job_id)
        assert job.status == ImportStatus.FAILED
        assert job.processed_rows == 100
        assert "Unexpected column format" in job.error_message

