# Testing Guide

## Prerequisites

Tests require a PostgreSQL database to match the production environment. You can use the provided Docker Compose setup or your own PostgreSQL instance.

## Quick Start

### 1. Start Test Database (Docker)

```bash
# Start PostgreSQL for testing
docker compose up -d postgres

# Wait for PostgreSQL to be ready
sleep 3
```

### 2. Run Tests

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_product_repository.py -v

# Run with coverage
uv run pytest --cov=app tests/
```

### 3. Stop Test Database

```bash
docker compose down
```

## Configuration

Tests use the following database connection:
- **Default**: `postgresql://acme:acme@localhost:5432/acme_test`
- **Override**: Set `TEST_DATABASE_URL` environment variable

```bash
export TEST_DATABASE_URL="postgresql://user:pass@host:port/dbname"
uv run pytest
```

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures (DB session, etc.)
├── test_csv_validator.py    # CSV validation tests
├── test_product_repository.py # Product repository tests
├── test_import_service.py   # Import service tests
└── test_progress_manager.py # Redis progress manager tests
```

## Writing Tests

### Database Tests

All database tests automatically run in a transaction that is rolled back after each test:

```python
def test_create_product(db_session: Session) -> None:
    repo = ProductRepository(db_session)
    # Test code here - changes are rolled back automatically
```

### Mocking Celery Tasks

When testing code that enqueues Celery tasks, mock the task to avoid Redis dependency:

```python
from unittest.mock import patch, MagicMock

def test_enqueue_task(db_session: Session):
    with patch("app.services.import_service.process_csv_import") as mock_task:
        mock_result = MagicMock()
        mock_result.id = "task-123"
        mock_task.apply_async.return_value = mock_result
        
        # Your test code here
```

## Troubleshooting

### PostgreSQL Connection Refused

Make sure PostgreSQL is running:

```bash
docker compose ps
docker compose up -d postgres
```

### Database Already Exists Error

Drop and recreate the test database:

```bash
docker compose exec postgres psql -U acme -c "DROP DATABASE IF EXISTS acme_test;"
docker compose exec postgres psql -U acme -c "CREATE DATABASE acme_test;"
```

### Import Errors

Make sure you're using the uv environment:

```bash
uv run pytest
# NOT: pytest (which might use system Python)
```

