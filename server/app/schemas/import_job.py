"""Pydantic schemas describing import job payloads."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.import_job import ImportStatus


class ImportJobCreate(BaseModel):
    """Payload used when creating a new import job record."""

    filename: str = Field(description="Original filename supplied during upload")
    total_rows: int | None = Field(
        default=None,
        ge=0,
        description="Optional hint about how many rows the CSV contains",
    )

    @field_validator("filename")
    @classmethod
    def ensure_filename(cls, value: str) -> str:
        value = value.strip()
        if not value:
            msg = "filename cannot be empty"
            raise ValueError(msg)
        return value


class ImportJobResponse(BaseModel):
    """Full representation of an import job."""

    id: UUID
    filename: str
    status: ImportStatus
    total_rows: int | None = Field(default=None, ge=0)
    processed_rows: int = Field(ge=0)
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ImportProgress(BaseModel):
    """Progress payload pushed to Redis + SSE clients."""

    job_id: UUID
    status: ImportStatus
    stage: str | None = Field(
        default=None, description="High-level stage (uploading, parsing, batch info, etc.)"
    )
    total_rows: int | None = Field(default=None, ge=0)
    processed_rows: int = Field(ge=0)
    progress_percent: float | None = Field(
        default=None,
        ge=0,
        le=100,
        description="Derived percentage to simplify client rendering",
    )
    error_message: str | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


