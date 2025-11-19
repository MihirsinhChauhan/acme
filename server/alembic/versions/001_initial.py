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
    op.create_table(
        "import_jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("filename", sa.Text(), nullable=False),
        sa.Column("status", import_job_status, nullable=False, server_default="queued"),
        sa.Column("total_rows", sa.Integer(), nullable=True),
        sa.Column("processed_rows", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_import_jobs"),
    )

    op.create_table(
        "products",
        sa.Column("id", sa.BigInteger(), autoincrement=True, nullable=False),
        sa.Column("sku", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_products"),
    )
    op.create_index("uq_products_sku_lower", "products", [sa.text("lower(sku)")], unique=True)


def downgrade() -> None:
    op.drop_index("uq_products_sku_lower", table_name="products")
    op.drop_table("products")

    op.drop_table("import_jobs")
    op.execute("DROP TYPE IF EXISTS import_job_status")


