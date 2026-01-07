"""
Database initialization script
"""
import asyncio
from sqlalchemy import text

from .database import engine, Base
from llm_app.models import user, file as file_model, task, content, statistics  # Import all models
from .migrations.add_is_favorite import migrate_add_is_favorite


async def init_db() -> None:
    """Initialize database - create all tables"""
    print("Initializing database...")

    # Run migrations before creating tables
    try:
        await migrate_add_is_favorite()
    except Exception as e:
        print(f"Warning: Migration failed (may be okay if column exists): {e}")

    async with engine.begin() as conn:
        # Create all tables
        await conn.run_sync(Base.metadata.create_all)
        print("✓ All tables created successfully")

        # Verify tables were created
        result = await conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
        tables = [row[0] for row in result.fetchall()]
        print(f"✓ Created tables: {', '.join(sorted(tables))}")


async def close_db() -> None:
    """Close database connections"""
    await engine.dispose()
    print("✓ Database connections closed")


async def reset_db() -> None:
    """Drop all tables and recreate (WARNING: destroys all data)"""
    print("WARNING: This will delete all data!")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        print("✓ All tables dropped")

    await init_db()


if __name__ == "__main__":
    asyncio.run(init_db())