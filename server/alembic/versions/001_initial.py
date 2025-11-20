"""Initial database schema with products & import_jobs tables."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create ENUM type if it doesn't exist
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname = 'import_job_status') THEN
                CREATE TYPE import_job_status AS ENUM ('queued', 'uploading', 'parsing', 'importing', 'done', 'failed');
            END IF;
        END$$;
        """
    )

    import_job_status = postgresql.ENUM(
        "queued",
        "uploading",
        "parsing",
        "importing",
        "done",
        "failed",
        name="import_job_status",
        create_type=False,
    )
    
    # Create import_jobs table if it doesn't exist
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS import_jobs (
            id UUID PRIMARY KEY,
            filename TEXT NOT NULL,
            status import_job_status NOT NULL DEFAULT 'queued',
            total_rows INTEGER,
            processed_rows INTEGER NOT NULL DEFAULT 0,
            error_message TEXT,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
        """
    )

    # Create products table if it doesn't exist
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS products (
            id BIGSERIAL PRIMARY KEY,
            sku TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            active BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
        """
    )
    
    # Create index if it doesn't exist
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_products_sku_lower 
        ON products (lower(sku));
        """
    )


def downgrade() -> None:
    op.drop_index("uq_products_sku_lower", table_name="products")
    op.drop_table("products")

    op.drop_table("import_jobs")
    op.execute("DROP TYPE IF EXISTS import_job_status")


