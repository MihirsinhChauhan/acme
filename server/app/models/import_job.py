"""Import job model definition."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Enum as PgEnum, Integer, Text, func
from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base


class ImportStatus(str, Enum):
    """Enumerates the lifecycle states an import job can be in."""

    QUEUED = "queued"
    UPLOADING = "uploading"
    PARSING = "parsing"
    IMPORTING = "importing"
    DONE = "done"
    FAILED = "failed"


class JobType(str, Enum):
    """Enumerates the types of jobs that can be tracked."""

    IMPORT = "import"
    BULK_DELETE = "bulk_delete"


class ImportJob(Base):
    """Tracks metadata and progress for a CSV import request."""

    __tablename__ = "import_jobs"

    id: Mapped[UUID] = mapped_column(
        PG_UUID(as_uuid=True),
        primary_key=True,
        default=uuid4,
    )
    filename: Mapped[str] = mapped_column(Text, nullable=False)
    job_type: Mapped[JobType] = mapped_column(
        PgEnum(JobType, name="job_type", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=JobType.IMPORT,
        server_default=JobType.IMPORT.value,
    )
    status: Mapped[ImportStatus] = mapped_column(
        PgEnum(ImportStatus, name="import_job_status", values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=ImportStatus.QUEUED,
        server_default=ImportStatus.QUEUED.value,
    )
    total_rows: Mapped[int | None] = mapped_column(Integer, nullable=True)
    processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


