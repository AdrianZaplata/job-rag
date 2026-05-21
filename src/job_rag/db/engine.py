import os
from collections.abc import AsyncGenerator, Generator
from pathlib import Path

from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from alembic import command
from job_rag.config import settings

# Canonical seeded user UUID — must match config.py settings.seeded_user_id and the
# row inserted by alembic/versions/0002_add_user_profile.py. Duplicated from
# alembic/versions/0005_adopt_entra_oid.py so engine.py doesn't import from migrations.
SEEDED_USER_UUID = "00000000-0000-0000-0000-000000000001"

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


def _seed_entra_oid() -> None:
    """Idempotent post-alembic UPDATE — bridges Phase 1's seeded UUID to Adrian's
    real Entra oid when SEEDED_USER_ENTRA_OID is set in env. On empty/unset env
    (bootstrap-pending state), this is a no-op so container startup still succeeds.

    Phase 4 deviation #3 (SUMMARY) fix: this UPDATE used to live in
    alembic/versions/0005_adopt_entra_oid.py::upgrade(), where it only ran once per
    revision-marker. Moving it here makes it re-run on every container boot, so
    rotating SEEDED_USER_ENTRA_OID just needs an ACA restart.
    """
    oid = os.environ.get("SEEDED_USER_ENTRA_OID", "").strip()
    if not oid:
        return
    with engine.begin() as conn:
        conn.execute(
            text(
                "UPDATE users SET entra_oid = :oid "
                "WHERE id = :seeded_uuid AND (entra_oid IS NULL OR entra_oid != :oid)"
            ).bindparams(oid=oid, seeded_uuid=SEEDED_USER_UUID)
        )


def init_db() -> None:
    """Run all pending Alembic migrations to bring the DB up to head, then run
    idempotent post-alembic seeding (entra_oid bridge for the seeded user).

    Replaces the previous metadata-build + CREATE EXTENSION logic; Alembic is
    now the canonical schema path (D-04). The CREATE EXTENSION call moves into
    alembic/versions/0001_baseline.py. The entra_oid UPDATE moved out of
    0005_adopt_entra_oid.py into _seed_entra_oid() (Phase 04.1 fix 1).
    """
    # Walk: src/job_rag/db/engine.py -> src/job_rag/db/ -> src/job_rag/ -> src/ -> repo root.
    cfg = Config(str(Path(__file__).resolve().parents[3] / "alembic.ini"))
    configure_alembic_url(cfg, settings.database_url)
    command.upgrade(cfg, "head")
    _seed_entra_oid()
