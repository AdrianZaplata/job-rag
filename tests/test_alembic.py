"""CI grep-guard test - no DDL DEFAULT on user_id columns + 0004 smoke tests.

Enforces decisions D-08 (hardcoded SEEDED_USER_ID, no random uuid_generate_v4()
DEFAULT in migrations) and D-12 (CI grep guard prevents Pitfall 18 regression:
silent multi-user collision when two requests both fall through to a
DEFAULT-generated UUID).

This test is intentionally a no-op until Plan 02 lands the first migration.
After that, it actively scans every file in alembic/versions/ for the forbidden
pattern and fails loudly if found. Belt-and-suspenders: a workflow-level grep
step in CI also runs the same check (RESEARCH §"CI grep guard" lines 1118-1145).

Phase 2 Plan 03 adds test_0004_upgrade_smoke + test_0004_downgrade_smoke that
exercise the full migration cycle against a live Postgres (skip cleanly when
DATABASE_URL is unreachable).
"""

import re
from pathlib import Path

import pytest

# Match either:
#   - DDL "DEFAULT '<uuid>'::uuid" (raw SQL inside op.execute or sa.text)
#   - SQLAlchemy "server_default=...uuid..." (inside op.add_column / op.create_table)
DEFAULT_UUID_PATTERN = re.compile(
    r"DEFAULT.*['\"]?[0-9a-f-]{36}['\"]?.*::?uuid|"
    r"server_default\s*=.*[Uu][Uu][Ii][Dd]",
    re.IGNORECASE,
)


def test_no_default_uuid_on_user_id_columns():
    """No Alembic migration may add a DDL DEFAULT to a user_id column."""
    versions_dir = Path(__file__).parent.parent / "alembic" / "versions"
    if not versions_dir.exists():
        # Plan 02 hasn't run yet - test is a no-op; passes trivially. As soon as
        # Plan 02 commits the baseline migration, this branch is bypassed and
        # the scanner below activates.
        return
    bad_files: list[tuple[Path, int, str]] = []
    for migration in versions_dir.glob("*.py"):
        for lineno, line in enumerate(migration.read_text().splitlines(), 1):
            if "user_id" in line and DEFAULT_UUID_PATTERN.search(line):
                bad_files.append((migration, lineno, line.strip()))
    assert not bad_files, (
        "Migrations adding DEFAULT to user_id columns:\n"
        + "\n".join(f"  {p.name}:{n}: {line}" for p, n, line in bad_files)
    )


def _postgres_reachable() -> bool:
    """Helper: returns True if DATABASE_URL points to a reachable Postgres."""
    try:
        from sqlalchemy import create_engine, text

        from job_rag.config import settings
        eng = create_engine(settings.database_url, pool_pre_ping=True, future=True)
        with eng.connect() as c:
            c.execute(text("SELECT 1"))
        eng.dispose()
        return True
    except Exception:
        return False


def test_0004_upgrade_smoke():
    """[BLOCKING per Phase 2 plan 03] alembic upgrade 0003->0004 preserves data
    and produces the new schema. Skips if no Postgres reachable.
    """
    if not _postgres_reachable():
        pytest.skip(
            "Postgres not reachable - alembic smoke skipped "
            "(run docker-compose up postgres)"
        )

    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command
    from job_rag.config import settings

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    # Ensure we're at 0003 to exercise the upgrade path. If already at 0004 (or
    # later), this rolls back to 0003 first.
    command.downgrade(cfg, "0003")

    eng = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    try:
        # Snapshot row counts before upgrade.
        with eng.connect() as c:
            pre_req = c.execute(text("SELECT COUNT(*) FROM job_requirements")).scalar()
            pre_post = c.execute(text("SELECT COUNT(*) FROM job_postings")).scalar()

        # Run the upgrade we care about.
        command.upgrade(cfg, "0004")

        with eng.connect() as c:
            post_req = c.execute(text("SELECT COUNT(*) FROM job_requirements")).scalar()
            post_post = c.execute(text("SELECT COUNT(*) FROM job_postings")).scalar()

            # Row counts unchanged (rename + add column do not delete rows).
            assert post_req == pre_req
            assert post_post == pre_post

            # Schema shape verified.
            cols = {r[0] for r in c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='job_requirements'"
            )).all()}
            assert "skill_type" in cols
            assert "skill_category" in cols
            assert "category" not in cols

            cols_p = {r[0] for r in c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='job_postings'"
            )).all()}
            assert "location_country" in cols_p
            assert "location_city" in cols_p
            assert "location_region" in cols_p
            assert "location" not in cols_p

            # All existing rows have non-null skill_category (backfill ran).
            if pre_req and pre_req > 0:
                nulls = c.execute(text(
                    "SELECT COUNT(*) FROM job_requirements WHERE skill_category IS NULL"
                )).scalar()
                assert nulls == 0, f"backfill left {nulls} NULL rows"

            # Indexes present.
            idxs = {r[0] for r in c.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename='job_requirements'"
            )).all()}
            assert "ix_job_requirements_skill_type" in idxs
            assert "ix_job_requirements_skill_category" in idxs
            assert "ix_job_requirements_category" not in idxs

            idxs_p = {r[0] for r in c.execute(text(
                "SELECT indexname FROM pg_indexes WHERE tablename='job_postings'"
            )).all()}
            assert "ix_job_postings_location_country" in idxs_p
    finally:
        eng.dispose()


def test_0004_downgrade_smoke():
    """alembic downgrade 0004->0003 reverses the schema (data may be in nullable
    shape -- ack'd in 0004 downgrade docstring). Skips if no Postgres."""
    if not _postgres_reachable():
        pytest.skip("Postgres not reachable - alembic downgrade smoke skipped")

    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command
    from job_rag.config import settings

    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", settings.database_url)

    # Ensure we're at 0004 (upgrade smoke ran first or DB is at head).
    command.upgrade(cfg, "0004")

    # Now exercise the downgrade.
    command.downgrade(cfg, "0003")

    eng = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    try:
        with eng.connect() as c:
            cols = {r[0] for r in c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='job_requirements'"
            )).all()}
            # Rename reversed.
            assert "category" in cols
            assert "skill_type" not in cols
            assert "skill_category" not in cols

            cols_p = {r[0] for r in c.execute(text(
                "SELECT column_name FROM information_schema.columns "
                "WHERE table_name='job_postings'"
            )).all()}
            assert "location" in cols_p
            assert "location_country" not in cols_p
    finally:
        eng.dispose()

    # Restore to head so the rest of the suite runs against current schema.
    command.upgrade(cfg, "head")
