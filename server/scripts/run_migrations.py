#!/usr/bin/env python3
"""Run Alembic migrations on application startup.

This script ensures the database schema is up-to-date before starting
the API server or Celery workers.
"""
import logging
import sys
import time
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

# Add parent directory to path so we can import app modules
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s - %(message)s",
)


def wait_for_db(database_url: str, max_retries: int = 30, retry_interval: int = 2) -> bool:
    """Wait for database to become available.
    
    Args:
        database_url: SQLAlchemy database URL
        max_retries: Maximum number of connection attempts
        retry_interval: Seconds to wait between retries
        
    Returns:
        True if database is available, False otherwise
    """
    logger.info("Waiting for database to become available...")
    
    engine = create_engine(database_url, pool_pre_ping=True)
    
    for attempt in range(1, max_retries + 1):
        try:
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            logger.info("✓ Database connection established")
            engine.dispose()
            return True
        except OperationalError as e:
            if attempt == max_retries:
                logger.error(f"✗ Failed to connect to database after {max_retries} attempts")
                logger.error(f"  Error: {e}")
                engine.dispose()
                return False
            
            logger.warning(f"  Attempt {attempt}/{max_retries} failed, retrying in {retry_interval}s...")
            time.sleep(retry_interval)
    
    engine.dispose()
    return False


def run_migrations() -> bool:
    """Run Alembic migrations to upgrade database to latest version.
    
    Returns:
        True if migrations succeeded, False otherwise
    """
    try:
        # Get alembic.ini path (in project root)
        alembic_ini_path = Path(__file__).parent.parent / "alembic.ini"
        
        if not alembic_ini_path.exists():
            logger.error(f"✗ Alembic config not found at {alembic_ini_path}")
            return False
        
        # Load Alembic configuration
        alembic_cfg = Config(str(alembic_ini_path))
        
        # Override database URL from environment
        settings = get_settings()
        alembic_cfg.set_main_option("sqlalchemy.url", settings.database_url)
        
        logger.info("Running Alembic migrations to 'head'...")
        logger.info("  Config: %s", alembic_ini_path)
        
        # Check current database revision before migrating
        try:
            engine = create_engine(settings.database_url, pool_pre_ping=True)
            with engine.connect() as conn:
                # Check if alembic_version table exists
                result = conn.execute(text(
                    "SELECT EXISTS (SELECT FROM information_schema.tables "
                    "WHERE table_schema = 'public' AND table_name = 'alembic_version')"
                ))
                table_exists = result.scalar()
                
                if table_exists:
                    result = conn.execute(text("SELECT version_num FROM alembic_version"))
                    current_rev = result.scalar()
                    logger.info("  Current database revision: %s", current_rev)
                else:
                    logger.info("  Database not yet migrated (alembic_version table missing)")
            
            engine.dispose()
        except Exception as e:
            logger.warning(f"  Could not check current revision: {e}")
        
        # List available migrations
        try:
            from alembic.script import ScriptDirectory
            script = ScriptDirectory.from_config(alembic_cfg)
            logger.info("  Available migrations:")
            for rev in script.walk_revisions():
                logger.info("    - %s: %s", rev.revision, rev.doc)
        except Exception as e:
            logger.warning(f"  Could not list migrations: {e}")
        
        # Run migrations to head (latest version)
        logger.info("  Executing upgrade command...")
        command.upgrade(alembic_cfg, "head")
        
        logger.info("✓ Migrations completed successfully")
        return True
        
    except Exception as e:
        logger.error(f"✗ Migration failed: {e}", exc_info=True)
        return False


def main() -> int:
    """Main entry point for migration script.
    
    Returns:
        Exit code (0 = success, 1 = failure)
    """
    logger.info("=" * 60)
    logger.info("Starting Database Migration Process")
    logger.info("=" * 60)
    
    settings = get_settings()
    
    # Step 1: Wait for database to be ready
    if not wait_for_db(settings.database_url):
        logger.error("Database is not available. Exiting.")
        return 1
    
    # Step 2: Run migrations
    if not run_migrations():
        logger.error("Migrations failed. Exiting.")
        return 1
    
    logger.info("=" * 60)
    logger.info("✓ Migration Process Completed Successfully")
    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(main())

