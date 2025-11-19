# Redis ProgressManager - Usage Guide

## Quick Start

```python
from app.core import ProgressManager, create_redis_client
from uuid import uuid4

# Initialize (typically done once at app startup)
redis_client = create_redis_client("redis://localhost:6379/0")
progress = ProgressManager(redis_client)

# In your Celery task
job_id = uuid4()

# Store progress snapshot
await progress.set_progress(job_id, {
    "status": "importing",
    "stage": "batch_5",
    "total_rows": 100000,
    "processed_rows": 50000,
    "error_message": None
})

# Notify SSE listeners (real-time push)
await progress.publish_update(job_id, {
    "status": "importing",
    "processed_rows": 50000
})
```

## API Reference

### `create_redis_client(url, decode_responses=False)`
Factory function to create a configured Redis asyncio client.

**Parameters:**
- `url` (str): Redis connection URL (e.g., `redis://localhost:6379/0`)
- `decode_responses` (bool): Auto-decode bytes to strings (default: False)

**Returns:** `Redis` instance with health checks enabled

---

### `ProgressManager(redis, namespace="import_progress", ttl_seconds=3600)`

#### `set_progress(job_id, data, ttl_seconds=None)`
Persist the latest progress snapshot to Redis hash.

**Parameters:**
- `job_id` (UUID | str): Job identifier
- `data` (dict): Progress payload (will be JSON-encoded)
- `ttl_seconds` (int, optional): Override default TTL

**Returns:** dict with `updated_at` timestamp added

**Example:**
```python
stored = await progress.set_progress(job_id, {
    "status": "parsing",
    "total_rows": 50000,
    "processed_rows": 0
})
# Returns: {"status": "parsing", ..., "updated_at": "2025-11-19T14:30:00+00:00"}
```

---

#### `get_progress(job_id)`
Retrieve stored progress state.

**Parameters:**
- `job_id` (UUID | str): Job identifier

**Returns:** dict | None (None if job not found or expired)

**Example:**
```python
state = await progress.get_progress(job_id)
if state:
    print(f"Status: {state['status']}, Progress: {state['processed_rows']}")
```

---

#### `publish_update(job_id, data, ensure_timestamp=True)`
Broadcast update to Redis pub/sub subscribers (SSE clients).

**Parameters:**
- `job_id` (UUID | str): Job identifier
- `data` (dict): Update payload
- `ensure_timestamp` (bool): Auto-add `updated_at` (default: True)

**Returns:** int (number of subscribers that received the message)

**Example:**
```python
subscribers = await progress.publish_update(job_id, {
    "status": "importing",
    "stage": "batch_10",
    "processed_rows": 100000
})
print(f"Notified {subscribers} SSE clients")
```

---

## Common Patterns

### Pattern 1: Celery Task Progress Tracking

```python
from celery import Task
from app.core import ProgressManager, create_redis_client

redis = create_redis_client(settings.redis_url)
progress = ProgressManager(redis)

@celery_app.task(bind=True)
def process_csv_import(self, job_id: str, file_path: str) -> None:
    total_rows = count_csv_rows(file_path)
    
    # Initial state
    await progress.set_progress(job_id, {
        "status": "parsing",
        "total_rows": total_rows,
        "processed_rows": 0
    })
    await progress.publish_update(job_id, {"status": "parsing"})
    
    # Process batches
    for batch_num, batch in enumerate(read_csv_batches(file_path, 10000)):
        insert_batch(batch)
        processed = (batch_num + 1) * 10000
        
        # Update every batch
        await progress.set_progress(job_id, {
            "status": "importing",
            "stage": f"batch_{batch_num + 1}",
            "processed_rows": min(processed, total_rows),
            "total_rows": total_rows
        })
        await progress.publish_update(job_id, {
            "processed_rows": processed
        })
    
    # Complete
    await progress.set_progress(job_id, {
        "status": "done",
        "processed_rows": total_rows,
        "total_rows": total_rows
    })
    await progress.publish_update(job_id, {"status": "done"})
```

### Pattern 2: SSE Progress Streaming

```python
from fastapi import APIRouter
from sse_starlette.sse import EventSourceResponse
import json

router = APIRouter()

@router.get("/progress/{job_id}")
async def stream_progress(job_id: UUID):
    async def event_generator():
        # Send current state immediately
        current = await progress.get_progress(job_id)
        if current:
            yield {"data": json.dumps(current)}
        
        # Subscribe to real-time updates
        pubsub = redis.pubsub()
        channel = f"import_progress:channel:{job_id}"
        await pubsub.subscribe(channel)
        
        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield {"data": message["data"]}
                    
                    # Check if done
                    data = json.loads(message["data"])
                    if data.get("status") in ("done", "failed"):
                        break
        finally:
            await pubsub.unsubscribe(channel)
    
    return EventSourceResponse(event_generator())
```

### Pattern 3: Error Handling

```python
try:
    # ... batch processing ...
    pass
except Exception as e:
    # Store error state
    await progress.set_progress(job_id, {
        "status": "failed",
        "error_message": str(e),
        "processed_rows": last_processed_count,
        "total_rows": total_rows
    })
    await progress.publish_update(job_id, {
        "status": "failed",
        "error_message": str(e)
    })
    raise
```

---

## Redis Key Structure

### Hash Keys (Persistent State)
Format: `import_progress:hash:{job_id}`

Example:
```
import_progress:hash:550e8400-e29b-41d4-a716-446655440000
  ├─ status: "importing"
  ├─ stage: "batch_5"
  ├─ total_rows: 100000
  ├─ processed_rows: 50000
  ├─ error_message: null
  └─ updated_at: "2025-11-19T14:30:00+00:00"
```

### Pub/Sub Channels (Real-time)
Format: `import_progress:channel:{job_id}`

Subscribers receive JSON messages:
```json
{
  "status": "importing",
  "stage": "batch_5",
  "processed_rows": 50000,
  "updated_at": "2025-11-19T14:30:00+00:00"
}
```

---

## Configuration

### Environment Variables

```bash
# .env
REDIS_URL=redis://localhost:6379/0
```

### Custom Namespace

```python
# Separate different import types
product_progress = ProgressManager(redis, namespace="product_imports")
order_progress = ProgressManager(redis, namespace="order_imports")
```

### Custom TTL

```python
# Keep completed jobs for 24 hours
progress = ProgressManager(redis, ttl_seconds=86400)

# Or per-job override
await progress.set_progress(job_id, data, ttl_seconds=7200)
```

---

## Performance Notes

- **Hash operations**: ~1ms latency (local Redis)
- **Pub/sub**: ~2-5ms latency (depends on subscriber count)
- **Memory**: ~200-500 bytes per job
- **Recommended update frequency**: Every 10k rows or 2-3 seconds

For 100k row imports with 10k batches:
- 20 Redis operations total (10 set_progress + 10 publish_update)
- ~30-50ms total Redis overhead
- Negligible impact on import performance

