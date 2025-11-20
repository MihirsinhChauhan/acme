#!/usr/bin/env python3
"""Startup script for Railway deployment.

This script ensures the database is migrated before starting the API or
Celery worker. It mirrors the Render startup helper but prints Railway-
specific logs for observability.
"""

import logging
import os
import sys
from pathlib import Path

# Allow imports from project root when executed from packaged image
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_migrations import main as run_migrations_main

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
)


def main() -> int:
    """Perform Railway startup tasks."""

    logger.info("=" * 60)
    logger.info("Railway Startup Script")
    logger.info("=" * 60)

    upload_dir = Path("/tmp/imports")
    upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info("✓ Upload directory ready at %s", upload_dir)

    logger.info("")
    logger.info("Running database migrations...")
    migration_exit_code = run_migrations_main()

    if migration_exit_code != 0:
        logger.error("Migrations failed. Exiting.")
        return 1

    # Log Railway environment info
    port = os.getenv("PORT", "8000")
    logger.info("")
    logger.info("Railway Environment:")
    logger.info("  PORT: %s", port)
    logger.info("  PYTHON_VERSION: %s", sys.version.split()[0])
    logger.info("=" * 60)
    logger.info("✓ Startup completed successfully")
    logger.info("=" * 60)

    return 0


if __name__ == "__main__":
    sys.exit(main())

