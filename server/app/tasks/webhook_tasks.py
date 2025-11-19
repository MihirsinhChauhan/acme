"""Celery tasks for webhook delivery."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from celery.exceptions import Retry

from app.core.config import get_settings
from app.core.db import session_scope
from app.models.webhook_delivery import WebhookDelivery, WebhookDeliveryStatus
from app.services.webhook_repository import WebhookRepository
from app.tasks.celery_app import celery_app

logger = logging.getLogger(__name__)

# Constants
WEBHOOK_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BODY_LENGTH = 1000


@celery_app.task(
    name="deliver_webhook",
    bind=True,
    acks_late=True,
    reject_on_worker_lost=True,
    autoretry_for=(Exception,),
    retry_kwargs={"max_retries": 3},
    retry_backoff=True,
    retry_backoff_max=60,
)
def deliver_webhook_task(
    self,
    webhook_id: int,
    event_type: str,
    payload: dict[str, Any],
) -> dict:
    """Deliver a webhook event to a configured webhook URL.
    
    Task Flow:
    1. Fetch webhook configuration from database
    2. Create pending delivery log entry
    3. Make HTTP POST request to webhook URL with JSON payload
    4. Record response details (status code, body, response time)
    5. Update delivery log with success/failure status
    
    Args:
        webhook_id: Database ID of the webhook configuration
        event_type: Event type that triggered this delivery
        payload: JSON payload to send to webhook
        
    Returns:
        dict with delivery status and details
        
    Raises:
        Exception: Any error during delivery (will trigger retry via autoretry_for)
    """
    settings = get_settings()
    
    logger.info(
        f"Starting webhook delivery task for webhook {webhook_id} (event: {event_type}, "
        f"attempt {self.request.retries + 1}/{self.max_retries + 1})"
    )
    
    delivery_id: int | None = None
    
    try:
        # Step 1: Fetch webhook from database
        with session_scope() as session:
            repo = WebhookRepository(session)
            webhook = repo.get_by_id(webhook_id)
            
            if not webhook:
                error_msg = f"Webhook {webhook_id} not found in database"
                logger.error(error_msg)
                return {"status": "failed", "error": error_msg}
            
            # Check if webhook is still enabled
            if not webhook.enabled:
                logger.info(f"Webhook {webhook_id} is disabled, skipping delivery")
                return {"status": "skipped", "reason": "webhook_disabled"}
            
            # Step 2: Create pending delivery log entry
            delivery = repo.create_delivery_log(
                webhook_id=webhook_id,
                event_type=event_type,
                payload=payload,
                status=WebhookDeliveryStatus.PENDING,
            )
            delivery_id = delivery.id
            logger.debug(f"Created delivery log entry {delivery_id} for webhook {webhook_id}")
        
        # Step 3: Make HTTP POST request to webhook URL
        start_time = time.time()
        response_code: int | None = None
        response_body: str | None = None
        response_time_ms: int | None = None
        
        try:
            with httpx.Client(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
                response = client.post(
                    webhook.url,
                    json=payload,
                    headers={"Content-Type": "application/json"},
                )
                
                response_code = response.status_code
                response_time_ms = int((time.time() - start_time) * 1000)
                
                # Read response body (truncate if too long)
                try:
                    body_text = response.text
                    if len(body_text) > MAX_RESPONSE_BODY_LENGTH:
                        response_body = body_text[:MAX_RESPONSE_BODY_LENGTH] + "... (truncated)"
                    else:
                        response_body = body_text
                except Exception as e:
                    logger.warning(f"Failed to read response body: {e}")
                    response_body = None
                
                # Consider 2xx status codes as success
                is_success = 200 <= response_code < 300
                
                if is_success:
                    logger.info(
                        f"Webhook {webhook_id} delivered successfully "
                        f"(status: {response_code}, time: {response_time_ms}ms)"
                    )
                else:
                    logger.warning(
                        f"Webhook {webhook_id} returned non-2xx status "
                        f"(status: {response_code}, time: {response_time_ms}ms)"
                    )
        
        except httpx.TimeoutException as e:
            error_msg = f"Webhook request timed out after {WEBHOOK_TIMEOUT_SECONDS}s"
            logger.error(f"Webhook {webhook_id} delivery failed: {error_msg}")
            response_time_ms = int((time.time() - start_time) * 1000)
            is_success = False
            response_body = str(e)[:MAX_RESPONSE_BODY_LENGTH]
        
        except httpx.RequestError as e:
            error_msg = f"Webhook request failed: {str(e)}"
            logger.error(f"Webhook {webhook_id} delivery failed: {error_msg}")
            response_time_ms = int((time.time() - start_time) * 1000) if start_time else None
            is_success = False
            response_body = str(e)[:MAX_RESPONSE_BODY_LENGTH]
        
        except Exception as e:
            error_msg = f"Unexpected error during webhook delivery: {str(e)}"
            logger.error(f"Webhook {webhook_id} delivery failed: {error_msg}", exc_info=True)
            response_time_ms = int((time.time() - start_time) * 1000) if start_time else None
            is_success = False
            response_body = str(e)[:MAX_RESPONSE_BODY_LENGTH]
        
        # Step 4: Update delivery log with results
        final_status = WebhookDeliveryStatus.SUCCESS if is_success else WebhookDeliveryStatus.FAILED
        
        with session_scope() as session:
            repo = WebhookRepository(session)
            # We need to update the existing delivery record
            delivery = session.get(WebhookDelivery, delivery_id)
            if delivery:
                delivery.status = final_status
                delivery.response_code = response_code
                delivery.response_body = response_body
                delivery.response_time_ms = response_time_ms
                from datetime import datetime, timezone
                delivery.completed_at = datetime.now(timezone.utc)
                session.commit()
                logger.debug(f"Updated delivery log entry {delivery_id} with status: {final_status}")
        
        return {
            "status": final_status,
            "webhook_id": webhook_id,
            "event_type": event_type,
            "response_code": response_code,
            "response_time_ms": response_time_ms,
        }
    
    except Retry:
        # This is a Celery retry - re-raise to let Celery handle it
        raise
    
    except Exception as e:
        # Log error with context
        logger.error(
            f"Webhook {webhook_id} delivery failed on attempt {self.request.retries + 1}: {e}",
            exc_info=True,
        )
        
        # Update delivery log to failed status if we created one
        if delivery_id:
            try:
                with session_scope() as session:
                    repo = WebhookRepository(session)
                    delivery = session.get(WebhookDelivery, delivery_id)
                    if delivery:
                        delivery.status = WebhookDeliveryStatus.FAILED
                        delivery.response_body = str(e)[:MAX_RESPONSE_BODY_LENGTH]
                        from datetime import datetime, timezone
                        delivery.completed_at = datetime.now(timezone.utc)
                        session.commit()
            except Exception as update_err:
                logger.warning(f"Failed to update delivery log {delivery_id}: {update_err}")
        
        # Re-raise exception to trigger Celery retry mechanism
        raise

