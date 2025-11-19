"""Webhook repository for database operations."""
from __future__ import annotations

from typing import Sequence

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.webhook import Webhook
from app.models.webhook_delivery import WebhookDelivery
from app.schemas.webhook import WebhookCreate, WebhookUpdate


class WebhookRepository:
    """Handles database operations for Webhook entities."""

    def __init__(self, session: Session) -> None:
        """Initialize repository with a SQLAlchemy session.
        
        Args:
            session: Active database session for executing queries
        """
        self._session = session

    def create(self, webhook: WebhookCreate) -> Webhook:
        """Create a new webhook.
        
        Args:
            webhook: WebhookCreate schema with webhook data
            
        Returns:
            Created Webhook instance
        """
        db_webhook = Webhook(
            url=webhook.url,
            events=webhook.events,
            enabled=webhook.enabled,
        )
        self._session.add(db_webhook)
        self._session.commit()
        self._session.refresh(db_webhook)
        return db_webhook

    def get_by_id(self, webhook_id: int) -> Webhook | None:
        """Fetch a webhook by its database ID.
        
        Args:
            webhook_id: Database identifier
            
        Returns:
            Webhook instance if found, None otherwise
        """
        return self._session.get(Webhook, webhook_id)

    def get_all(self) -> Sequence[Webhook]:
        """Fetch all webhooks.
        
        Returns:
            Sequence of Webhook instances
        """
        return self._session.query(Webhook).order_by(Webhook.created_at.desc()).all()

    def update(self, webhook_id: int, webhook: WebhookUpdate) -> Webhook | None:
        """Update a webhook by ID.
        
        Args:
            webhook_id: Database identifier
            webhook: WebhookUpdate schema with fields to update
            
        Returns:
            Updated Webhook instance if found, None otherwise
        """
        db_webhook = self.get_by_id(webhook_id)
        if db_webhook is None:
            return None
        
        # Update only provided fields
        if webhook.url is not None:
            db_webhook.url = webhook.url
        if webhook.events is not None:
            db_webhook.events = webhook.events
        if webhook.enabled is not None:
            db_webhook.enabled = webhook.enabled
        
        self._session.commit()
        self._session.refresh(db_webhook)
        return db_webhook

    def delete(self, webhook_id: int) -> bool:
        """Delete a webhook by ID.
        
        Args:
            webhook_id: Database identifier
            
        Returns:
            True if webhook was deleted, False if not found
        """
        db_webhook = self.get_by_id(webhook_id)
        if db_webhook is None:
            return False
        
        self._session.delete(db_webhook)
        self._session.commit()
        return True

    def get_enabled_webhooks_for_event(self, event_type: str) -> Sequence[Webhook]:
        """Get all enabled webhooks that subscribe to a specific event type.
        
        Args:
            event_type: Event type to filter by (e.g., "product.created")
            
        Returns:
            Sequence of enabled Webhook instances that subscribe to this event
        """
        # Fetch all enabled webhooks and filter in Python
        # This is simpler and more reliable than JSON array queries
        # For production with many webhooks, consider using raw SQL with JSONB operators
        all_webhooks = (
            self._session.query(Webhook)
            .filter(Webhook.enabled == True)
            .all()
        )
        
        # Filter webhooks that have this event type in their events list
        return [wh for wh in all_webhooks if event_type in wh.events]

    def create_delivery_log(
        self,
        webhook_id: int,
        event_type: str,
        payload: dict,
        status: str,
        response_code: int | None = None,
        response_body: str | None = None,
        response_time_ms: int | None = None,
    ) -> WebhookDelivery:
        """Create a delivery log entry for a webhook attempt.
        
        Args:
            webhook_id: Associated webhook ID
            event_type: Event type that triggered this delivery
            payload: JSON payload that was sent
            status: Delivery status (pending, success, failed)
            response_code: HTTP status code from webhook endpoint
            response_body: Response body from webhook endpoint
            response_time_ms: Response time in milliseconds
            
        Returns:
            Created WebhookDelivery instance
        """
        from datetime import datetime, timezone
        
        delivery = WebhookDelivery(
            webhook_id=webhook_id,
            event_type=event_type,
            payload=payload,
            status=status,
            response_code=response_code,
            response_body=response_body,
            response_time_ms=response_time_ms,
        )
        
        if status != "pending":
            delivery.completed_at = datetime.now(timezone.utc)
        
        self._session.add(delivery)
        self._session.commit()
        self._session.refresh(delivery)
        return delivery

    def get_deliveries_for_webhook(
        self, webhook_id: int, limit: int = 50, offset: int = 0
    ) -> tuple[Sequence[WebhookDelivery], int]:
        """Get delivery history for a webhook with pagination.
        
        Args:
            webhook_id: Webhook ID to get deliveries for
            limit: Maximum number of deliveries to return
            offset: Number of deliveries to skip
            
        Returns:
            Tuple of (deliveries sequence, total count)
        """
        query = (
            self._session.query(WebhookDelivery)
            .filter(WebhookDelivery.webhook_id == webhook_id)
            .order_by(WebhookDelivery.attempted_at.desc())
        )
        
        total = query.count()
        deliveries = query.limit(limit).offset(offset).all()
        
        return deliveries, total

