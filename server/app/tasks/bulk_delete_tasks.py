"""Celery tasks for bulk deletion of all products.

This module implements the background worker task for deleting all products
in batches with progress tracking.
"""
from __future__ import annotations

import logging
import time
from uuid import UUID

from redis import Redis
from celery.exceptions import Retry
from sqlalchemy import delete, select, func

from app.core.config import get_settings
from app.core.db import session_scope
from app.models.import_job import ImportStatus, JobType
from app.models.product import Product
from app.services.import_service import ImportRepository
from app.tasks.celery_app import celery_app

# Configure logging
logger = logging.getLogger(__name__)

# Constants
BATCH_SIZE = 10_000  # Delete 10k rows per batch
PROGRESS_UPDATE_INTERVAL = 2.0  # Update progress every 2 seconds


class BulkDeleteProgressTracker:
    """Helper class to track and publish bulk delete progress to Redis."""

    def __init__(self, redis_client: Redis, job_id: str, total_products: int):
        """Initialize progress tracker.
        
        Args:
            redis_client: Synchronous Redis client instance
            job_id: Job UUID
            total_products: Total number of products to delete
        """
        self._redis = redis_client
        self._job_id = job_id
        self._total_products = total_products
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
        deleted_count: int,
        *,
        stage: str | None = None,
        error_message: str | None = None,
        force: bool = False,
    ) -> None:
        """Update progress in Redis hash and publish to pub/sub if enough time has passed.
        
        Args:
            status: Current job status (preparing, deleting, done, failed)
            deleted_count: Number of products deleted so far
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
        progress_pct = (deleted_count / self._total_products * 100) if self._total_products > 0 else 0

        # Build progress payload
        payload = {
            "status": status,
            "processed_rows": deleted_count,  # Use processed_rows for consistency with import
            "total_rows": self._total_products,  # Use total_rows for consistency
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
                f"Progress update published for job {self._job_id}: {progress_pct:.2f}% ({deleted_count}/{self._total_products})"
            )

        except Exception as e:
            # Don't fail the deletion if Redis updates fail - just log it
            logger.warning(f"Failed to publish progress update for job {self._job_id}: {e}")


@celery_app.task(
    name="bulk_delete_all_products",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=600,
)
def bulk_delete_all_products_task(self, job_id: str) -> dict:
    """Delete all products in the database in batches.
    
    Task Flow:
    1. Celery worker receives task from RabbitMQ
    2. Update status → "preparing", count total products
    3. Delete products in batches (10k per batch)
    4. For each batch:
       - Execute DELETE FROM products WHERE id IN (...)
       - Update processed_rows in DB
       - Publish progress to Redis (every 2-3s or per batch)
    5. On Success:
       - Set status → "done"
       - Publish final progress
       - Return success
    6. On Error:
       - Set status → "failed" + error_message
       - Log error with context
       - Raise exception (Celery handles NACK/requeue based on retry settings)
    
    Args:
        job_id: UUID string of the deletion job
        
    Returns:
        dict with job completion details
        
    Raises:
        Exception: Any error during processing (will trigger retry via autoretry_for)
    """
    settings = get_settings()
    
    # Initialize Redis client (synchronous for Celery worker)
    redis_client = Redis.from_url(
        settings.redis_url,
        decode_responses=False,
        socket_keepalive=True,
    )
    
    logger.info(
        f"Starting bulk delete task for job {job_id} (attempt {self.request.retries + 1}/{self.max_retries + 1})"
    )

    try:
        # Get job from database
        with session_scope() as session:
            repo = ImportRepository(session)
            job = repo.get_by_id(UUID(job_id))
            if not job:
                error_msg = f"Delete job {job_id} not found in database"
                logger.error(error_msg)
                return {"status": "failed", "error": error_msg}
            
            # Verify job type
            if job.job_type != JobType.BULK_DELETE:
                error_msg = f"Job {job_id} is not a bulk_delete job (type: {job.job_type})"
                logger.error(error_msg)
                return {"status": "failed", "error": error_msg}

        # Count total products
        with session_scope() as session:
            total_products = session.scalar(select(func.count(Product.id)))
            total_products = total_products or 0

        logger.info(f"Job {job_id}: Found {total_products} products to delete")

        # Initialize progress tracker
        tracker = BulkDeleteProgressTracker(redis_client, job_id, total_products)

        # Update status to PREPARING (reuse PARSING status for consistency)
        with session_scope() as session:
            repo = ImportRepository(session)
            repo.update_status(UUID(job_id), ImportStatus.PARSING)
        
        tracker.update(status="preparing", deleted_count=0, stage="counting", force=True)
        logger.info(f"Job {job_id}: Status updated to PREPARING")

        # If no products, mark as done immediately
        if total_products == 0:
            with session_scope() as session:
                repo = ImportRepository(session)
                repo.update_status(UUID(job_id), ImportStatus.DONE, processed_rows=0)
            
            tracker.update(
                status="done",
                deleted_count=0,
                stage="completed",
                force=True,
            )
            
            logger.info(f"Job {job_id}: No products to delete, job completed")
            
            # Publish webhook event for bulk delete completion (no products case)
            try:
                with session_scope() as session:
                    from app.services.webhook_service import WebhookService
                    webhook_service = WebhookService(session)
                    payload = {
                        "job_id": job_id,
                        "status": "done",
                        "deleted_count": 0,
                        "total_products": 0,
                    }
                    webhook_service.publish_event("product.bulk_deleted", payload)
            except Exception as webhook_err:
                logger.warning(f"Failed to publish webhook event for product.bulk_deleted: {webhook_err}")
            
            redis_client.close()
            
            return {
                "status": "done",
                "job_id": job_id,
                "deleted_count": 0,
                "total_products": 0,
            }

        # Update status to IMPORTING (reuse for deletion phase)
        with session_scope() as session:
            repo = ImportRepository(session)
            repo.update_status(UUID(job_id), ImportStatus.IMPORTING)
        
        tracker.update(status="deleting", deleted_count=0, stage="batch_0", force=True)
        logger.info(f"Job {job_id}: Status updated to DELETING")

        # Delete products in batches
        deleted_count = 0
        batch_num = 0

        while deleted_count < total_products:
            batch_num += 1
            
            # Fetch a batch of product IDs to delete
            with session_scope() as session:
                # Get IDs for this batch
                product_ids = session.scalars(
                    select(Product.id)
                    .limit(BATCH_SIZE)
                ).all()
                
                if not product_ids:
                    # No more products to delete
                    break
                
                # Delete this batch
                stmt = delete(Product).where(Product.id.in_(product_ids))
                result = session.execute(stmt)
                session.commit()
                
                batch_deleted = result.rowcount
                deleted_count += batch_deleted
                
                # Update database
                repo = ImportRepository(session)
                repo.update_status(
                    UUID(job_id),
                    ImportStatus.IMPORTING,
                    processed_rows=deleted_count,
                )
            
            # Update progress in Redis
            tracker.update(
                status="deleting",
                deleted_count=deleted_count,
                stage=f"batch_{batch_num}",
                force=True,
            )
            
            logger.info(
                f"Job {job_id}: Deleted batch {batch_num} ({batch_deleted} products, "
                f"total: {deleted_count}/{total_products})"
            )

        # Success! Update status to DONE
        with session_scope() as session:
            repo = ImportRepository(session)
            repo.update_status(
                UUID(job_id),
                ImportStatus.DONE,
                processed_rows=deleted_count,
            )
        
        tracker.update(
            status="done",
            deleted_count=deleted_count,
            stage="completed",
            force=True,
        )
        
        logger.info(f"Job {job_id}: Bulk delete completed successfully ({deleted_count} products deleted)")

        # Publish webhook event for bulk delete completion
        try:
            with session_scope() as session:
                from app.services.webhook_service import WebhookService
                webhook_service = WebhookService(session)
                payload = {
                    "job_id": job_id,
                    "status": "done",
                    "deleted_count": deleted_count,
                    "total_products": total_products,
                }
                webhook_service.publish_event("product.bulk_deleted", payload)
        except Exception as webhook_err:
            logger.warning(f"Failed to publish webhook event for product.bulk_deleted: {webhook_err}")

        # Close Redis connection
        redis_client.close()

        return {
            "status": "done",
            "job_id": job_id,
            "deleted_count": deleted_count,
            "total_products": total_products,
        }

    except Retry:
        # This is a Celery retry - re-raise to let Celery handle it
        raise

    except Exception as e:
        # Log error with context
        logger.error(
            f"Job {job_id}: Bulk delete failed on attempt {self.request.retries + 1}: {e}",
            exc_info=True,
        )

        # Update job status to FAILED
        error_message = f"{type(e).__name__}: {str(e)}"
        
        # Only update to FAILED if this is the final retry attempt
        if self.request.retries >= self.max_retries:
            _update_job_failed(job_id, error_message)

        # Update Redis progress
        try:
            tracker.update(
                status="failed" if self.request.retries >= self.max_retries else "deleting",
                deleted_count=deleted_count if 'deleted_count' in locals() else 0,
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
        raise


def _update_job_failed(job_id: str, error_message: str) -> None:
    """Update import job status to FAILED with error message.
    
    Args:
        job_id: Job UUID
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

