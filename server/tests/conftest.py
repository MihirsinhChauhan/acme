"""Pytest configuration and shared fixtures."""
from __future__ import annotations

import os
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.dialects import postgresql

from app.models.base import Base
from app.models.import_job import ImportStatus

# Use PostgreSQL for testing - matches production environment
TEST_DATABASE_URL = os.getenv(
    "TEST_DATABASE_URL",
    "postgresql://postgres:postgres@localhost:5432/acme_test"
)


@pytest.fixture(scope="session")
def db_engine():
    """Create a PostgreSQL engine for testing."""
    engine = create_engine(TEST_DATABASE_URL, future=True, pool_pre_ping=True)
    
    # Drop and recreate schema to ensure clean state
    with engine.connect() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.commit()
    
    # Manually create the enum type first (before Base.metadata.create_all)
    with engine.connect() as conn:
        # Create import_job_status enum if it doesn't exist
        enum_values = [status.value for status in ImportStatus]
        enum_check = conn.execute(
            text("SELECT 1 FROM pg_type WHERE typname = 'import_job_status'")
        ).scalar()
        
        if not enum_check:
            conn.execute(
                text(f"CREATE TYPE import_job_status AS ENUM {tuple(enum_values)}")
            )
        conn.commit()
    
    # Now create all tables
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Clean up
    Base.metadata.drop_all(engine)
    with engine.connect() as conn:
        conn.execute(text("DROP TYPE IF EXISTS import_job_status"))
        conn.commit()
    engine.dispose()


@pytest.fixture
def db_session(db_engine) -> Generator[Session, None, None]:
    """Provide a database session for testing with automatic rollback."""
    connection = db_engine.connect()
    transaction = connection.begin()
    
    SessionLocal = sessionmaker(bind=connection, autoflush=False, autocommit=False)
    session = SessionLocal()
    
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()

