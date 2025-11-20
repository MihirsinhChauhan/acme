# Railway Deployment Guide

This document explains how to deploy the Acme CSV Import Platform on
[Railway](https://railway.app). The goal is to reproduce the production
stack (FastAPI API + Celery worker + PostgreSQL + Redis) using Railway’s
managed services and build pipeline.

## Overview

Railway project composition:

| Service | Purpose | Notes |
| --- | --- | --- |
| `acme-api` | FastAPI web service | Provides REST + SSE |
| `acme-worker` | Celery worker | Handles CSV imports & webhooks |
| `PostgreSQL` plugin | Primary database | Railway supplies `DATABASE_URL` |
| `Redis` plugin | Celery broker + progress cache | Exposes `REDIS_URL` |

Each code service executes the same startup helper so Alembic migrations
run before the process starts (`python scripts/railway-startup.py`).

## Prerequisites

1. Railway account (GitHub or email login is fine).
2. Fork or push this repository to GitHub so Railway can deploy from it.
3. Optional: install the [Railway CLI](https://docs.railway.com/quick-start)
   if you prefer deploying from the terminal.

## Step-by-Step Deployment

### 1. Create Project & Add Data Stores

1. In the Railway dashboard, click **New Project**.
2. Select **Provision PostgreSQL** → leave defaults (name auto-generated).
   - Copy the displayed `DATABASE_URL` – Railway also auto-injects it into
     every service in the project.
3. Click **Add Service** → **Provision Redis**.
   - Copy the `REDIS_URL` value; it will become the Celery broker/result
     backend and the progress cache.

### 2. Deploy the API Service

1. Within the same project choose **Add Service → Deploy from Repo**.
2. Select the repository (`fullfil/acme`).
3. In the deploy dialog (or later under **Settings → Build & Deploy**):
   - **Root Directory**: `server`
   - **Build Command**:
     ```
     pip install --upgrade pip && pip install -e .
     ```
   - **Start Command**:
     ```
     python scripts/railway-startup.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT
     ```
4. Environment variables (Railway “Variables” tab):
   | Key | Value |
   | --- | --- |
   | `ENVIRONMENT` | `production` |
   | `API_PREFIX` | `/api` |
   | `UPLOAD_TMP_DIR` | `/tmp/imports` |
   | `MAX_UPLOAD_SIZE_MB` | `512` |
   | `DATABASE_URL` | **Reference the Postgres service variable** |
   | `REDIS_URL` | **Reference the Redis service variable** |
   | `CELERY_BROKER_URL` | same as `REDIS_URL` |
   | `CELERY_RESULT_BACKEND` | same as `REDIS_URL` |

> 💡 Railway automatically injects the Postgres connection string as
> `DATABASE_URL`; use the “Reference Variable” picker to avoid copy/paste.

### 3. Deploy the Celery Worker

Repeat the deploy-from-repo flow to create a second service:

- **Root Directory**: `server`
- **Build Command**: same as API
- **Start Command**:
  ```
  python scripts/railway-startup.py && celery -A app.tasks.celery_app.celery_app worker --loglevel=info --concurrency=4 --max-tasks-per-child=1000 -Q import_queue,bulk_ops_queue,default
  ```
- **Environment Variables**:
  - Copy the same values as the API service.
  - Optionally add `CELERY_WORKER_CONCURRENCY=4` and
    `CELERY_WORKER_PREFETCH_MULTIPLIER=1` for clarity.

### 4. Verify Deployment

1. Wait for both services to finish building.
2. Open the API service → **Settings → Domains** → click **Generate Domain**.
3. Hit the `/health` endpoint to confirm:
   ```
   curl https://<your-domain>.up.railway.app/health
   ```
4. Upload a small CSV in the UI to confirm the worker picks up jobs
   (check service logs under **Observability → Logs**).

## Optional: Railway CLI Workflow

If you prefer CLI deployments:

```bash
cd server
railway login
railway init --service acme-api
railway up
```

Repeat with `railway init --service acme-worker` for the worker, editing
`.railway/config.json` or using `railway variables set` for env values.
You can also attach Postgres / Redis via `railway add`.

## Environment Variable Summary

| Variable | Source | Description |
| --- | --- | --- |
| `DATABASE_URL` | Railway Postgres | SQLAlchemy connection string |
| `REDIS_URL` | Railway Redis | Redis cache + Celery broker |
| `CELERY_BROKER_URL` | (manual) | Set equal to `REDIS_URL` |
| `CELERY_RESULT_BACKEND` | (manual) | Set equal to `REDIS_URL` |
| `ENVIRONMENT` | manual | `production` |
| `API_PREFIX` | manual | `/api` |
| `UPLOAD_TMP_DIR` | manual | `/tmp/imports` |
| `MAX_UPLOAD_SIZE_MB` | manual | `512` |
| `CELERY_WORKER_CONCURRENCY` | manual | `4` (worker only) |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | manual | `1` (worker only) |

## Tips & Troubleshooting

- **Sleeping services**: Railway’s free tier may sleep after inactivity.
  Enable “Keep Awake” (paid) or send periodic health checks.
- **File storage**: `/tmp/imports` is ephemeral. For long-term storage,
  push CSVs to S3/GCS before triggering imports.
- **Scaling**: Increase service plan, or add replicas via the Railway UI.
- **Logs**: Use the **Observability** tab per service for build/run logs.

That’s it! After both services are healthy you can point the frontend to
the Railway API domain and run imports end-to-end.

