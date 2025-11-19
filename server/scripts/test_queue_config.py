#!/usr/bin/env python3
"""Helper script to test RabbitMQ queue configuration and task routing.

Usage:
    python scripts/test_queue_config.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.tasks.celery_app import celery_app
from app.tasks.test_tasks import (
    test_ack_strategy,
    test_bulk_queue,
    test_import_queue,
    test_retry_mechanism,
    test_time_limits,
)


def print_separator(title: str) -> None:
    """Print a formatted section separator."""
    print("\n" + "=" * 80)
    print(f"  {title}")
    print("=" * 80 + "\n")


def inspect_queues() -> None:
    """Inspect configured queues and routing."""
    print_separator("Queue Configuration")
    
    # Get queue configuration
    queues = celery_app.conf.task_queues
    
    print("Configured Queues:")
    for queue in queues:
        print(f"\n  Queue: {queue.name}")
        print(f"    Exchange: {queue.exchange.name} (type: {queue.exchange.type})")
        print(f"    Routing Key: {queue.routing_key}")
        print(f"    Durable: {queue.durable}")
        if queue.queue_arguments:
            print(f"    Arguments:")
            for key, value in queue.queue_arguments.items():
                print(f"      {key}: {value}")


def inspect_routing() -> None:
    """Inspect task routing configuration."""
    print_separator("Task Routing Rules")
    
    routes = celery_app.conf.task_routes
    
    if routes:
        print("Task Routes:")
        for pattern, config in routes.items():
            print(f"\n  Pattern: {pattern}")
            for key, value in config.items():
                print(f"    {key}: {value}")
    else:
        print("No custom routing rules configured")


def inspect_worker_config() -> None:
    """Inspect worker configuration."""
    print_separator("Worker Configuration")
    
    config_items = [
        ("task_acks_late", "ACK after completion"),
        ("task_reject_on_worker_lost", "Requeue if worker dies"),
        ("worker_prefetch_multiplier", "Tasks to prefetch"),
        ("task_track_started", "Track task start"),
        ("task_max_retries", "Max retry attempts"),
        ("task_retry_backoff", "Exponential backoff"),
        ("worker_concurrency", "Worker concurrency"),
        ("task_serializer", "Task serializer"),
        ("result_serializer", "Result serializer"),
    ]
    
    print("Key Settings:")
    for key, description in config_items:
        value = getattr(celery_app.conf, key, "Not set")
        print(f"  {description:30} ({key}): {value}")


def test_task_enqueue() -> None:
    """Test enqueueing tasks to different queues."""
    print_separator("Task Enqueue Tests")
    
    print("Sending test tasks to queues...\n")
    
    # Test 1: Import queue task
    print("1. Testing import_queue routing:")
    result1 = test_import_queue.apply_async(
        args=["Test CSV import"],
        priority=5,
    )
    print(f"   Task ID: {result1.id}")
    print(f"   Status: {result1.status}")
    
    # Test 2: Bulk operations queue (won't route properly as task name doesn't match pattern)
    print("\n2. Testing bulk_ops_queue routing:")
    result2 = test_bulk_queue.apply_async(
        args=["insert", [{"id": 1}, {"id": 2}]],
        priority=3,
    )
    print(f"   Task ID: {result2.id}")
    print(f"   Status: {result2.status}")
    
    # Test 3: Retry mechanism
    print("\n3. Testing retry mechanism:")
    result3 = test_retry_mechanism.apply_async(
        args=[True, 1],  # Fail once, succeed on first retry
    )
    print(f"   Task ID: {result3.id}")
    print(f"   Status: {result3.status}")
    print(f"   This task will fail once and retry automatically")
    
    # Test 4: Time limits
    print("\n4. Testing time limits:")
    result4 = test_time_limits.apply_async(
        args=[3],  # Sleep for 3 seconds (within limits)
    )
    print(f"   Task ID: {result4.id}")
    print(f"   Status: {result4.status}")
    
    # Test 5: ACK strategy
    print("\n5. Testing ACK late strategy:")
    result5 = test_ack_strategy.apply_async(
        args=["test data"],
    )
    print(f"   Task ID: {result5.id}")
    print(f"   Status: {result5.status}")
    
    print("\n" + "-" * 80)
    print("Tasks enqueued successfully!")
    print("Monitor progress with:")
    print("  - RabbitMQ Management UI: http://localhost:15672")
    print("  - Celery worker logs")
    print("  - Task status: celery -A app.tasks.celery_app.celery_app result <task_id>")


def check_connectivity() -> None:
    """Check connectivity to broker and backend."""
    print_separator("Connectivity Check")
    
    try:
        # Try to ping workers
        print("Checking worker connectivity...")
        inspector = celery_app.control.inspect()
        
        # Get active workers
        active = inspector.active()
        if active:
            print(f"✓ Found {len(active)} active worker(s):")
            for worker, tasks in active.items():
                print(f"  - {worker}: {len(tasks)} active task(s)")
        else:
            print("⚠ No active workers found")
            print("  Start a worker with:")
            print("  celery -A app.tasks.celery_app.celery_app worker --loglevel=info")
        
        # Check registered tasks
        print("\nRegistered tasks:")
        registered = inspector.registered()
        if registered:
            for worker, tasks in registered.items():
                print(f"  Worker: {worker}")
                import_tasks = [t for t in tasks if "import" in t or "test" in t]
                for task in import_tasks[:5]:  # Show first 5
                    print(f"    - {task}")
        else:
            print("  No workers to query")
            
    except Exception as e:
        print(f"✗ Error checking connectivity: {e}")
        print("\nMake sure RabbitMQ is running:")
        print("  docker compose up -d rabbitmq")


def main() -> None:
    """Main entry point."""
    print("\n" + "=" * 80)
    print("  RabbitMQ Queue Configuration Test")
    print("=" * 80)
    
    # Run all checks
    check_connectivity()
    inspect_queues()
    inspect_routing()
    inspect_worker_config()
    
    # Ask user if they want to enqueue test tasks
    print("\n" + "=" * 80)
    response = input("Do you want to enqueue test tasks? (yes/no): ").strip().lower()
    
    if response in ["yes", "y"]:
        test_task_enqueue()
    else:
        print("\nSkipping task enqueue. Run this script again to enqueue test tasks.")
    
    print("\n" + "=" * 80)
    print("  Test completed!")
    print("=" * 80 + "\n")


if __name__ == "__main__":
    main()

