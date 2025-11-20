# Acme Import Backend

FastAPI + Celery service that ingests large CSV product catalogs with real-time progress updates, product CRUD APIs, webhook management, and bulk delete workflows.

## Getting Started

### Local Development

1. Create a Python 3.12 virtual environment.
2. Install dependencies with `poetry install` (or `pip install -e .`).
3. Copy `.env.example` to `.env` and fill in connection strings.
4. Start the API with `uvicorn app.main:app --reload`.
5. Run the Celery worker with `celery -A app.tasks.celery_app.celery_app worker -l info`.

Infrastructure services (Postgres, RabbitMQ, Redis) will be provided via `docker-compose` in a later step.

### Docker Compose

```bash
docker compose up -d
```

This will start:
- PostgreSQL database
- Redis cache
- RabbitMQ message broker
- FastAPI API server
- Celery worker

### Render Deployment

For deploying to Render cloud platform, see [RENDER_DEPLOYMENT.md](./RENDER_DEPLOYMENT.md).

Quick start:
1. Push your code to a Git repository
2. Connect to Render and use the `render.yaml` blueprint
3. Set the root directory to `server`
4. Deploy!

The deployment uses Redis as the Celery broker (since Render doesn't offer managed RabbitMQ).

### Railway Deployment

To deploy on Railway, follow [RAILWAY_DEPLOYMENT.md](./docs/RAILWAY_DEPLOYMENT.md).
It covers provisioning managed Postgres + Redis, configuring two services
(API + worker) from this repo, and the exact build/start commands Railway
should run.
