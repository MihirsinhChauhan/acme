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
    # Create webhooks table if it doesn't exist
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webhooks (
            id SERIAL PRIMARY KEY,
            url TEXT NOT NULL,
            events JSON NOT NULL,
            enabled BOOLEAN NOT NULL DEFAULT true,
            created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            updated_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now()
        );
        """
    )

    # Create webhook_deliveries table if it doesn't exist
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_deliveries (
            id SERIAL PRIMARY KEY,
            webhook_id INTEGER NOT NULL,
            event_type TEXT NOT NULL,
            payload JSON NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            response_code INTEGER,
            response_body TEXT,
            response_time_ms INTEGER,
            attempted_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT now(),
            completed_at TIMESTAMP WITH TIME ZONE,
            CONSTRAINT fk_webhook_deliveries_webhook_id_webhooks 
                FOREIGN KEY (webhook_id) 
                REFERENCES webhooks(id) 
                ON DELETE CASCADE
        );
        """
    )

    # Create index if it doesn't exist
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_webhook_deliveries_webhook_id 
        ON webhook_deliveries (webhook_id);
        """
    )


def downgrade() -> None:
    # Drop tables in reverse order (deliveries first due to FK)
    op.drop_index("ix_webhook_deliveries_webhook_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_table("webhooks")

