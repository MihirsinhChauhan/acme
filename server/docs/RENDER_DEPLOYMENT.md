# Render Deployment Guide

This guide explains how to deploy the Acme CSV Import Platform to Render.

## Overview

The deployment consists of:
- **Web Service**: FastAPI API server
- **Background Worker**: Celery worker for processing CSV imports
- **PostgreSQL Database**: Managed database for application data
- **Redis**: Managed Redis for caching, progress tracking, and Celery broker

## Prerequisites

1. A Render account (sign up at https://render.com)
2. Your code pushed to a Git repository (GitHub, GitLab, or Bitbucket)

## Deployment Steps

### Option 1: Using render.yaml (Recommended)

1. **Connect your repository to Render**:
   - Go to Render Dashboard → New → Blueprint
   - Connect your Git repository
   - Render will automatically detect `render.yaml` in the `server/` directory

2. **Configure the Blueprint**:
   - Set the **Root Directory** to `server`
   - Render will create all services defined in `render.yaml`

3. **Deploy**:
   - Click "Apply" to create all services
   - Render will build and deploy everything automatically

### Option 2: Manual Setup

If you prefer to set up services manually:

#### 1. Create PostgreSQL Database

- Go to **New → PostgreSQL**
- Name: `acme-db`
- Database: `acme`
- User: `acme_user`
- Plan: Starter (or higher for production)
- Note the **Internal Database URL** and **Connection Pooling URL**

#### 2. Create Redis Instance

- Go to **New → Redis**
- Name: `acme-redis`
- Plan: Starter (or higher for production)
- Note the **Internal Redis URL**

#### 3. Create Web Service (API)

- Go to **New → Web Service**
- Connect your repository
- Settings:
  - **Name**: `acme-api`
  - **Root Directory**: `server`
  - **Environment**: `Python 3`
  - **Build Command**: `pip install --upgrade pip && pip install -e .`
  - **Start Command**: `python scripts/render-startup.py && uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Environment Variables:
  ```
  ENVIRONMENT=production
  API_PREFIX=/api
  UPLOAD_TMP_DIR=/tmp/imports
  MAX_UPLOAD_SIZE_MB=512
  DATABASE_URL=<from database connection string>
  REDIS_URL=<from redis connection string>
  CELERY_BROKER_URL=<same as REDIS_URL>
  CELERY_RESULT_BACKEND=<same as REDIS_URL>
  ```
- **Auto-Deploy**: Yes (deploys on every push to main)

#### 4. Create Background Worker

- Go to **New → Background Worker**
- Connect your repository
- Settings:
  - **Name**: `acme-worker`
  - **Root Directory**: `server`
  - **Environment**: `Python 3`
  - **Build Command**: `pip install --upgrade pip && pip install -e .`
  - **Start Command**: `python scripts/render-startup.py && celery -A app.tasks.celery_app.celery_app worker --loglevel=info --concurrency=4 --max-tasks-per-child=1000 -Q import_queue,bulk_ops_queue,default`
- Environment Variables:
  ```
  ENVIRONMENT=production
  DATABASE_URL=<from database connection string>
  REDIS_URL=<from redis connection string>
  CELERY_BROKER_URL=<same as REDIS_URL>
  CELERY_RESULT_BACKEND=<same as REDIS_URL>
  CELERY_WORKER_CONCURRENCY=4
  CELERY_WORKER_PREFETCH_MULTIPLIER=1
  ```

## Environment Variables

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/acme` |
| `REDIS_URL` | Redis connection string | `redis://host:6379/0` |
| `CELERY_BROKER_URL` | Celery broker URL (use Redis URL) | `redis://host:6379/0` |
| `CELERY_RESULT_BACKEND` | Celery result backend (use Redis URL) | `redis://host:6379/1` |

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Environment mode: `development`, `staging`, `production` |
| `API_PREFIX` | `/api` | API route prefix |
| `UPLOAD_TMP_DIR` | `/tmp/imports` | Temporary directory for CSV uploads |
| `MAX_UPLOAD_SIZE_MB` | `512` | Maximum upload size in MB |

## Important Notes

### Using Redis as Celery Broker

Render doesn't offer managed RabbitMQ, so we use **Redis as the Celery broker**. This is a common pattern and works well for most use cases. The configuration in `celery_config.py` includes some RabbitMQ-specific settings that will be gracefully ignored when using Redis.

### Database Migrations

Migrations run automatically on startup via `scripts/render-startup.py`. This ensures your database schema is always up-to-date.

### File Uploads

- Uploads are stored in `/tmp/imports` (ephemeral storage)
- Files are processed and deleted after import completes
- For production, consider using S3 or similar for persistent storage

### Scaling

- **Web Service**: Can scale horizontally (multiple instances)
- **Worker**: Can scale horizontally (multiple worker instances)
- **Database**: Upgrade plan for more connections/performance
- **Redis**: Upgrade plan for more memory

### Monitoring

- Check service logs in Render Dashboard
- Monitor database connections and Redis memory usage
- Set up alerts for service failures

## Important Notes on Service References

If the automatic service references in `render.yaml` don't work (some Render plans may have limitations), you can manually set the environment variables:

1. After creating the Redis service, go to its dashboard
2. Find the "Connection Info" or "Internal Redis URL"
3. Copy the connection string (format: `redis://...`)
4. Manually set these environment variables in both the API and Worker services:
   - `REDIS_URL`
   - `CELERY_BROKER_URL` (same as REDIS_URL)
   - `CELERY_RESULT_BACKEND` (can be same as REDIS_URL or use a different database number)

## Troubleshooting

### Build Failures

- Check that `pyproject.toml` is valid
- Ensure all dependencies are listed correctly
- Check build logs for specific errors

### Database Connection Issues

- Verify `DATABASE_URL` is correct
- Check database is running and accessible
- Ensure connection pooling is configured if using it

### Worker Not Processing Tasks

- Verify `CELERY_BROKER_URL` matches `REDIS_URL`
- Check worker logs for connection errors
- Ensure Redis is running and accessible

### Migration Failures

- Check database connection string
- Verify database user has migration permissions
- Review migration logs in startup script output

## Post-Deployment

1. **Test the API**:
   ```bash
   curl https://your-service.onrender.com/health
   ```

2. **Test CSV Upload**:
   - Use the web interface or API client
   - Upload a test CSV file
   - Monitor worker logs for processing

3. **Monitor Services**:
   - Check all services are running
   - Monitor resource usage
   - Set up alerts

## Updating the Deployment

1. Push changes to your repository
2. Render will automatically rebuild and redeploy (if auto-deploy is enabled)
3. Or manually trigger a deploy from the Render Dashboard

## Cost Considerations

- **Starter Plan**: Free tier available (with limitations)
- **Production**: Consider paid plans for:
  - Better performance
  - More resources
  - Better reliability
  - Support

## Security

- Use Render's environment variable encryption
- Never commit secrets to the repository
- Use connection pooling for databases
- Enable SSL/TLS for all connections
- Regularly update dependencies

