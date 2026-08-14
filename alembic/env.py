"""Alembic environment for explicit runtime-schema migrations."""

from __future__ import annotations

from sqlalchemy import engine_from_config, pool

from alembic import context

config = context.config


def run_migrations_offline() -> None:
    """Run migrations without an active database connection."""
    context.configure(url=config.get_main_option("sqlalchemy.url"), literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations through the configured application database URL."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}), prefix="sqlalchemy.", poolclass=pool.NullPool
    )
    with connectable.connect() as connection:
        context.configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
