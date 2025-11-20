#!/usr/bin/env python3
"""Startup script for Render deployment.

This script runs database migrations before starting the service.
It's designed to work in Render's non-Docker environment.
"""
import logging
import sys
from pathlib import Path

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.run_migrations import main as run_migrations_main

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
)


def main() -> int:
    """Run startup tasks for Render deployment.
    
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    logger.info("=" * 60)
    logger.info("Render Startup Script")
    logger.info("=" * 60)
    
    # Create upload directory if it doesn't exist
    upload_dir = Path("/tmp/imports")
    upload_dir.mkdir(parents=True, exist_ok=True)
    logger.info(f"✓ Upload directory ready: {upload_dir}")
    
    # Run database migrations
    logger.info("")
    logger.info("Running database migrations...")
    migration_exit_code = run_migrations_main()
    
    if migration_exit_code != 0:
        logger.error("Migrations failed. Exiting.")
        return 1
    
    logger.info("=" * 60)
    logger.info("✓ Startup completed successfully")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

