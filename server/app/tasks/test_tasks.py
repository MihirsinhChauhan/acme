"""Test tasks to verify RabbitMQ configuration and task routing."""

import time
from typing import Any

from celery import Task
from celery.exceptions import SoftTimeLimitExceeded

from app.tasks.celery_app import celery_app


class CallbackTask(Task):
    """Base task with lifecycle callbacks for debugging."""

    def on_success(self, retval: Any, task_id: str, args: tuple, kwargs: dict) -> None:
        """Called when task succeeds."""
        print(f"Task {task_id} succeeded with result: {retval}")

    def on_retry(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        """Called when task is retried."""
        print(f"Task {task_id} retrying due to: {exc}")

    def on_failure(self, exc: Exception, task_id: str, args: tuple, kwargs: dict, einfo: Any) -> None:
        """Called when task fails."""
        print(f"Task {task_id} failed with error: {exc}")


@celery_app.task(
    base=CallbackTask,
    bind=True,
    name="app.tasks.test_tasks.test_import_queue",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def test_import_queue(self: Task, test_data: str) -> dict[str, Any]:
    """Test task for import_queue routing.
    
    This task should be routed to the import_queue based on celery_config.py routing rules.
    
    Args:
        test_data: Sample data to process
        
    Returns:
        dict with task execution details
    """
    try:
        print(f"Processing test task on import_queue: {test_data}")
        
        # Simulate some work
        time.sleep(2)
        
        return {
            "status": "success",
            "task_id": self.request.id,
            "queue": "import_queue",
            "data": test_data,
            "retry_count": self.request.retries,
        }
    except SoftTimeLimitExceeded:
        print(f"Task {self.request.id} exceeded soft time limit")
        # Perform cleanup before hard kill
        raise
    except Exception as exc:
        print(f"Task {self.request.id} encountered error: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(
    base=CallbackTask,
    bind=True,
    name="app.tasks.test_tasks.test_bulk_queue",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def test_bulk_queue(self: Task, operation: str, data: list[dict]) -> dict[str, Any]:
    """Test task for bulk_ops_queue routing.
    
    Args:
        operation: Type of bulk operation
        data: List of items to process
        
    Returns:
        dict with task execution details
    """
    try:
        print(f"Processing bulk operation '{operation}' with {len(data)} items")
        
        # Simulate bulk processing
        time.sleep(1)
        
        return {
            "status": "success",
            "task_id": self.request.id,
            "queue": "bulk_ops_queue",
            "operation": operation,
            "items_processed": len(data),
            "retry_count": self.request.retries,
        }
    except Exception as exc:
        print(f"Bulk task {self.request.id} encountered error: {exc}")
        raise self.retry(exc=exc, countdown=2 ** self.request.retries)


@celery_app.task(
    bind=True,
    name="app.tasks.test_tasks.test_retry_mechanism",
    autoretry_for=(ValueError,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def test_retry_mechanism(self: Task, should_fail: bool = True, attempt_to_succeed: int = 2) -> dict[str, Any]:
    """Test task to verify retry mechanism with exponential backoff.
    
    Args:
        should_fail: Whether task should fail initially
        attempt_to_succeed: Which retry attempt should succeed
        
    Returns:
        dict with task execution details
    """
    current_attempt = self.request.retries
    
    print(f"Retry test - Attempt {current_attempt + 1} (retries: {current_attempt})")
    
    if should_fail and current_attempt < attempt_to_succeed:
        # Fail on purpose to trigger retry
        raise ValueError(f"Intentional failure on attempt {current_attempt + 1}")
    
    return {
        "status": "success",
        "task_id": self.request.id,
        "total_attempts": current_attempt + 1,
        "message": f"Succeeded after {current_attempt} retries",
    }


@celery_app.task(
    bind=True,
    name="app.tasks.test_tasks.test_time_limits",
    soft_time_limit=5,
    time_limit=10,
)
def test_time_limits(self: Task, sleep_duration: int = 3) -> dict[str, Any]:
    """Test task to verify time limit enforcement.
    
    Args:
        sleep_duration: How long to sleep (in seconds)
        
    Returns:
        dict with task execution details
    """
    try:
        print(f"Starting task with {sleep_duration}s sleep duration")
        time.sleep(sleep_duration)
        
        return {
            "status": "success",
            "task_id": self.request.id,
            "duration": sleep_duration,
            "message": "Completed within time limits",
        }
    except SoftTimeLimitExceeded:
        print(f"Task {self.request.id} exceeded soft time limit - cleaning up")
        # Perform cleanup here
        return {
            "status": "timeout",
            "task_id": self.request.id,
            "duration": sleep_duration,
            "message": "Exceeded soft time limit",
        }


@celery_app.task(name="app.tasks.test_tasks.test_ack_strategy")
def test_ack_strategy(data: str) -> dict[str, Any]:
    """Test task to verify ACK late strategy.
    
    With task_acks_late=True, this task should only be ACKed after completion.
    If the worker crashes during execution, the task will be requeued.
    
    Args:
        data: Test data
        
    Returns:
        dict with task execution details
    """
    print(f"Processing ACK test with data: {data}")
    
    # Simulate some work
    time.sleep(1)
    
    # If this task were to crash here (before return), it would be requeued
    # because of task_acks_late=True
    
    return {
        "status": "success",
        "data": data,
        "message": "ACK sent only after this return statement",
    }

