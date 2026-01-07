"""
Database migration to add is_favorite column to files table.

This migration safely adds the is_favorite boolean field to the existing
files table without losing any data.
"""
import logging
from sqlalchemy import text, inspect
from llm_app.db.database import engine
from llm_app.core.logger import get_logger

logger = get_logger(__name__)


async def check_column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in the table"""
    async with engine.connect() as conn:
        inspector = inspect(engine.sync_engine if hasattr(engine, 'sync_engine') else engine)
        columns = [col['name'] for col in inspector.get_columns(table_name)]
        return column_name in columns


async def migrate_add_is_favorite():
    """
    Add is_favorite column to files table.

    This migration:
    1. Checks if is_favorite column exists
    2. Adds the column if missing using ALTER TABLE
    3. Sets default value to False for existing rows
    4. Creates index for performance
    """
    try:
        # Check if column already exists
        column_exists = await check_column_exists('files', 'is_favorite')

        if column_exists:
            logger.info("Migration: is_favorite column already exists in files table, skipping")
            return

        # Add is_favorite column
        async with engine.begin() as conn:
            # Add the column with default value False
            await conn.execute(text(
                "ALTER TABLE files ADD COLUMN is_favorite BOOLEAN NOT NULL DEFAULT 0"
            ))
            logger.info("Migration: Added is_favorite column to files table")

            # Create index for performance
            await conn.execute(text(
                "CREATE INDEX IF NOT EXISTS ix_files_is_favorite ON files(is_favorite)"
            ))
            logger.info("Migration: Created index ix_files_is_favorite")

        logger.info("✅ Migration add_is_favorite completed successfully")

    except Exception as e:
        logger.error(f"❌ Migration add_is_favorite failed: {str(e)}")
        raise


async def rollback_add_is_favorite():
    """
    Rollback the is_favorite column addition.

    WARNING: This will remove the is_favorite column and all favorite data.
    """
    try:
        async with engine.begin() as conn:
            # Drop index if exists
            await conn.execute(text("DROP INDEX IF EXISTS ix_files_is_favorite"))
            logger.info("Rollback: Dropped index ix_files_is_favorite")

            # Drop column
            await conn.execute(text("ALTER TABLE files DROP COLUMN is_favorite"))
            logger.info("Rollback: Dropped is_favorite column from files table")

        logger.info("✅ Rollback add_is_favorite completed successfully")

    except Exception as e:
        logger.error(f"❌ Rollback add_is_favorite failed: {str(e)}")
        raise
