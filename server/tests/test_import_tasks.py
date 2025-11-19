"""Tests for Celery import tasks."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch
from uuid import uuid4

import pytest
from redis import Redis

from app.models.import_job import ImportJob, ImportStatus
from app.schemas.product import ProductCreate
from app.tasks.import_tasks import (
    ProgressTracker,
    _parse_csv_row,
    _process_batch,
    _update_job_failed,
    process_csv_import,
)


class TestProgressTracker:
    """Tests for the ProgressTracker helper class."""

    def test_hash_key_generation(self):
        """Test Redis hash key is generated correctly."""
        redis_mock = Mock(spec=Redis)
        job_id = str(uuid4())
        tracker = ProgressTracker(redis_mock, job_id, total_rows=1000)
        
        expected_key = f"import_progress:hash:{job_id}"
        assert tracker._hash_key() == expected_key

    def test_channel_generation(self):
        """Test Redis pub/sub channel is generated correctly."""
        redis_mock = Mock(spec=Redis)
        job_id = str(uuid4())
        tracker = ProgressTracker(redis_mock, job_id, total_rows=1000)
        
        expected_channel = f"import_progress:channel:{job_id}"
        assert tracker._channel() == expected_channel

    def test_update_progress_calculates_percentage(self):
        """Test progress percentage is calculated correctly."""
        redis_mock = Mock(spec=Redis)
        redis_mock.hset = Mock()
        redis_mock.expire = Mock()
        redis_mock.publish = Mock()
        
        job_id = str(uuid4())
        tracker = ProgressTracker(redis_mock, job_id, total_rows=1000)
        
        # Force update to bypass time check
        tracker.update(status="importing", processed_rows=250, force=True)
        
        # Check Redis hash was updated
        redis_mock.hset.assert_called_once()
        call_args = redis_mock.hset.call_args
        
        # Verify the mapping contains progress percentage
        mapping = call_args[1]["mapping"]
        assert mapping["status"] == "importing"
        assert mapping["processed_rows"] == "250"
        assert mapping["total_rows"] == "1000"
        assert float(mapping["progress"]) == 25.0

    def test_update_publishes_to_pubsub(self):
        """Test progress is published to Redis pub/sub channel."""
        redis_mock = Mock(spec=Redis)
        redis_mock.hset = Mock()
        redis_mock.expire = Mock()
        redis_mock.publish = Mock()
        
        job_id = str(uuid4())
        tracker = ProgressTracker(redis_mock, job_id, total_rows=1000)
        
        tracker.update(status="importing", processed_rows=500, stage="batch_5", force=True)
        
        # Verify publish was called
        redis_mock.publish.assert_called_once()
        channel, message = redis_mock.publish.call_args[0]
        
        assert channel == f"import_progress:channel:{job_id}"
        
        # Parse the JSON message
        payload = json.loads(message)
        assert payload["status"] == "importing"
        assert payload["processed_rows"] == 500
        assert payload["progress"] == 50.0
        assert payload["stage"] == "batch_5"

    def test_update_skips_if_interval_not_elapsed(self):
        """Test progress update is skipped if update interval hasn't elapsed."""
        redis_mock = Mock(spec=Redis)
        redis_mock.hset = Mock()
        redis_mock.publish = Mock()
        
        job_id = str(uuid4())
        tracker = ProgressTracker(redis_mock, job_id, total_rows=1000)
        
        # First update (forced)
        tracker.update(status="importing", processed_rows=100, force=True)
        redis_mock.hset.assert_called_once()
        
        # Second update immediately after (should be skipped)
        redis_mock.hset.reset_mock()
        tracker.update(status="importing", processed_rows=200, force=False)
        redis_mock.hset.assert_not_called()

    def test_update_handles_redis_errors_gracefully(self):
        """Test progress tracker doesn't crash if Redis fails."""
        redis_mock = Mock(spec=Redis)
        redis_mock.hset.side_effect = Exception("Redis connection error")
        
        job_id = str(uuid4())
        tracker = ProgressTracker(redis_mock, job_id, total_rows=1000)
        
        # Should not raise exception
        tracker.update(status="importing", processed_rows=100, force=True)


class TestParseCSVRow:
    """Tests for CSV row parsing logic."""

    def test_parse_valid_row(self):
        """Test parsing a valid CSV row."""
        row = {
            "sku": "  TEST-001  ",
            "name": "  Test Product  ",
            "description": "A test product",
            "active": "true",
        }
        
        product = _parse_csv_row(row)
        
        assert product is not None
        assert product.sku == "TEST-001"
        assert product.name == "Test Product"
        assert product.description == "A test product"
        assert product.active is True

    def test_parse_row_with_minimal_fields(self):
        """Test parsing a row with only required fields."""
        row = {
            "sku": "SKU-123",
            "name": "Product Name",
        }
        
        product = _parse_csv_row(row)
        
        assert product is not None
        assert product.sku == "SKU-123"
        assert product.name == "Product Name"
        assert product.description is None
        assert product.active is True  # Default

    def test_parse_row_with_false_active(self):
        """Test parsing active field with various false values."""
        for false_value in ["false", "False", "no", "0", "f", "n"]:
            row = {"sku": "SKU-123", "name": "Product", "active": false_value}
            product = _parse_csv_row(row)
            assert product.active is False, f"Failed for value: {false_value}"

    def test_parse_row_with_true_active(self):
        """Test parsing active field with various true values."""
        for true_value in ["true", "True", "yes", "1", "t", "y"]:
            row = {"sku": "SKU-123", "name": "Product", "active": true_value}
            product = _parse_csv_row(row)
            assert product.active is True, f"Failed for value: {true_value}"

    def test_parse_row_skips_empty_sku(self):
        """Test that rows with empty SKU are skipped."""
        row = {"sku": "", "name": "Product Name"}
        product = _parse_csv_row(row)
        assert product is None

    def test_parse_row_skips_empty_name(self):
        """Test that rows with empty name are skipped."""
        row = {"sku": "SKU-123", "name": ""}
        product = _parse_csv_row(row)
        assert product is None

    def test_parse_row_handles_empty_description(self):
        """Test that empty description is converted to None."""
        row = {"sku": "SKU-123", "name": "Product", "description": ""}
        product = _parse_csv_row(row)
        assert product.description is None


class TestProcessBatch:
    """Tests for batch processing logic."""

    @patch("app.tasks.import_tasks.session_scope")
    def test_process_batch_calls_repository(self, mock_session_scope):
        """Test that _process_batch calls ProductRepository.batch_upsert."""
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        mock_repo = Mock()
        mock_repo.batch_upsert.return_value = 5
        
        with patch("app.tasks.import_tasks.ProductRepository", return_value=mock_repo):
            products = [
                ProductCreate(sku="SKU-1", name="Product 1"),
                ProductCreate(sku="SKU-2", name="Product 2"),
            ]
            
            _process_batch("test-job-id", products, batch_num=1)
            
            mock_repo.batch_upsert.assert_called_once_with(products)


class TestUpdateJobFailed:
    """Tests for job failure update logic."""

    @patch("app.tasks.import_tasks.session_scope")
    def test_update_job_failed_updates_status(self, mock_session_scope):
        """Test that _update_job_failed updates job status to FAILED."""
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        mock_repo = Mock()
        
        with patch("app.tasks.import_tasks.ImportRepository", return_value=mock_repo):
            job_id = str(uuid4())
            error_msg = "Test error message"
            
            _update_job_failed(job_id, error_msg)
            
            mock_repo.update_status.assert_called_once()
            call_args = mock_repo.update_status.call_args[0]
            
            assert str(call_args[0]) == job_id
            assert call_args[1] == ImportStatus.FAILED
            
            call_kwargs = mock_repo.update_status.call_args[1]
            assert call_kwargs["error_message"] == error_msg

    @patch("app.tasks.import_tasks.session_scope")
    def test_update_job_failed_handles_db_errors(self, mock_session_scope):
        """Test that _update_job_failed handles database errors gracefully."""
        mock_session_scope.side_effect = Exception("DB connection error")
        
        # Should not raise exception
        _update_job_failed(str(uuid4()), "Test error")


class TestProcessCSVImport:
    """Tests for the main CSV import task."""

    @pytest.fixture
    def sample_csv_file(self, tmp_path):
        """Create a temporary CSV file for testing."""
        csv_path = tmp_path / "test_import.csv"
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["sku", "name", "description", "active"])
            writer.writeheader()
            
            # Write 25 rows (less than batch size for quick test)
            for i in range(25):
                writer.writerow({
                    "sku": f"SKU-{i:03d}",
                    "name": f"Product {i}",
                    "description": f"Description for product {i}",
                    "active": "true" if i % 2 == 0 else "false",
                })
        
        return csv_path

    @pytest.fixture
    def large_csv_file(self, tmp_path):
        """Create a large CSV file (2 batches) for testing."""
        csv_path = tmp_path / "large_import.csv"
        
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["sku", "name", "description", "active"])
            writer.writeheader()
            
            # Write 12,000 rows (1.2 batches at 10k per batch) - easier to verify
            for i in range(12000):
                writer.writerow({
                    "sku": f"LARGE-SKU-{i:05d}",
                    "name": f"Large Product {i}",
                    "description": f"Desc {i}",
                    "active": "true",
                })
        
        return csv_path

    @patch("app.tasks.import_tasks.Redis")
    @patch("app.tasks.import_tasks.session_scope")
    @patch("app.tasks.import_tasks.get_settings")
    def test_successful_import_small_file(
        self,
        mock_get_settings,
        mock_session_scope,
        mock_redis_class,
        sample_csv_file,
    ):
        """Test successful import of a small CSV file."""
        # Setup mocks
        mock_settings = Mock()
        mock_settings.redis_url = "redis://localhost:6379"
        mock_get_settings.return_value = mock_settings
        
        mock_redis = Mock(spec=Redis)
        mock_redis.hset = Mock()
        mock_redis.expire = Mock()
        mock_redis.publish = Mock()
        mock_redis.close = Mock()
        mock_redis_class.from_url.return_value = mock_redis
        
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        # Mock ImportRepository
        mock_import_repo = Mock()
        mock_job = Mock(spec=ImportJob)
        mock_job.total_rows = 25
        mock_import_repo.get_by_id.return_value = mock_job
        mock_import_repo.update_status = Mock()
        
        # Mock ProductRepository
        mock_product_repo = Mock()
        mock_product_repo.batch_upsert.return_value = 25
        
        with patch("app.tasks.import_tasks.ImportRepository", return_value=mock_import_repo):
            with patch("app.tasks.import_tasks.ProductRepository", return_value=mock_product_repo):
                job_id = str(uuid4())
                
                # Call the task directly using .run() to bypass Celery's autoretry wrapper
                result = process_csv_import.run(job_id, str(sample_csv_file))
                
                # Verify result
                assert result["status"] == "done"
                assert result["job_id"] == job_id
                assert result["processed_rows"] == 25
                
                # Verify status updates were called
                assert mock_import_repo.update_status.call_count >= 2  # At least PARSING and DONE
                
                # Verify batch upsert was called
                mock_product_repo.batch_upsert.assert_called_once()
                
                # Verify temp file was cleaned up
                assert not sample_csv_file.exists()

    @patch("app.tasks.import_tasks.Redis")
    @patch("app.tasks.import_tasks.session_scope")
    @patch("app.tasks.import_tasks.get_settings")
    def test_import_processes_multiple_batches(
        self,
        mock_get_settings,
        mock_session_scope,
        mock_redis_class,
        large_csv_file,
    ):
        """Test that large files are processed in multiple batches."""
        # Setup mocks
        mock_settings = Mock()
        mock_settings.redis_url = "redis://localhost:6379"
        mock_get_settings.return_value = mock_settings
        
        mock_redis = Mock(spec=Redis)
        mock_redis.hset = Mock()
        mock_redis.expire = Mock()
        mock_redis.publish = Mock()
        mock_redis.close = Mock()
        mock_redis_class.from_url.return_value = mock_redis
        
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        # Mock ImportRepository
        mock_import_repo = Mock()
        mock_job = Mock(spec=ImportJob)
        mock_job.total_rows = 12000
        mock_import_repo.get_by_id.return_value = mock_job
        mock_import_repo.update_status = Mock()
        
        # Mock ProductRepository
        mock_product_repo = Mock()
        mock_product_repo.batch_upsert.return_value = 10000  # Return value doesn't matter much
        
        with patch("app.tasks.import_tasks.ImportRepository", return_value=mock_import_repo):
            with patch("app.tasks.import_tasks.ProductRepository", return_value=mock_product_repo):
                job_id = str(uuid4())
                
                # Call the task directly using .run() to bypass Celery's autoretry wrapper
                result = process_csv_import.run(job_id, str(large_csv_file))
                
                # Verify result
                assert result["status"] == "done"
                assert result["processed_rows"] == 12000
                
                # Verify batch_upsert was called twice (one full batch + one partial)
                assert mock_product_repo.batch_upsert.call_count == 2
                
                # Verify batches total to 12,000 rows
                all_calls = mock_product_repo.batch_upsert.call_args_list
                batch_sizes = [len(call[0][0]) for call in all_calls]
                total_processed = sum(batch_sizes)
                assert total_processed == 12000, f"Expected 12,000 total rows, got {total_processed} from batches: {batch_sizes}"
                
                # First batch should be the full 10k size, second should be 2k
                assert batch_sizes == [10000, 2000], f"Expected batches [10000, 2000], got: {batch_sizes}"

    @patch("app.tasks.import_tasks.Redis")
    @patch("app.tasks.import_tasks.session_scope")
    @patch("app.tasks.import_tasks.get_settings")
    def test_import_handles_missing_file(
        self,
        mock_get_settings,
        mock_session_scope,
        mock_redis_class,
    ):
        """Test that task handles missing file gracefully."""
        mock_settings = Mock()
        mock_settings.redis_url = "redis://localhost:6379"
        mock_get_settings.return_value = mock_settings
        
        mock_redis = Mock(spec=Redis)
        mock_redis.close = Mock()
        mock_redis_class.from_url.return_value = mock_redis
        
        job_id = str(uuid4())
        
        # Call the task directly using .run() to bypass Celery's autoretry wrapper
        result = process_csv_import.run(job_id, "/nonexistent/file.csv")
        
        assert result["status"] == "failed"
        assert "not found" in result["error"].lower()

    @patch("app.tasks.import_tasks.Redis")
    @patch("app.tasks.import_tasks.session_scope")
    @patch("app.tasks.import_tasks.get_settings")
    def test_import_cleans_up_file_on_error(
        self,
        mock_get_settings,
        mock_session_scope,
        mock_redis_class,
        sample_csv_file,
    ):
        """Test that temp file is cleaned up even when processing fails."""
        mock_settings = Mock()
        mock_settings.redis_url = "redis://localhost:6379"
        mock_get_settings.return_value = mock_settings
        
        mock_redis = Mock(spec=Redis)
        mock_redis.hset = Mock()
        mock_redis.expire = Mock()
        mock_redis.publish = Mock()
        mock_redis.close = Mock()
        mock_redis_class.from_url.return_value = mock_redis
        
        mock_session = MagicMock()
        mock_session_scope.return_value.__enter__.return_value = mock_session
        
        # Mock ImportRepository
        mock_import_repo = Mock()
        mock_job = Mock(spec=ImportJob)
        mock_job.total_rows = 25
        mock_import_repo.get_by_id.return_value = mock_job
        mock_import_repo.update_status = Mock()
        
        # Mock ProductRepository to raise error
        mock_product_repo = Mock()
        mock_product_repo.batch_upsert.side_effect = Exception("Database error")
        
        with patch("app.tasks.import_tasks.ImportRepository", return_value=mock_import_repo):
            with patch("app.tasks.import_tasks.ProductRepository", return_value=mock_product_repo):
                job_id = str(uuid4())
                
                # Task should raise exception (to trigger retry)
                # Call the task directly using .run() to bypass Celery's autoretry wrapper
                with pytest.raises(Exception, match="Database error"):
                    process_csv_import.run(job_id, str(sample_csv_file))
                
                # Verify temp file was still cleaned up
                assert not sample_csv_file.exists()


class TestIntegrationProgressTracking:
    """Integration tests for progress tracking during import."""

    @pytest.fixture
    def redis_client(self):
        """Create a real Redis client for integration testing."""
        try:
            from redis import Redis
            client = Redis(host="localhost", port=6379, db=15)  # Use test DB
            client.ping()
            yield client
            # Cleanup
            client.flushdb()
            client.close()
        except Exception:
            pytest.skip("Redis not available for integration tests")

    def test_progress_updates_in_redis(self, redis_client):
        """Test that progress updates are actually stored in Redis."""
        job_id = str(uuid4())
        tracker = ProgressTracker(redis_client, job_id, total_rows=1000)
        
        # Update progress
        tracker.update(status="importing", processed_rows=500, stage="batch_5", force=True)
        
        # Verify data in Redis
        hash_key = f"import_progress:hash:{job_id}"
        data = redis_client.hgetall(hash_key)
        
        assert data
        assert data[b"status"] == b"importing"
        assert data[b"processed_rows"] == b"500"
        assert data[b"total_rows"] == b"1000"
        assert float(data[b"progress"]) == 50.0
        assert data[b"stage"] == b"batch_5"

