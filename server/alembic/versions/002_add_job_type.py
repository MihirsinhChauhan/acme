"""Add job_type column to import_jobs table."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "002_add_job_type"
down_revision = "001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create job_type ENUM if it doesn't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'job_type') THEN
                CREATE TYPE job_type AS ENUM ('import', 'bulk_delete');
            END IF;
        END$$;
        """
    )

    # Add job_type column if it doesn't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM information_schema.columns 
                WHERE table_name = 'import_jobs' AND column_name = 'job_type'
            ) THEN
                ALTER TABLE import_jobs 
                ADD COLUMN job_type job_type NOT NULL DEFAULT 'import';
            END IF;
        END$$;
        """
    )


def downgrade() -> None:
    # Remove job_type column
    op.drop_column("import_jobs", "job_type")
    # Drop the ENUM type
    op.execute("DROP TYPE IF EXISTS job_type")

