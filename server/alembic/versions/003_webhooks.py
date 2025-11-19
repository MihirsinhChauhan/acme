"""Create webhooks and webhook_deliveries tables."""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = "003_webhooks"
down_revision = "002_add_job_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create webhooks table
    op.create_table(
        "webhooks",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("events", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id", name="pk_webhooks"),
    )

    # Create webhook_deliveries table
    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("webhook_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.Text(), nullable=False),
        sa.Column("payload", postgresql.JSON(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="pending"),
        sa.Column("response_code", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("response_time_ms", sa.Integer(), nullable=True),
        sa.Column("attempted_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_deliveries"),
        sa.ForeignKeyConstraint(
            ["webhook_id"],
            ["webhooks.id"],
            name="fk_webhook_deliveries_webhook_id_webhooks",
            ondelete="CASCADE",
        ),
    )

    # Create index on webhook_id for faster lookups
    op.create_index("ix_webhook_deliveries_webhook_id", "webhook_deliveries", ["webhook_id"])


def downgrade() -> None:
    # Drop tables in reverse order (deliveries first due to FK)
    op.drop_index("ix_webhook_deliveries_webhook_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")

