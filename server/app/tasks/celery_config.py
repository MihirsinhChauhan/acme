"""Celery configuration for RabbitMQ task queue with reliability and performance settings."""

from kombu import Exchange, Queue

# ==============================================================================
# BROKER & BACKEND CONFIGURATION
# ==============================================================================

# Connection settings
broker_connection_retry_on_startup = True
broker_connection_retry = True
broker_connection_max_retries = 10

# Connection pooling for better performance
broker_pool_limit = 10
broker_heartbeat = 30  # Seconds between heartbeats to detect connection issues

# Result backend settings
result_backend_transport_options = {
    "master_name": "mymaster",
    "socket_keepalive": True,
    "socket_timeout": 30,
    "retry_on_timeout": True,
}

result_expires = 3600  # Results expire after 1 hour

# ==============================================================================
# TASK EXECUTION SETTINGS
# ==============================================================================

# Acknowledgment strategy - CRITICAL for reliability
task_acks_late = True  # ACK after task completion, not on start
task_reject_on_worker_lost = True  # Requeue if worker dies unexpectedly
worker_prefetch_multiplier = 1  # Fetch 1 task at a time for fair distribution

# Task tracking
task_track_started = True  # Track when task execution begins
task_send_sent_event = True  # Send events when tasks are sent

# Serialization
task_serializer = "json"
accept_content = ["json"]
result_serializer = "json"
timezone = "UTC"
enable_utc = True

# ==============================================================================
# RETRY POLICY - Exponential Backoff
# ==============================================================================

# Default retry policy for all tasks
task_default_retry_delay = 60  # Initial retry delay in seconds
task_max_retries = 3  # Maximum number of retries

# Exponential backoff settings
# Retry delays will be: 2^1=2s, 2^2=4s, 2^3=8s
task_retry_backoff = True
task_retry_backoff_max = 600  # Max delay of 10 minutes
task_retry_jitter = True  # Add randomness to prevent thundering herd

# ==============================================================================
# QUEUE DEFINITIONS
# ==============================================================================

# Define exchanges
default_exchange = Exchange("default", type="direct", durable=True)
import_exchange = Exchange("import_tasks", type="direct", durable=True)

# Define queues with specific properties
task_queues = (
    # Default queue for general tasks
    Queue(
        "default",
        exchange=default_exchange,
        routing_key="default",
        queue_arguments={
            "x-message-ttl": 3600000,  # Messages expire after 1 hour (milliseconds)
            "x-max-priority": 10,  # Enable priority support (0-10)
        },
        durable=True,  # Survive broker restarts
    ),
    # Dedicated queue for CSV import tasks
    Queue(
        "import_queue",
        exchange=import_exchange,
        routing_key="import.csv",
        queue_arguments={
            "x-message-ttl": 7200000,  # 2 hours TTL for long-running imports
            "x-max-priority": 10,
            "x-dead-letter-exchange": "dlx",  # Dead letter exchange for failed tasks
            "x-dead-letter-routing-key": "import.failed",
        },
        durable=True,
    ),
    # Queue for bulk operations (future use)
    Queue(
        "bulk_ops_queue",
        exchange=import_exchange,
        routing_key="bulk.operations",
        queue_arguments={
            "x-message-ttl": 3600000,
            "x-max-priority": 5,
            "x-dead-letter-exchange": "dlx",
            "x-dead-letter-routing-key": "bulk.failed",
        },
        durable=True,
    ),
    # Dead Letter Queue for failed tasks
    Queue(
        "failed_tasks",
        exchange=Exchange("dlx", type="direct", durable=True),
        routing_key="*.failed",
        durable=True,
        queue_arguments={
            "x-message-ttl": 604800000,  # Keep failed tasks for 7 days
        },
    ),
)

# Default queue for unrouted tasks
task_default_queue = "default"
task_default_exchange = "default"
task_default_routing_key = "default"

# ==============================================================================
# TASK ROUTING
# ==============================================================================

# Route tasks to specific queues based on task name
task_routes = {
    # CSV import tasks
    "app.tasks.import_tasks.process_csv_import": {
        "queue": "import_queue",
        "routing_key": "import.csv",
        "priority": 5,
    },
    "app.tasks.import_tasks.validate_csv_async": {
        "queue": "import_queue",
        "routing_key": "import.csv",
        "priority": 8,  # Higher priority for quick validation
    },
    # Bulk operations
    "app.tasks.bulk_tasks.*": {
        "queue": "bulk_ops_queue",
        "routing_key": "bulk.operations",
        "priority": 3,
    },
}

# ==============================================================================
# WORKER CONFIGURATION
# ==============================================================================

# Worker pool settings (configured for I/O-bound CSV processing)
worker_concurrency = 4  # Default: 4 concurrent workers
worker_max_tasks_per_child = 1000  # Restart worker after 1000 tasks to prevent memory leaks
worker_disable_rate_limits = False

# Worker lifecycle
worker_send_task_events = True  # Send task events for monitoring
worker_log_format = "[%(asctime)s: %(levelname)s/%(processName)s] %(message)s"
worker_task_log_format = "[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s"

# ==============================================================================
# MESSAGE PERSISTENCE
# ==============================================================================

# Ensure messages are persisted to disk
task_default_delivery_mode = 2  # 2 = persistent, 1 = transient

# Task result settings
result_persistent = True
result_compression = "gzip"

# ==============================================================================
# MONITORING & EVENTS
# ==============================================================================

# Enable task events for monitoring (Flower, etc.)
worker_send_task_events = True
task_send_sent_event = True

# Event settings
event_queue_expires = 60  # Event queue expires after 60 seconds
event_queue_ttl = 5  # Event messages TTL: 5 seconds

# ==============================================================================
# BEAT SCHEDULER (for periodic tasks - future use)
# ==============================================================================

beat_schedule = {}
beat_scheduler = "celery.beat:PersistentScheduler"
beat_schedule_filename = "/tmp/celerybeat-schedule"

# ==============================================================================
# TASK ANNOTATIONS (task-specific overrides)
# ==============================================================================

task_annotations = {
    # CSV import task specific settings
    "app.tasks.import_tasks.process_csv_import": {
        "rate_limit": "10/m",  # Max 10 imports per minute
        "time_limit": 3600,  # Hard time limit: 1 hour
        "soft_time_limit": 3300,  # Soft time limit: 55 minutes (raises exception)
        "max_retries": 3,
        "default_retry_delay": 30,
    },
    # Validation task - quick execution expected
    "app.tasks.import_tasks.validate_csv_async": {
        "rate_limit": "50/m",
        "time_limit": 300,  # 5 minutes max
        "soft_time_limit": 240,
        "max_retries": 2,
    },
}

# ==============================================================================
# SECURITY & ERROR HANDLING
# ==============================================================================

# Don't send sensitive data in task errors
task_ignore_result = False
task_store_errors_even_if_ignored = True

# Security settings
accept_content = ["json"]  # Only accept JSON, prevent pickle attacks
task_protocol = 2  # Use protocol 2 for better performance

