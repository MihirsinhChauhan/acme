"""Redis progress tracking utilities."""
from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Mapping
from uuid import UUID

from redis.asyncio import Redis, from_url

DEFAULT_PROGRESS_TTL_SECONDS = 60 * 60  # keep hashes for 1 hour after completion
DEFAULT_NAMESPACE = "import_progress"


def create_redis_client(url: str, *, decode_responses: bool = False) -> Redis:
    """Return a configured Redis asyncio client instance."""

    return from_url(
        url,
        encoding="utf-8" if decode_responses else None,
        decode_responses=decode_responses,
        health_check_interval=30,
    )


class ProgressManager:
    """Manages Redis storage + pub/sub fanout for import job progress."""

    def __init__(
        self,
        redis: Redis,
        *,
        namespace: str = DEFAULT_NAMESPACE,
        ttl_seconds: int = DEFAULT_PROGRESS_TTL_SECONDS,
    ) -> None:
        self._redis = redis
        self._namespace = namespace
        self._ttl_seconds = ttl_seconds

    def _hash_key(self, job_id: str | UUID) -> str:
        return f"{self._namespace}:hash:{job_id}"

    def _channel(self, job_id: str | UUID) -> str:
        return f"{self._namespace}:channel:{job_id}"

    async def set_progress(
        self,
        job_id: str | UUID,
        data: Mapping[str, Any],
        *,
        ttl_seconds: int | None = None,
    ) -> Mapping[str, Any]:
        """Persist the latest progress snapshot to a Redis hash."""

        payload = dict(data)
        payload.setdefault("updated_at", datetime.now(timezone.utc).isoformat())
        serialized = {key: self._encode_value(value) for key, value in payload.items()}

        key = self._hash_key(job_id)
        await self._redis.hset(key, mapping=serialized)
        await self._redis.expire(key, ttl_seconds or self._ttl_seconds)
        return payload

    async def get_progress(self, job_id: str | UUID) -> Mapping[str, Any] | None:
        """Return the stored progress state for the given job, if present."""

        raw = await self._redis.hgetall(self._hash_key(job_id))
        if not raw:
            return None
        return {
            self._decode_key(key): self._decode_value(value)
            for key, value in raw.items()
        }

    async def publish_update(
        self,
        job_id: str | UUID,
        data: Mapping[str, Any],
        *,
        ensure_timestamp: bool = True,
    ) -> int:
        """Publish an update message to Redis pub/sub listeners.

        Returns the number of clients that received the message.
        """

        payload = dict(data)
        if ensure_timestamp:
            payload.setdefault("updated_at", datetime.now(timezone.utc).isoformat())

        channel = self._channel(job_id)
        message = json.dumps(payload, default=self._json_default)
        return await self._redis.publish(channel, message)

    def _encode_value(self, value: Any) -> str:
        return json.dumps(value, default=self._json_default)

    def _decode_value(self, value: str | bytes) -> Any:
        if isinstance(value, (bytes, bytearray)):
            value = value.decode("utf-8")
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

    def _decode_key(self, key: str | bytes) -> str:
        if isinstance(key, (bytes, bytearray)):
            return key.decode("utf-8")
        return key

    def _json_default(self, value: Any) -> Any:
        if isinstance(value, datetime):
            return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, UUID):
            return str(value)
        return value


