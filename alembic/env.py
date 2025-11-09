from __future__ import annotations

import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import create_engine, pool

sys.path.append(".")

from app.core.config import settings  # noqa: E402

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

DATABASE_URL = settings.DATABASE_URL or ""

if not DATABASE_URL:
    raise RuntimeError(
        "DATABASE_URL is empty. Set it to a SQLAlchemy-style URL like:\n"
        "  postgresql+psycopg://user:pass@host:5432/dbname"
    )

config.set_main_option("sqlalchemy.url", DATABASE_URL)

connectable = create_engine(
    DATABASE_URL,
    poolclass=pool.NullPool,
    future=True,
)

def run_migrations_offline() -> None:
    context.configure(
        url=DATABASE_URL,
        target_metadata=None,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=None,
        )
        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
