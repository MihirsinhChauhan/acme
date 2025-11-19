# RabbitMQ Task Queue Configuration

## Overview

Phase 4 implements a robust RabbitMQ-based task queue system with Celery for reliable CSV import processing. This configuration ensures:

- **Reliability**: Manual ACK strategy ensures tasks are only removed after successful completion
- **Fault Tolerance**: Dead Letter Queues (DLQ) for failed tasks, automatic retries with exponential backoff
- **Performance**: Optimized for I/O-bound CSV processing with proper worker concurrency
- **Monitoring**: Full event tracking for observability

## Architecture

```
Upload → FastAPI → RabbitMQ (import_queue) → Celery Worker → PostgreSQL
                                          ↓
                                     Redis (progress)
                                          ↓
                                    SSE Stream
```

## Queue Structure

### 1. **import_queue** (Primary)
- **Purpose**: CSV import processing tasks
- **Exchange**: `import_tasks` (direct, durable)
- **Routing Key**: `import.csv`
- **Properties**:
  - 2-hour message TTL (long-running imports)
  - Priority support (0-10)
  - Dead letter routing to `failed_tasks` queue
  - Durable (survives broker restarts)

### 2. **bulk_ops_queue** (Future Use)
- **Purpose**: Bulk database operations
- **Exchange**: `import_tasks` (direct, durable)
- **Routing Key**: `bulk.operations`
- **Properties**:
  - 1-hour message TTL
  - Priority support (0-5)
  - Dead letter routing

### 3. **default** (Fallback)
- **Purpose**: General-purpose tasks
- **Exchange**: `default` (direct, durable)
- **Routing Key**: `default`

### 4. **failed_tasks** (Dead Letter Queue)
- **Purpose**: Store tasks that exceeded retry limits
- **Exchange**: `dlx` (direct, durable)
- **Routing Key**: `*.failed`
- **Properties**:
  - 7-day retention
  - Manual inspection and reprocessing

## Task Delivery Flow

### 1. Enqueue Phase
```python
# FastAPI endpoint enqueues task
from app.tasks.import_tasks import process_csv_import
result = process_csv_import.apply_async(
    args=[job_id, file_path],
    priority=5
)
```

### 2. Delivery Phase
1. RabbitMQ delivers message to worker
2. Worker **reserves** message (not ACK yet)
3. Worker begins task execution
4. Worker processes CSV in batches

### 3. Completion Phase

**Success:**
```python
# Worker finishes successfully
# → Celery sends ACK to RabbitMQ
# → Message removed from queue
```

**Failure:**
```python
# Worker encounters error
# → Celery sends NACK with requeue=True (if retries remain)
# → RabbitMQ requeues message with delay
# → OR sends to DLQ if max retries exceeded
```

## Retry Strategy

### Exponential Backoff
```
Attempt 1: Original execution
Attempt 2: 2^1 = 2 seconds delay
Attempt 3: 2^2 = 4 seconds delay  
Attempt 4: 2^3 = 8 seconds delay
After 3 retries → DLQ
```

### Configuration
```python
task_acks_late = True                    # ACK after completion
task_reject_on_worker_lost = True        # Requeue if worker crashes
worker_prefetch_multiplier = 1           # Fair distribution
task_max_retries = 3                     # Max retry attempts
task_retry_backoff = True                # Enable exponential backoff
task_retry_jitter = True                 # Add randomness
```

## Worker Configuration

### Concurrency Settings
```bash
celery -A app.tasks.celery_app.celery_app worker \
  --loglevel=info \
  --concurrency=4 \                      # 4 concurrent tasks
  --max-tasks-per-child=1000 \           # Prevent memory leaks
  -Q import_queue,bulk_ops_queue,default # Subscribe to queues
```

### Environment Variables
```bash
CELERY_BROKER_URL=pyamqp://guest:guest@rabbitmq:5672//
CELERY_RESULT_BACKEND=redis://redis:6379/1
CELERY_WORKER_CONCURRENCY=4
CELERY_WORKER_PREFETCH_MULTIPLIER=1
```

## Task-Specific Settings

### CSV Import Task
```python
task_annotations = {
    "app.tasks.import_tasks.process_csv_import": {
        "rate_limit": "10/m",           # Max 10 imports/minute
        "time_limit": 3600,             # Hard limit: 1 hour
        "soft_time_limit": 3300,        # Soft limit: 55 minutes
        "max_retries": 3,
        "default_retry_delay": 30,
    }
}
```

- **Rate Limit**: Prevents system overload
- **Hard Time Limit**: Kills task after 1 hour
- **Soft Time Limit**: Raises `SoftTimeLimitExceeded` at 55 minutes (allows cleanup)

## Monitoring & Health Checks

### Worker Health Check
```bash
# Docker healthcheck
celery -A app.tasks.celery_app.celery_app inspect ping

# Expected output:
# -> celery@worker: OK pong
```

### RabbitMQ Health Check
```bash
# Docker healthcheck
rabbitmq-diagnostics check_port_connectivity

# Management UI: http://localhost:15672
# Username: guest
# Password: guest
```

### Queue Monitoring
Access RabbitMQ Management UI to monitor:
- **Queue Depth**: Number of pending messages
- **Consumer Count**: Active workers
- **Message Rates**: In/out throughput
- **Failed Tasks**: Messages in DLQ

## Development Usage

### Start Services
```bash
cd server
docker compose up -d postgres redis rabbitmq
```

### Run Worker Locally
```bash
celery -A app.tasks.celery_app.celery_app worker \
  --loglevel=debug \
  --concurrency=2 \
  -Q import_queue,default
```

### Run API Server
```bash
uvicorn app.main:app --reload
```

### Test Task Enqueue
```python
from app.tasks.celery_app import celery_app

# Send test task
result = celery_app.send_task(
    "app.tasks.import_tasks.process_csv_import",
    args=["test-job-id", "/path/to/file.csv"],
    queue="import_queue",
    priority=5
)

# Check status
print(result.ready())  # False if pending/running
print(result.status)   # PENDING, STARTED, SUCCESS, FAILURE
```

## Production Considerations

### Scaling Workers
```bash
# Horizontal scaling: Run multiple worker containers
docker compose up --scale worker=3
```

### Connection Pooling
```python
broker_pool_limit = 10  # Max connections per worker
broker_heartbeat = 30   # Detect dead connections
```

### Message Persistence
- All queues are **durable** (survive broker restarts)
- Messages are **persistent** (written to disk)
- Task results stored in Redis with 1-hour expiry

### Error Scenarios

| Scenario | Behavior |
|----------|----------|
| Worker crashes mid-task | Task requeued (task_reject_on_worker_lost=True) |
| RabbitMQ restarts | Queues/messages persist (durable=True) |
| Task exceeds time limit | SoftTimeLimitExceeded → cleanup → hard kill |
| Task fails with exception | Auto-retry with backoff (up to 3 times) |
| Max retries exceeded | Send to DLQ for manual inspection |
| Network partition | Auto-reconnect with retry (broker_connection_retry=True) |

## Testing

### Unit Test Example
```python
from unittest.mock import patch
from app.tasks.import_tasks import process_csv_import

@patch("app.tasks.import_tasks.process_batch")
def test_csv_import_task(mock_process):
    mock_process.return_value = {"processed": 100}
    result = process_csv_import.apply(args=["job-123", "test.csv"])
    assert result.status == "SUCCESS"
```

### Integration Test
```python
# Use TestClient with dockerized RabbitMQ
def test_upload_enqueues_task(client):
    with open("test.csv", "rb") as f:
        response = client.post("/api/upload", files={"file": f})
    assert response.status_code == 200
    job_id = response.json()["job_id"]
    
    # Verify task was enqueued
    # (requires celery.inspect() or RabbitMQ API)
```

## Troubleshooting

### Worker Not Consuming Tasks
```bash
# Check worker connection
celery -A app.tasks.celery_app.celery_app inspect active

# Check queue bindings
rabbitmqctl list_bindings
```

### Tasks Stuck in Queue
- Verify worker is subscribed to correct queue
- Check worker logs for errors
- Verify queue routing key matches task route

### High Memory Usage
- Ensure `max_tasks_per_child=1000` is set
- Monitor task execution time
- Check for memory leaks in task code

## Next Steps (Phases 5-7)

1. **Phase 5**: Implement CSV validation service
2. **Phase 6**: Create import service with task enqueuing
3. **Phase 7**: Implement `process_csv_import` Celery task with:
   - ACK/NACK handling
   - Progress updates to Redis
   - Batch processing
   - Error recovery

