"""Celery application factory with RabbitMQ task queue configuration."""

from celery import Celery

from app.core.config import get_settings

settings = get_settings()

# Create Celery app instance
celery_app = Celery(
    "acme_importer",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Load configuration from celery_config module
celery_app.config_from_object("app.tasks.celery_config")

# Auto-discover tasks from app.tasks module
# This will find all tasks decorated with @celery_app.task
celery_app.autodiscover_tasks(["app.tasks"])

# Configure broker connection with retry and health check settings
celery_app.conf.update(
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
)


def get_celery_app() -> Celery:
    """Return the configured Celery application instance.
    
    Useful for dependency injection in tests and for explicit imports.
    """
    return celery_app
