"""Server-Sent Events endpoint for real-time import progress tracking."""
from __future__ import annotations

import asyncio
import json
import logging
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.db import get_session
from app.core.redis_manager import ProgressManager, create_redis_client
from app.models.import_job import ImportStatus
from app.services.import_service import ImportService

logger = logging.getLogger(__name__)
settings = get_settings()

router = APIRouter(prefix="/progress", tags=["progress"])


async def get_redis_client() -> Redis:
    """FastAPI dependency that provides a Redis client for progress tracking."""
    redis = create_redis_client(settings.redis_url, decode_responses=True)
    try:
        yield redis
    finally:
        await redis.aclose()


@router.get(
    "/{job_id}",
    summary="Stream import progress via SSE",
    description=(
        "Opens a Server-Sent Events stream that pushes real-time progress updates "
        "for the specified import job. Stream closes automatically when job completes "
        "or fails. Clients should reconnect with exponential backoff if disconnected."
    ),
    responses={
        200: {
            "description": "SSE stream of progress updates",
            "content": {
                "text/event-stream": {
                    "example": 'data: {"status":"importing","stage":"batch_5","progress":45.2}\n\n'
                }
            },
        },
        404: {"description": "Import job not found"},
    },
)
async def stream_progress(
    job_id: UUID,
    session: Session = Depends(get_session),
    redis: Redis = Depends(get_redis_client),
) -> StreamingResponse:
    """
    Stream real-time progress updates for an import job via Server-Sent Events.

    The endpoint:
    1. Validates that the job exists
    2. Subscribes to Redis pub/sub channel for live updates
    3. Falls back to polling Redis hash every 2-3 seconds
    4. Streams JSON progress events to the client
    5. Closes stream when status reaches 'done' or 'failed'
    6. Handles client disconnects gracefully

    Args:
        job_id: UUID of the import job to track
        session: Database session (injected)
        redis: Redis client for pub/sub (injected)

    Returns:
        StreamingResponse with content-type text/event-stream

    Raises:
        HTTPException: 404 if job not found
    """
    # Verify job exists
    import_service = ImportService(session)
    job = import_service.get_job(job_id)

    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Import job not found: {job_id}",
        )

    logger.info(f"SSE client connected for job_id: {job_id}")

    async def event_generator():
        """
        Async generator that yields SSE-formatted progress events.

        Combines Redis pub/sub (for real-time updates) with polling (as fallback)
        to ensure clients always receive progress even if pub/sub messages are missed.
        """
        progress_manager = ProgressManager(redis)
        pubsub = redis.pubsub()
        channel = f"import_progress:channel:{job_id}"

        try:
            # Subscribe to Redis pub/sub channel
            await pubsub.subscribe(channel)
            logger.info(f"Subscribed to Redis channel: {channel}")

            # Send initial progress immediately (if available)
            initial_progress = await progress_manager.get_progress(job_id)
            if initial_progress:
                yield _format_sse_event(initial_progress)
            else:
                # Send initial queued status if no progress yet
                yield _format_sse_event({
                    "job_id": str(job_id),
                    "status": job.status.value,
                    "stage": "queued",
                    "processed_rows": job.processed_rows,
                    "total_rows": job.total_rows,
                    "progress_percent": 0.0,
                })

            # Track terminal status to know when to close stream
            is_terminal = False
            last_poll_time = asyncio.get_event_loop().time()
            poll_interval = 2.5  # seconds

            # Stream updates until job completes
            while not is_terminal:
                try:
                    # Wait for pub/sub message with timeout (non-blocking)
                    message = await asyncio.wait_for(
                        pubsub.get_message(ignore_subscribe_messages=True),
                        timeout=1.0,
                    )

                    if message and message["type"] == "message":
                        # Parse and stream the progress update
                        data = json.loads(message["data"])
                        yield _format_sse_event(data)

                        # Check if job reached terminal state
                        status_value = data.get("status", "")
                        if status_value in (
                            ImportStatus.DONE.value,
                            ImportStatus.FAILED.value,
                        ):
                            logger.info(f"Job {job_id} reached terminal state: {status_value}")
                            is_terminal = True
                            break

                except asyncio.TimeoutError:
                    # No pub/sub message received - fall back to polling
                    current_time = asyncio.get_event_loop().time()
                    if current_time - last_poll_time >= poll_interval:
                        logger.debug(f"Polling progress for job {job_id}")
                        progress = await progress_manager.get_progress(job_id)

                        if progress:
                            yield _format_sse_event(progress)

                            # Check if job reached terminal state
                            status_value = progress.get("status", "")
                            if status_value in (
                                ImportStatus.DONE.value,
                                ImportStatus.FAILED.value,
                            ):
                                logger.info(
                                    f"Job {job_id} reached terminal state (polled): {status_value}"
                                )
                                is_terminal = True
                                break

                        last_poll_time = current_time

                # Yield heartbeat comment to keep connection alive
                # SSE spec: lines starting with ':' are comments and ignored by clients
                if not is_terminal:
                    yield ": heartbeat\n\n"
                    await asyncio.sleep(0.1)  # Small delay to avoid tight loop

            # Send final close event
            logger.info(f"Closing SSE stream for job {job_id}")
            yield _format_sse_event({"event": "close", "job_id": str(job_id)})

        except asyncio.CancelledError:
            logger.info(f"SSE client disconnected for job {job_id}")
            raise

        except Exception as e:
            logger.exception(f"Error in SSE stream for job {job_id}: {e}")
            # Send error event to client
            yield _format_sse_event({
                "event": "error",
                "job_id": str(job_id),
                "message": "Internal server error during progress streaming",
            })
            raise

        finally:
            # Clean up Redis subscription
            try:
                await pubsub.unsubscribe(channel)
                await pubsub.aclose()
                logger.info(f"Cleaned up Redis subscription for job {job_id}")
            except Exception as e:
                logger.error(f"Error cleaning up Redis subscription: {e}")

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",  # Disable nginx buffering for SSE
        },
    )


def _format_sse_event(data: dict) -> str:
    """
    Format a dictionary as a Server-Sent Events message.

    SSE format:
    data: <json>\n\n

    Multiple lines are supported by prefixing each with 'data: '

    Args:
        data: Dictionary to serialize as JSON

    Returns:
        SSE-formatted string ready to yield to client
    """
    json_data = json.dumps(data, default=_json_serializer)
    return f"data: {json_data}\n\n"


def _json_serializer(obj):
    """Custom JSON serializer for types not natively supported."""
    if isinstance(obj, UUID):
        return str(obj)
    raise TypeError(f"Object of type {type(obj)} is not JSON serializable")

