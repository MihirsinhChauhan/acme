"""Health check endpoints for monitoring service and dependency status."""
from typing import Any

from fastapi import APIRouter, status
from sqlalchemy import text

from app.core.config import get_settings
from app.core.db import engine
from app.core.redis_manager import get_redis_client
from app.tasks.celery_app import celery_app

router = APIRouter(tags=["health"])
settings = get_settings()


@router.get("/health")
async def health_check() -> dict[str, str]:
    """Basic health check endpoint.
    
    Returns:
        Simple status response for load balancers
    """
    return {"status": "ok"}


@router.get("/health/detailed")
async def detailed_health_check() -> dict[str, Any]:
    """Detailed health check for all service dependencies.
    
    Checks:
    - Database connectivity
    - Redis connectivity
    - Celery worker availability
    - RabbitMQ connectivity (via Celery)
    
    Returns:
        Detailed health status for each component
    """
    health_status = {
        "status": "healthy",
        "components": {},
    }
    
    # Check Database
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        health_status["components"]["database"] = {
            "status": "healthy",
            "message": "PostgreSQL connection successful",
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["database"] = {
            "status": "unhealthy",
            "message": f"Database connection failed: {str(e)}",
        }
    
    # Check Redis
    try:
        redis_client = get_redis_client()
        await redis_client.ping()
        health_status["components"]["redis"] = {
            "status": "healthy",
            "message": "Redis connection successful",
        }
    except Exception as e:
        health_status["status"] = "unhealthy"
        health_status["components"]["redis"] = {
            "status": "unhealthy",
            "message": f"Redis connection failed: {str(e)}",
        }
    
    # Check Celery Workers
    try:
        # Inspect active workers
        inspect = celery_app.control.inspect(timeout=2.0)
        active_workers = inspect.active()
        
        if active_workers:
            worker_count = len(active_workers)
            health_status["components"]["celery"] = {
                "status": "healthy",
                "message": f"{worker_count} worker(s) available",
                "workers": list(active_workers.keys()),
            }
        else:
            health_status["status"] = "degraded"
            health_status["components"]["celery"] = {
                "status": "degraded",
                "message": "No active Celery workers found",
            }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["celery"] = {
            "status": "degraded",
            "message": f"Failed to inspect Celery workers: {str(e)}",
        }
    
    # Check RabbitMQ (via Celery broker)
    try:
        # Attempt to get broker connection stats
        stats = inspect.stats() if inspect else None
        if stats:
            health_status["components"]["rabbitmq"] = {
                "status": "healthy",
                "message": "RabbitMQ broker connection successful",
            }
        else:
            health_status["status"] = "degraded"
            health_status["components"]["rabbitmq"] = {
                "status": "degraded",
                "message": "Unable to retrieve RabbitMQ stats",
            }
    except Exception as e:
        health_status["status"] = "degraded"
        health_status["components"]["rabbitmq"] = {
            "status": "degraded",
            "message": f"RabbitMQ check failed: {str(e)}",
        }
    
    # Set HTTP status code based on health
    return health_status


@router.get("/health/celery")
async def celery_health() -> dict[str, Any]:
    """Celery-specific health check with detailed worker information.
    
    Returns:
        Celery worker stats including active tasks, queues, and registered tasks
    """
    try:
        inspect = celery_app.control.inspect(timeout=3.0)
        
        if not inspect:
            return {
                "status": "unhealthy",
                "message": "Unable to connect to Celery",
            }
        
        # Get various worker stats
        active_tasks = inspect.active()
        registered_tasks = inspect.registered()
        stats = inspect.stats()
        active_queues = inspect.active_queues()
        
        return {
            "status": "healthy" if active_tasks is not None else "degraded",
            "workers": {
                "active": list(active_tasks.keys()) if active_tasks else [],
                "count": len(active_tasks) if active_tasks else 0,
            },
            "tasks": {
                "active": sum(len(tasks) for tasks in active_tasks.values()) if active_tasks else 0,
                "registered": len(registered_tasks.get(list(registered_tasks.keys())[0], [])) if registered_tasks else 0,
            },
            "queues": active_queues,
            "stats": stats,
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "message": f"Celery health check failed: {str(e)}",
        }

