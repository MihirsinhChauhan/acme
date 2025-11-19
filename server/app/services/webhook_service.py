"""Webhook service for event publishing and delivery coordination."""
from __future__ import annotations

import logging
from typing import Any

from sqlalchemy.orm import Session

from app.services.webhook_repository import WebhookRepository
from app.tasks.webhook_tasks import deliver_webhook_task

logger = logging.getLogger(__name__)


class WebhookService:
    """Service for publishing events to webhooks."""

    def __init__(self, session: Session) -> None:
        """Initialize webhook service with a database session.
        
        Args:
            session: Active database session
        """
        self._session = session
        self._repository = WebhookRepository(session)

    def publish_event(self, event_type: str, payload: dict[str, Any]) -> None:
        """Publish an event to all enabled webhooks that subscribe to it.
        
        This method:
        1. Queries for enabled webhooks that subscribe to the event type
        2. Enqueues a Celery task for each webhook to deliver the event asynchronously
        
        Args:
            event_type: Event type (e.g., "product.created", "import.completed")
            payload: Event payload dictionary to send to webhooks
        """
        try:
            # Get all enabled webhooks for this event type
            webhooks = self._repository.get_enabled_webhooks_for_event(event_type)
            
            if not webhooks:
                logger.debug(f"No enabled webhooks found for event type: {event_type}")
                return
            
            logger.info(f"Publishing event '{event_type}' to {len(webhooks)} webhook(s)")
            
            # Enqueue delivery task for each webhook
            for webhook in webhooks:
                try:
                    deliver_webhook_task.delay(
                        webhook_id=webhook.id,
                        event_type=event_type,
                        payload=payload,
                    )
                    logger.debug(f"Enqueued webhook delivery task for webhook {webhook.id} (event: {event_type})")
                except Exception as e:
                    logger.error(
                        f"Failed to enqueue webhook delivery task for webhook {webhook.id}: {e}",
                        exc_info=True,
                    )
                    # Continue with other webhooks even if one fails
        
        except Exception as e:
            logger.error(f"Error publishing event '{event_type}': {e}", exc_info=True)
            # Don't raise - webhook failures shouldn't break the main operation

