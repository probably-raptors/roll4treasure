from __future__ import annotations

import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

# this is the Alembic Config object, which provides access to the values within the .ini file
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Pull DATABASE_URL from env (pydantic-settings writes into os.environ at process start)
DATABASE_URL = os.environ.get("DATABASE_URL", "")

if not DATABASE_URL:
    # Fallback: read from alembic.ini interpolation
    DATABASE_URL = config.get_main_option("sqlalchemy.url")

# Use SQLAlchemy engine in synchronous mode for migrations
connectable = create_engine(
    DATABASE_URL,
    poolclass=pool.NullPool,
    future=True,
)

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""
    url = DATABASE_URL
    context.configure(
        url=url,
        target_metadata=None,  # no autogenerate; we write migrations explicitly
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,  # no autogenerate
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
