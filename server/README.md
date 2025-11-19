# Acme Import Backend

FastAPI + Celery service that ingests large CSV product catalogs with real-time progress updates, product CRUD APIs, webhook management, and bulk delete workflows.

## Getting Started

1. Create a Python 3.12 virtual environment.
2. Install dependencies with `poetry install` (or `pip install -e .`).
3. Copy `.env.example` to `.env` and fill in connection strings.
4. Start the API with `uvicorn app.main:app --reload`.
5. Run the Celery worker with `celery -A app.tasks.celery_app.celery_app worker -l info`.

Infrastructure services (Postgres, RabbitMQ, Redis) will be provided via `docker-compose` in a later step.
