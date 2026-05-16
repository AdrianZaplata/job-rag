from collections.abc import AsyncGenerator, Generator
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from alembic import command
from job_rag.config import settings

# Sync engine (CLI commands) — keeps default pool (CLI is single-process).
engine = create_engine(settings.database_url, echo=False)
SessionLocal = sessionmaker(bind=engine)

# Async engine (FastAPI) — D-29 pool sizing for B1ms Postgres compat.
# pool_size=3 + max_overflow=2 caps concurrent conns per worker at 5;
# pool_pre_ping detects stale conns dropped by Azure firewall;
# pool_recycle=300s rotates conns before Azure's idle-kill window.
async_engine = create_async_engine(
    settings.async_database_url,
    echo=False,
    pool_size=3,
    max_overflow=2,
    pool_pre_ping=True,
    pool_recycle=300,
)
AsyncSessionLocal = async_sessionmaker(bind=async_engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_session() -> Generator[Session, None, None]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        yield session


def configure_alembic_url(cfg: Config, url: str) -> None:
    """Set sqlalchemy.url on an alembic Config, escaping % for ConfigParser.

    Alembic's set_main_option() uses ConfigParser, which validates that the
    value is interpolation-safe. URL-encoded chars in a password (e.g. & → %26)
    look like unfinished %(name)s substitutions and raise InterpolationSyntaxError.
    Doubling % to %% lets ConfigParser interpolate it back to a single %, which
    SQLAlchemy then URL-decodes correctly.
    """
    cfg.set_main_option("sqlalchemy.url", url.replace("%", "%%"))


def init_db() -> None:
    """Run all pending Alembic migrations to bring the DB up to head.

    Replaces the previous metadata-build + CREATE EXTENSION logic; Alembic is
    now the canonical schema path (D-04). The CREATE EXTENSION call moves into
    alembic/versions/0001_baseline.py.
    """
    # Walk: src/job_rag/db/engine.py -> src/job_rag/db/ -> src/job_rag/ -> src/ -> repo root.
    cfg = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    configure_alembic_url(cfg, settings.database_url)
    command.upgrade(cfg, "head")
