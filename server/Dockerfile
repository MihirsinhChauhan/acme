FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends build-essential curl && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md alembic.ini ./
COPY alembic ./alembic
RUN pip install --upgrade pip && pip install .

COPY app ./app
COPY scripts ./scripts

# Make entrypoint script executable
RUN chmod +x scripts/docker-entrypoint.sh

# Create upload directory
RUN mkdir -p /tmp/imports

ENTRYPOINT ["./scripts/docker-entrypoint.sh"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
