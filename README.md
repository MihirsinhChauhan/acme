# Acme CSV Import Platform

Modern CSV import pipeline for product catalogs with FastAPI, Celery, PostgreSQL, Redis, RabbitMQ, and a React/Vite dashboard. Supports 500k-row uploads, live progress over SSE, product CRUD, bulk deletes, and webhook delivery monitoring.

## Features

- Large CSV imports in 10k-row batches with idempotent Celery workers and deduped `LOWER(sku)` upserts.
- Real-time progress tracking via Redis-backed SSE (`/api/progress/{job_id}`) and Redis pub/sub broadcasts every 2-3s.
- Product catalog CRUD APIs plus async bulk delete workflow with the same progress pipeline.
- Webhook management UI + API (test sends, delivery logs, `product.*` + `import.*` event payloads).
- React + shadcn/ui frontend (Vite, TypeScript) for uploads, monitoring, product search, and webhook tooling.
- Docker Compose stack for Postgres 16, Redis 7, RabbitMQ 3, FastAPI API, and Celery workers.

## Architecture

```
[client (Vite/React)] → REST/SSE → [FastAPI API layer]
                                 ↘ writes ↙
                            [PostgreSQL 16]
      Celery tasks ← RabbitMQ (pyamqp) ← FastAPI enqueue
             ↓                    ↙
        Redis 7 (result backend + pub/sub progress cache)
```

- API lives in `server/app` (FastAPI routers under `app/api/`).
- Background workers under `app/tasks/` use Celery 5.4 with Redis result backend and RabbitMQ broker.
- SQLAlchemy 2.0 models + Alembic migrations under `server/app/models` and `server/alembic`.
- Frontend in `client/` (Vite 5, React 18, TypeScript, shadcn/ui).

## Repository Layout

```
server/
  app/                FastAPI application, services, tasks
  alembic/            Database migrations
  docs/               API, Redis, RabbitMQ, deployment notes
  data/products.csv   Sample import file
  docker-compose.yml  Local infra + API/worker services
client/
  src/                React application (pages, hooks, ui)
render.yaml           Render blueprint (API + worker)
```

## Prerequisites

- Python 3.12 with [uv](https://github.com/astral-sh/uv) (preferred) or virtualenv + pip.
- Node.js 20+ (Vite dev server) and npm or bun.
- Docker + docker compose (for local infra parity).

## Backend Setup (`server/`)

1. `cd server`
2. Copy environment: `cp .env.example .env` and fill Postgres, Redis, RabbitMQ URLs if not using defaults.
3. Install dependencies (editable mode for dev):
   ```bash
   uv sync  # or: python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"
   ```
4. Run database migrations:
   ```bash
   uv run alembic upgrade head
   ```
5. Start supporting services (choose one):
   - **Docker Compose (recommended)**: `docker compose up --build` from `server/`.
   - **Local services**: provision Postgres, Redis, RabbitMQ manually and ensure URLs match `.env`.
6. Launch API & workers (if not using compose services):
   ```bash
   uv run uvicorn app.main:app --reload
   uv run celery -A app.tasks.celery_app.celery_app worker -l info
   ```
7. Optional Redis/Postgres CLIs: `docker exec -it server-redis-1 redis-cli`, etc., when using compose.

### Useful Backend Scripts

- `scripts/start-api.sh`: starts API with env validation.
- `scripts/run_migrations.py`: helper for programmatic Alembic execution.
- `scripts/test_*.py`: targeted smoke tests for queue config, uploads, and webhooks.

## Frontend Setup (`client/`)

1. `cd client`
2. Install deps: `npm install` (or `bun install` / `pnpm install`).
3. Run dev server: `npm run dev` (defaults to `http://localhost:5173`).
4. Configure API base URL in `client/src/lib/api/config.ts` (defaults to `http://localhost:8000/api`).

The UI includes:
- Upload screen that posts to `/api/upload`, streams progress via `EventSource`, and shows batch stats.
- Product table with filters, inline dialogs for create/edit/delete, and bulk delete initiation.
- Webhooks area for CRUD, delivery history, and synchronous test sends.

## Running Everything with Docker Compose

```bash
cd server
docker compose up --build
```

Services exposed locally:
- FastAPI API: `http://localhost:8000`
- Frontend (when run separately): `http://localhost:5173`
- Postgres: `localhost:5432` (`postgres/postgres`)
- Redis: `localhost:6379`
- RabbitMQ: `localhost:5672` (AMQP) & `http://localhost:15672` (management UI)

Attach a local frontend by pointing `VITE_API_BASE_URL` (or `client/src/lib/api/config.ts`) to `http://localhost:8000/api`.

## CSV Import Workflow

1. **Upload:** `POST /api/upload` with multipart CSV containing headers `sku`, `name`, `price`, `description`, `active`. Files up to 512 MB are accepted by default.
2. **Job creation:** API persists an `import_jobs` row, stores temp file under `UPLOAD_TMP_DIR`, enqueues Celery task with batch metadata.
3. **Processing:** Workers parse CSV in 10k-row chunks, perform case-insensitive upserts, retry transient failures with exponential backoff, and clean up temp files.
4. **Progress:** Redis hash caches `{status, stage, processed_rows, total_rows, percent}`; SSE endpoint `/api/progress/{job_id}` streams updates until `done` or `failed`.
5. **Webhooks:** On completion/failure, optional webhook events `import.completed` / `import.failed` fire; product events emit during CRUD and bulk delete flows.

Sample CSV lives in `server/data/products.csv`.

## Testing

### Backend
```bash
cd server
uv run pytest              # full suite (unit + API)
uv run pytest tests/test_upload_endpoint.py -k progress
uv run ruff check app      # lint
uv run black app tests     # format
```
Tests rely on fakeredis/mocked RabbitMQ, so they run without containers. Integration tests expect Postgres.

### Frontend
```bash
cd client
npm run lint
# add component tests via Vitest/React Testing Library if needed
```

## Deployment

- **Render**: use `render.yaml` blueprint; see `server/docs/RENDER_DEPLOYMENT.md` for build/run commands and Celery worker wiring (Redis as broker).
- **Railway**: follow `server/docs/RAILWAY_DEPLOYMENT.md` to provision managed Postgres + Redis and configure API/worker services with `scripts/railway-startup.py`.
- **Custom K8s/VMs**: container image built from `server/Dockerfile` runs both API and worker (set `COMMAND`/`PROC_TYPE`). Provide Postgres, Redis, RabbitMQ URLs via env vars.

## Monitoring & Health

- `/health`: FastAPI + DB reachability check.
- RabbitMQ management UI (port 15672) shows Celery queues `import_queue`, `bulk_ops_queue`, `default`.
- Celery worker readiness uses `celery inspect ping` healthcheck inside Compose.
- Redis pub/sub can be inspected via `redis-cli monitor` for progress payloads.

## Troubleshooting

- **Upload fails immediately**: confirm CSV headers (`sku`, `name`, `price`, `description`, `active`) and size < `MAX_UPLOAD_SIZE_MB`.
- **SSE stops early**: ensure client keeps connection open and network proxies allow streaming; check Redis + worker logs.
- **Duplicate SKUs not updated**: verify Postgres unique index on `LOWER(sku)` exists (`alembic upgrade head`) and job logs show `ON CONFLICT` upsert path.
- **Worker idle**: confirm RabbitMQ reachable via `amqp://` URL and Celery queues match `CELERY_IMPORTS` definitions.

## Next Steps

- Expand test coverage for webhook retries and SSE disconnect handling.
- Add observability (structured logging with job IDs, metrics for batch throughput).
- Harden deployments with autoscaling workers and managed RabbitMQ/Redis.

---

For deeper docs see:
- `server/docs/api_endpoints.md` – full REST/SSE reference.
- `server/docs/rabbitmq.md` / `server/docs/redis.md` – queue and cache details.
- `server/docs/RAILWAY_DEPLOYMENT.md` / `server/docs/RENDER_DEPLOYMENT.md` – platform guides.

