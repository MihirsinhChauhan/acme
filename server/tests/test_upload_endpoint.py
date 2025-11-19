"""Tests for CSV upload endpoint."""
from __future__ import annotations

import io
from pathlib import Path
from unittest.mock import MagicMock, patch
from uuid import uuid4

import pytest
from fastapi import status
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.core.db import get_session
from app.models.import_job import ImportStatus


@pytest.fixture
def client(db_session: Session):
    """Create a FastAPI test client with overridden database session."""

    def override_get_session():
        yield db_session

    app.dependency_overrides[get_session] = override_get_session
    
    with TestClient(app) as test_client:
        yield test_client
    
    app.dependency_overrides.clear()


@pytest.fixture
def sample_csv_content() -> bytes:
    """Sample valid CSV content for testing."""
    return b"""sku,name,description,active
TEST-001,Test Product 1,A great product,true
TEST-002,Test Product 2,Another product,false
TEST-003,Test Product 3,Yet another product,true
"""


@pytest.fixture
def invalid_csv_content() -> bytes:
    """Sample invalid CSV content (missing required 'name' header)."""
    return b"""sku,description,active
TEST-001,A great product,true
TEST-002,Another product,false
"""


@pytest.fixture
def large_csv_content() -> bytes:
    """Generate a large CSV for testing size limits."""
    header = b"sku,name,description,active\n"
    # Create ~1000 rows to simulate a larger file
    rows = []
    for i in range(1000):
        rows.append(f"SKU-{i:05d},Product {i},Description for product {i},true\n".encode())
    return header + b"".join(rows)


def test_upload_csv_success(client: TestClient, sample_csv_content: bytes, db_session: Session):
    """Test successful CSV upload with valid file."""
    
    # Mock the Celery task to avoid requiring RabbitMQ in tests
    with patch("app.tasks.import_tasks.process_csv_import") as mock_task:
        mock_task.apply_async.return_value = MagicMock(id=str(uuid4()))
        
        # Create a file-like object
        files = {"file": ("products.csv", io.BytesIO(sample_csv_content), "text/csv")}
        
        response = client.post("/api/upload", files=files)
        
        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        
        # Validate response structure
        assert "job_id" in data
        assert "sse_url" in data
        assert "message" in data
        
        # Validate SSE URL format
        assert data["sse_url"].startswith("/api/progress/")
        assert data["job_id"] in data["sse_url"]
        
        # Verify job was created in database
        from app.services.import_service import ImportService
        import_service = ImportService(db_session)
        from uuid import UUID
        job = import_service.get_job(UUID(data["job_id"]))
        
        assert job is not None
        assert job.filename == "products.csv"
        assert job.status == ImportStatus.QUEUED
        assert job.total_rows == 3  # 3 data rows (excluding header)
        
        # Verify Celery task was enqueued
        mock_task.apply_async.assert_called_once()


def test_upload_csv_invalid_file_type(client: TestClient):
    """Test upload with non-CSV file."""
    
    files = {"file": ("document.txt", io.BytesIO(b"not a csv"), "text/plain")}
    
    response = client.post("/api/upload", files=files)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Invalid file type" in response.json()["detail"]


def test_upload_csv_missing_required_headers(
    client: TestClient, invalid_csv_content: bytes
):
    """Test upload with CSV missing required headers."""
    
    files = {"file": ("invalid.csv", io.BytesIO(invalid_csv_content), "text/csv")}
    
    response = client.post("/api/upload", files=files)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    
    assert "detail" in data
    assert "message" in data["detail"]
    assert "CSV validation failed" in data["detail"]["message"]
    assert "errors" in data["detail"]
    assert any("Missing required headers" in err for err in data["detail"]["errors"])


def test_upload_csv_empty_file(client: TestClient):
    """Test upload with empty CSV file."""
    
    files = {"file": ("empty.csv", io.BytesIO(b""), "text/csv")}
    
    response = client.post("/api/upload", files=files)
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST


def test_upload_csv_no_filename(client: TestClient):
    """Test upload without filename."""
    
    # Create file without name
    files = {"file": ("", io.BytesIO(b"sku,name\n"), "text/csv")}
    
    response = client.post("/api/upload", files=files)
    
    # Should fail with 400 or 422 (filename required)
    assert response.status_code in (
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_422_UNPROCESSABLE_ENTITY,
    )


def test_upload_csv_file_size_validation(client: TestClient, large_csv_content: bytes):
    """Test that file size is validated (though this is a soft test since our limit is 512MB)."""
    
    with patch("app.tasks.import_tasks.process_csv_import") as mock_task:
        mock_task.apply_async.return_value = MagicMock(id=str(uuid4()))
        
        files = {"file": ("large.csv", io.BytesIO(large_csv_content), "text/csv")}
        
        response = client.post("/api/upload", files=files)
        
        # Should succeed (file is well under limit)
        assert response.status_code == status.HTTP_202_ACCEPTED


def test_upload_csv_malformed_data(client: TestClient):
    """Test upload with malformed CSV data."""
    
    # CSV with mismatched columns
    malformed = b"""sku,name,description,active
TEST-001,Product 1,Description
TEST-002,Product 2
"""
    
    with patch("app.tasks.import_tasks.process_csv_import") as mock_task:
        mock_task.apply_async.return_value = MagicMock(id=str(uuid4()))
        
        files = {"file": ("malformed.csv", io.BytesIO(malformed), "text/csv")}
        
        response = client.post("/api/upload", files=files)
        
        # CSV parser is lenient with missing fields, so this might succeed
        # The validation happens row-by-row during processing
        # For this test, we just verify the endpoint doesn't crash
        assert response.status_code in (
            status.HTTP_202_ACCEPTED,
            status.HTTP_400_BAD_REQUEST,
        )


def test_upload_csv_celery_task_failure(client: TestClient, sample_csv_content: bytes):
    """Test handling when Celery task enqueueing fails."""
    
    with patch("app.tasks.import_tasks.process_csv_import") as mock_task:
        # Simulate Celery connection failure
        mock_task.apply_async.side_effect = Exception("RabbitMQ connection failed")
        
        files = {"file": ("products.csv", io.BytesIO(sample_csv_content), "text/csv")}
        
        response = client.post("/api/upload", files=files)
        
        # Should return 500 internal server error
        assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
        assert "Failed to process upload" in response.json()["detail"]


def test_upload_csv_temp_file_cleanup_on_validation_failure(
    client: TestClient, invalid_csv_content: bytes, tmp_path: Path
):
    """Test that temporary files are cleaned up when validation fails."""
    
    # Override upload directory to use pytest's tmp_path
    with patch("app.api.upload.settings") as mock_settings:
        mock_settings.upload_tmp_dir = str(tmp_path)
        mock_settings.max_upload_size_mb = 512
        mock_settings.api_prefix = "/api"
        
        files = {"file": ("invalid.csv", io.BytesIO(invalid_csv_content), "text/csv")}
        
        response = client.post("/api/upload", files=files)
        
        # Request should fail with validation error
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        
        # Verify no CSV files remain in temp directory
        csv_files = list(tmp_path.glob("*.csv"))
        assert len(csv_files) == 0, "Temp files should be cleaned up on validation failure"


def test_upload_csv_with_warnings(client: TestClient):
    """Test upload with CSV that has warnings but is still valid."""
    
    # CSV with extra unknown headers (should warn but succeed)
    csv_with_unknown_headers = b"""sku,name,description,active,extra_field,unknown_column
TEST-001,Product 1,Description,true,extra_value,unknown_value
TEST-002,Product 2,Description 2,false,extra_value2,unknown_value2
"""
    
    with patch("app.tasks.import_tasks.process_csv_import") as mock_task:
        mock_task.apply_async.return_value = MagicMock(id=str(uuid4()))
        
        files = {"file": ("products.csv", io.BytesIO(csv_with_unknown_headers), "text/csv")}
        
        response = client.post("/api/upload", files=files)
        
        # Should succeed despite warnings
        assert response.status_code == status.HTTP_202_ACCEPTED
        
        data = response.json()
        assert "job_id" in data


def test_upload_creates_upload_directory_if_missing(
    client: TestClient, sample_csv_content: bytes, tmp_path: Path
):
    """Test that upload endpoint creates upload directory if it doesn't exist."""
    
    # Use a non-existent subdirectory
    non_existent_dir = tmp_path / "non_existent_upload_dir"
    assert not non_existent_dir.exists()
    
    with patch("app.api.upload.settings") as mock_settings:
        mock_settings.upload_tmp_dir = str(non_existent_dir)
        mock_settings.max_upload_size_mb = 512
        mock_settings.api_prefix = "/api"
        
        with patch("app.tasks.import_tasks.process_csv_import") as mock_task:
            mock_task.apply_async.return_value = MagicMock(id=str(uuid4()))
            
            files = {"file": ("products.csv", io.BytesIO(sample_csv_content), "text/csv")}
            
            response = client.post("/api/upload", files=files)
            
            assert response.status_code == status.HTTP_202_ACCEPTED
            
            # Verify directory was created
            assert non_existent_dir.exists()

