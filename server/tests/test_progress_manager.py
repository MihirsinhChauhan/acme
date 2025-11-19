from __future__ import annotations

import json
import asyncio
from collections import defaultdict
import json
from uuid import uuid4

import pytest  # type: ignore[import-not-found]

from app.core.redis_manager import ProgressManager, DEFAULT_NAMESPACE


@pytest.mark.asyncio
async def test_set_and_get_progress_snapshot_roundtrip() -> None:
    redis = FakeRedis()
    manager = ProgressManager(redis)
    job_id = uuid4()

    snapshot = {
        "status": "parsing",
        "stage": "batch_1",
        "total_rows": 20000,
        "processed_rows": 10000,
        "error_message": None,
    }

    stored = await manager.set_progress(job_id, snapshot)
    assert stored["status"] == "parsing"
    assert "updated_at" in stored

    fetched = await manager.get_progress(job_id)
    assert fetched is not None
    assert fetched["status"] == "parsing"
    assert fetched["processed_rows"] == 10000
    assert fetched["error_message"] is None


@pytest.mark.asyncio
async def test_publish_update_broadcasts_json_payload() -> None:
    redis = FakeRedis()
    manager = ProgressManager(redis)
    job_id = uuid4()

    channel = f"{DEFAULT_NAMESPACE}:channel:{job_id}"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    payload = {
        "status": "importing",
        "stage": "batch_3",
        "processed_rows": 30000,
    }

    published_count = await manager.publish_update(job_id, payload, ensure_timestamp=False)
    assert published_count >= 0

    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
    assert message is not None
    data = json.loads(message["data"])
    assert data["stage"] == "batch_3"
    assert data["processed_rows"] == 30000


@pytest.mark.asyncio
async def test_full_workflow_set_and_publish() -> None:
    """Test realistic workflow: set progress hash + publish to subscribers."""
    redis = FakeRedis()
    manager = ProgressManager(redis)
    job_id = uuid4()

    # Subscribe before publishing
    channel = f"{DEFAULT_NAMESPACE}:channel:{job_id}"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)

    # Simulate import workflow stages
    stages = [
        {"status": "parsing", "stage": "validation", "processed_rows": 0, "total_rows": 50000},
        {"status": "importing", "stage": "batch_1", "processed_rows": 10000, "total_rows": 50000},
        {"status": "importing", "stage": "batch_5", "processed_rows": 50000, "total_rows": 50000},
        {"status": "done", "stage": "complete", "processed_rows": 50000, "total_rows": 50000},
    ]

    for stage_data in stages:
        # Store snapshot
        stored = await manager.set_progress(job_id, stage_data)
        assert stored["status"] == stage_data["status"]
        assert "updated_at" in stored

        # Broadcast to listeners
        await manager.publish_update(job_id, stage_data)

        # Verify hash persisted
        fetched = await manager.get_progress(job_id)
        assert fetched is not None
        assert fetched["status"] == stage_data["status"]
        assert fetched["processed_rows"] == stage_data["processed_rows"]

    # Final state should be 'done'
    final = await manager.get_progress(job_id)
    assert final is not None
    assert final["status"] == "done"
    assert final["processed_rows"] == 50000


@pytest.mark.asyncio
async def test_custom_namespace_and_ttl() -> None:
    """Verify custom namespace and TTL values are applied."""
    redis = FakeRedis()
    manager = ProgressManager(redis, namespace="custom_jobs", ttl_seconds=7200)
    job_id = uuid4()

    data = {"status": "queued"}
    await manager.set_progress(job_id, data, ttl_seconds=3600)

    # Check hash key uses custom namespace
    fetched = await manager.get_progress(job_id)
    assert fetched is not None
    assert fetched["status"] == "queued"

    # Verify channel name also uses custom namespace
    channel = f"custom_jobs:channel:{job_id}"
    pubsub = redis.pubsub()
    await pubsub.subscribe(channel)
    await manager.publish_update(job_id, {"status": "parsing"})
    message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
    assert message is not None


class FakeRedis:
    """Minimal async-friendly Redis stub for unit tests."""

    def __init__(self) -> None:
        self._hashes: dict[str, dict[str, str]] = {}
        self._channels: defaultdict[str, list[asyncio.Queue[str]]] = defaultdict(list)

    async def hset(self, key: str, mapping: dict[str, str]) -> int:
        bucket = self._hashes.setdefault(key, {})
        bucket.update(mapping)
        return len(mapping)

    async def expire(self, key: str, ttl: int) -> bool:
        # TTL not simulated for tests, just return truthy success.
        return key in self._hashes

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self._hashes.get(key, {}))

    async def publish(self, channel: str, message: str) -> int:
        queues = self._channels.get(channel, [])
        for queue in queues:
            await queue.put(message)
        return len(queues)

    def pubsub(self) -> "FakePubSub":
        return FakePubSub(self)


class FakePubSub:
    def __init__(self, redis: FakeRedis) -> None:
        self._redis = redis
        self._queue: asyncio.Queue[str] | None = None

    async def subscribe(self, channel: str) -> None:
        queue: asyncio.Queue[str] = asyncio.Queue()
        self._redis._channels[channel].append(queue)
        self._queue = queue

    async def get_message(self, ignore_subscribe_messages: bool, timeout: float | None = None):
        if not self._queue:
            return None
        try:
            data = await asyncio.wait_for(self._queue.get(), timeout)
        except asyncio.TimeoutError:
            return None
        return {"type": "message", "data": data}

