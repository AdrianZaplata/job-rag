"""Alembic migration environment.

Wires pgvector's custom Vector type into the dialect's ischema_names
BEFORE context.configure() so autogenerate reflects it correctly.
"""

import os
from logging.config import fileConfig

import pgvector.sqlalchemy  # CRITICAL — registers Vector (Pitfall A)
from sqlalchemy import engine_from_config, pool

from alembic import context
from job_rag.db import models as _models  # noqa: F401 — side-effect import
from job_rag.db.engine import Base

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_online() -> None:
    """Run migrations against a live DB connection (NullPool per D-02)."""
    config.set_main_option("sqlalchemy.url", os.environ["DATABASE_URL"])
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        # Tell the dialect about pgvector BEFORE configure() — Pitfall A.
        # ischema_names lives on PostgresDialect at runtime but isn't on the
        # base Dialect interface pyright infers; suppress the false positive.
        connection.dialect.ischema_names["vector"] = pgvector.sqlalchemy.Vector  # pyright: ignore[reportAttributeAccessIssue]
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
            compare_server_default=True,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
