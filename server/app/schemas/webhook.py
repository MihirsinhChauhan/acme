"""Pydantic schemas for webhook resources."""
from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator


class WebhookBase(BaseModel):
    """Shared attributes for webhook payloads."""

    url: str = Field(description="Webhook URL to receive POST requests")
    events: list[str] = Field(description="List of event types to subscribe to")
    enabled: bool = Field(default=True, description="Whether the webhook is active")

    @field_validator("url")
    @classmethod
    def validate_url(cls, value: str) -> str:
        """Validate that URL is a valid HTTP/HTTPS URL."""
        if not value.startswith(("http://", "https://")):
            raise ValueError("URL must start with http:// or https://")
        return value.strip()

    @field_validator("events")
    @classmethod
    def validate_events(cls, value: list[str]) -> list[str]:
        """Validate that events list is not empty."""
        if not value:
            raise ValueError("Events list cannot be empty")
        return value


class WebhookCreate(WebhookBase):
    """Payload used when creating a webhook."""

    pass


class WebhookUpdate(BaseModel):
    """Payload used when updating a webhook (all fields optional)."""

    url: str | None = Field(default=None, description="Webhook URL to receive POST requests")
    events: list[str] | None = Field(default=None, description="List of event types to subscribe to")
    enabled: bool | None = Field(default=None, description="Whether the webhook is active")

    @field_validator("url", mode="before")
    @classmethod
    def validate_url(cls, value: str | None) -> str | None:
        """Validate that URL is a valid HTTP/HTTPS URL."""
        if value is not None:
            if not value.startswith(("http://", "https://")):
                raise ValueError("URL must start with http:// or https://")
            return value.strip()
        return value

    @field_validator("events")
    @classmethod
    def validate_events(cls, value: list[str] | None) -> list[str] | None:
        """Validate that events list is not empty if provided."""
        if value is not None and not value:
            raise ValueError("Events list cannot be empty")
        return value


class WebhookResponse(WebhookBase):
    """Response model returned by API endpoints."""

    id: int = Field(description="Database identifier")
    created_at: datetime = Field(description="Timestamp when the webhook was created")
    updated_at: datetime = Field(description="Timestamp when the webhook was last updated")

    model_config = ConfigDict(from_attributes=True)


class WebhookTestResponse(BaseModel):
    """Response model for webhook test endpoint."""

    success: bool = Field(description="Whether the webhook call succeeded")
    response_code: int | None = Field(description="HTTP status code from webhook endpoint")
    response_time_ms: int | None = Field(description="Response time in milliseconds")
    response_body: str | None = Field(description="Response body (truncated to 1000 chars)")
    error: str | None = Field(default=None, description="Error message if call failed")

    model_config = ConfigDict(from_attributes=True)


class WebhookDeliveryResponse(BaseModel):
    """Response model for webhook delivery history."""

    id: int = Field(description="Database identifier")
    webhook_id: int = Field(description="Associated webhook ID")
    event_type: str = Field(description="Event type that triggered this delivery")
    status: str = Field(description="Delivery status (pending, success, failed)")
    response_code: int | None = Field(description="HTTP status code from webhook endpoint")
    response_time_ms: int | None = Field(description="Response time in milliseconds")
    attempted_at: datetime = Field(description="When the delivery was attempted")
    completed_at: datetime | None = Field(description="When the delivery completed")

    model_config = ConfigDict(from_attributes=True)

