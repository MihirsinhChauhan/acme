"""Webhook configuration and management API endpoints."""
from __future__ import annotations

import logging
import time
from typing import Any

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.db import get_session
from app.schemas.webhook import (
    WebhookCreate,
    WebhookDeliveryResponse,
    WebhookResponse,
    WebhookTestResponse,
    WebhookUpdate,
)
from app.services.webhook_repository import WebhookRepository

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])

# Constants
WEBHOOK_TIMEOUT_SECONDS = 10
MAX_RESPONSE_BODY_LENGTH = 1000


def get_webhook_repository(session: Session = Depends(get_session)) -> WebhookRepository:
    """Dependency to get WebhookRepository instance."""
    return WebhookRepository(session)


@router.get(
    "",
    response_model=list[WebhookResponse],
    status_code=status.HTTP_200_OK,
    summary="List all webhooks",
    description="Retrieve a list of all configured webhooks.",
)
async def list_webhooks(
    repository: WebhookRepository = Depends(get_webhook_repository),
) -> list[WebhookResponse]:
    """
    List all webhooks.

    Args:
        repository: WebhookRepository instance (injected)

    Returns:
        List of WebhookResponse
    """
    webhooks = repository.get_all()
    return [WebhookResponse.model_validate(w) for w in webhooks]


@router.post(
    "",
    response_model=WebhookResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new webhook",
    description="Create a new webhook configuration with URL, events, and enabled status.",
)
async def create_webhook(
    webhook: WebhookCreate,
    repository: WebhookRepository = Depends(get_webhook_repository),
) -> WebhookResponse:
    """
    Create a new webhook.

    Args:
        webhook: WebhookCreate schema with webhook data
        repository: WebhookRepository instance (injected)

    Returns:
        Created WebhookResponse
    """
    try:
        created_webhook = repository.create(webhook)
        return WebhookResponse.model_validate(created_webhook)
    except Exception as e:
        logger.exception(f"Unexpected error creating webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create webhook",
        ) from e


@router.get(
    "/{webhook_id}",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Get webhook by ID",
    description="Retrieve a single webhook by its database ID.",
)
async def get_webhook(
    webhook_id: int,
    repository: WebhookRepository = Depends(get_webhook_repository),
) -> WebhookResponse:
    """
    Get a webhook by ID.

    Args:
        webhook_id: Database identifier
        repository: WebhookRepository instance (injected)

    Returns:
        WebhookResponse

    Raises:
        HTTPException: 404 if webhook not found
    """
    webhook = repository.get_by_id(webhook_id)
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found",
        )
    return WebhookResponse.model_validate(webhook)


@router.put(
    "/{webhook_id}",
    response_model=WebhookResponse,
    status_code=status.HTTP_200_OK,
    summary="Update a webhook",
    description="Update a webhook by ID. All fields in WebhookUpdate are optional.",
)
async def update_webhook(
    webhook_id: int,
    webhook: WebhookUpdate,
    repository: WebhookRepository = Depends(get_webhook_repository),
) -> WebhookResponse:
    """
    Update a webhook by ID.

    Args:
        webhook_id: Database identifier
        webhook: WebhookUpdate schema with fields to update
        repository: WebhookRepository instance (injected)

    Returns:
        Updated WebhookResponse

    Raises:
        HTTPException: 404 if webhook not found
    """
    try:
        updated_webhook = repository.update(webhook_id, webhook)
        if updated_webhook is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Webhook with ID {webhook_id} not found",
            )
        return WebhookResponse.model_validate(updated_webhook)
    except HTTPException:
        raise
    except Exception as e:
        logger.exception(f"Unexpected error updating webhook {webhook_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update webhook",
        ) from e


@router.delete(
    "/{webhook_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a webhook by ID",
    description="Delete a webhook by its database ID. Returns 204 No Content on success.",
)
async def delete_webhook(
    webhook_id: int,
    repository: WebhookRepository = Depends(get_webhook_repository),
) -> None:
    """
    Delete a webhook by ID.

    Args:
        webhook_id: Database identifier
        repository: WebhookRepository instance (injected)

    Raises:
        HTTPException: 404 if webhook not found
    """
    deleted = repository.delete(webhook_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found",
        )


@router.post(
    "/{webhook_id}/test",
    response_model=WebhookTestResponse,
    status_code=status.HTTP_200_OK,
    summary="Test a webhook",
    description=(
        "Send a test event to the webhook URL synchronously. "
        "Returns the response code, response time, and response body (truncated)."
    ),
)
async def test_webhook(
    webhook_id: int,
    repository: WebhookRepository = Depends(get_webhook_repository),
) -> WebhookTestResponse:
    """
    Test a webhook by sending a test event synchronously.

    Args:
        webhook_id: Database identifier
        repository: WebhookRepository instance (injected)

    Returns:
        WebhookTestResponse with delivery details

    Raises:
        HTTPException: 404 if webhook not found
    """
    webhook = repository.get_by_id(webhook_id)
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found",
        )
    
    # Create test payload
    test_payload: dict[str, Any] = {
        "event": "webhook.test",
        "webhook_id": webhook_id,
        "message": "This is a test webhook event",
        "timestamp": time.time(),
    }
    
    # Make asynchronous HTTP request
    start_time = time.time()
    response_code: int | None = None
    response_body: str | None = None
    response_time_ms: int | None = None
    error: str | None = None
    is_success = False
    
    try:
        async with httpx.AsyncClient(timeout=WEBHOOK_TIMEOUT_SECONDS) as client:
            response = await client.post(
                webhook.url,
                json=test_payload,
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
            
            is_success = 200 <= response_code < 300
    
    except httpx.TimeoutException as e:
        error = f"Webhook request timed out after {WEBHOOK_TIMEOUT_SECONDS}s"
        response_time_ms = int((time.time() - start_time) * 1000) if start_time else None
        is_success = False
        response_body = str(e)[:MAX_RESPONSE_BODY_LENGTH]
    
    except httpx.RequestError as e:
        error = f"Webhook request failed: {str(e)}"
        response_time_ms = int((time.time() - start_time) * 1000) if start_time else None
        is_success = False
        response_body = str(e)[:MAX_RESPONSE_BODY_LENGTH]
    
    except Exception as e:
        error = f"Unexpected error during webhook test: {str(e)}"
        response_time_ms = int((time.time() - start_time) * 1000) if start_time else None
        is_success = False
        response_body = str(e)[:MAX_RESPONSE_BODY_LENGTH]
        logger.exception(f"Error testing webhook {webhook_id}: {e}")
    
    return WebhookTestResponse(
        success=is_success,
        response_code=response_code,
        response_time_ms=response_time_ms,
        response_body=response_body,
        error=error,
    )


@router.get(
    "/{webhook_id}/deliveries",
    response_model=list[WebhookDeliveryResponse],
    status_code=status.HTTP_200_OK,
    summary="Get webhook delivery history",
    description="Retrieve delivery history for a webhook with pagination.",
)
async def get_webhook_deliveries(
    webhook_id: int,
    page: int = Query(default=1, ge=1, description="Page number (1-indexed)"),
    page_size: int = Query(default=50, ge=1, le=100, description="Items per page (max 100)"),
    repository: WebhookRepository = Depends(get_webhook_repository),
) -> list[WebhookDeliveryResponse]:
    """
    Get delivery history for a webhook.

    Args:
        webhook_id: Database identifier
        page: Page number (default: 1)
        page_size: Items per page (default: 50, max: 100)
        repository: WebhookRepository instance (injected)

    Returns:
        List of WebhookDeliveryResponse

    Raises:
        HTTPException: 404 if webhook not found
    """
    # Verify webhook exists
    webhook = repository.get_by_id(webhook_id)
    if webhook is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Webhook with ID {webhook_id} not found",
        )
    
    offset = (page - 1) * page_size
    deliveries, total = repository.get_deliveries_for_webhook(webhook_id, limit=page_size, offset=offset)
    
    return [WebhookDeliveryResponse.model_validate(d) for d in deliveries]

