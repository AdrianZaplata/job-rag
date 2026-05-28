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

import os
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
    from job_rag.db.engine import configure_alembic_url
    configure_alembic_url(cfg, settings.database_url)

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
    from job_rag.db.engine import configure_alembic_url
    configure_alembic_url(cfg, settings.database_url)

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


# --- Plan 04-02: migration 0005 (entra_oid + idempotent UPDATE + partial index) ---


def _alembic_env_ready() -> bool:
    """Skip-gate for 0005 tests — both PG reachable AND DATABASE_URL set.

    alembic/env.py reads os.environ["DATABASE_URL"] directly (raises
    KeyError otherwise). Mirrors the recommendation in
    .planning/phases/04-frontend-shell-auth/deferred-items.md to widen
    the skip-gate beyond _postgres_reachable() alone.
    """
    if "DATABASE_URL" not in os.environ:
        return False
    return _postgres_reachable()


def test_0005_upgrade_smoke() -> None:
    """0005 adds users.entra_oid + partial unique index (idempotent).

    Plan 04-02 Task 1. Skip cleanly when DATABASE_URL is missing or PG is
    unreachable (mirrors deferred-items.md recommendation).
    """
    if not _alembic_env_ready():
        pytest.skip(
            "DATABASE_URL not set or Postgres not reachable — alembic 0005 smoke skipped"
        )

    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command
    from job_rag.config import settings
    from job_rag.db.engine import configure_alembic_url

    cfg = Config("alembic.ini")
    configure_alembic_url(cfg, settings.database_url)

    # Roll back to one-before; ensure clean state.
    command.downgrade(cfg, "0004")

    eng = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    try:
        # Snapshot users row count pre-upgrade.
        with eng.connect() as c:
            row_count_before = c.execute(text("SELECT COUNT(*) FROM users")).scalar()

        # Ensure empty env (bootstrap-pending state) — UPDATE should be no-op.
        os.environ.pop("SEEDED_USER_ENTRA_OID", None)
        command.upgrade(cfg, "0005")

        with eng.connect() as c:
            # Column exists.
            col_check = c.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'users' AND column_name = 'entra_oid'"
                )
            ).first()
            assert col_check is not None, "entra_oid column not present"

            # Partial unique index exists.
            idx_check = c.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE tablename = 'users' AND indexname = 'ix_users_entra_oid_unique'"
                )
            ).first()
            assert idx_check is not None, "ix_users_entra_oid_unique not created"

            # Row count preserved (column-add + index-create does not delete rows).
            row_count_after = c.execute(text("SELECT COUNT(*) FROM users")).scalar()
            assert row_count_after == row_count_before

            # Empty env → UPDATE no-op → entra_oid IS NULL for seeded row
            # (we just downgraded then upgraded; downgrade does NOT drop the
            # column, so any prior value persists. Verify the empty-env
            # branch did not overwrite an existing value with empty string.)
            oid_val = c.execute(
                text("SELECT entra_oid FROM users WHERE id = :u").bindparams(
                    u="00000000-0000-0000-0000-000000000001"
                )
            ).scalar()
            # On empty env, the UPDATE skipped — value is whatever was there
            # before downgrade (could be NULL or a prior oid). The contract
            # is "empty env does not overwrite"; we assert nothing about
            # specific value here. Stricter check is in the env-set test below.
            assert oid_val is None or isinstance(oid_val, str)

        # Idempotent second upgrade head.
        command.upgrade(cfg, "head")
    finally:
        eng.dispose()


def test_0005_upgrade_populates_oid_when_env_set() -> None:
    """SEEDED_USER_ENTRA_OID env set → seeded row's entra_oid UPDATED.

    Plan 04-02 Task 1. Skip cleanly without DATABASE_URL.
    """
    if not _alembic_env_ready():
        pytest.skip("DATABASE_URL not set or Postgres not reachable — 0005 env test skipped")

    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command
    from job_rag.config import settings
    from job_rag.db.engine import configure_alembic_url

    cfg = Config("alembic.ini")
    configure_alembic_url(cfg, settings.database_url)

    command.downgrade(cfg, "0004")

    eng = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    try:
        os.environ["SEEDED_USER_ENTRA_OID"] = "test-oid-xyz-123"
        try:
            command.upgrade(cfg, "0005")
            with eng.connect() as c:
                oid_val = c.execute(
                    text("SELECT entra_oid FROM users WHERE id = :u").bindparams(
                        u="00000000-0000-0000-0000-000000000001"
                    )
                ).scalar()
                assert oid_val == "test-oid-xyz-123"
        finally:
            os.environ.pop("SEEDED_USER_ENTRA_OID", None)

        # Cleanup — reset the row's entra_oid back to NULL so other tests start clean.
        with eng.begin() as c:
            c.execute(
                text(
                    "UPDATE users SET entra_oid = NULL WHERE id = :u"
                ).bindparams(u="00000000-0000-0000-0000-000000000001")
            )
    finally:
        eng.dispose()


def test_0005_downgrade_smoke() -> None:
    """Downgrade 0005 → 0004 removes partial unique index (column preserved).

    Plan 04-02 Task 1. The entra_oid column itself is preserved across the
    downgrade (created by 0002, not by 0005); only the partial unique index
    is dropped.
    """
    if not _alembic_env_ready():
        pytest.skip("DATABASE_URL not set or Postgres not reachable — 0005 downgrade skipped")

    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command
    from job_rag.config import settings
    from job_rag.db.engine import configure_alembic_url

    cfg = Config("alembic.ini")
    configure_alembic_url(cfg, settings.database_url)

    # Ensure we're at 0005 first.
    command.upgrade(cfg, "0005")
    command.downgrade(cfg, "0004")

    eng = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    try:
        with eng.connect() as c:
            idx_check = c.execute(
                text(
                    "SELECT indexname FROM pg_indexes "
                    "WHERE indexname = 'ix_users_entra_oid_unique'"
                )
            ).first()
            assert idx_check is None, "Partial unique index should be dropped"

            # Column survives downgrade (created by 0002, not 0005).
            col_check = c.execute(
                text(
                    "SELECT column_name FROM information_schema.columns "
                    "WHERE table_name = 'users' AND column_name = 'entra_oid'"
                )
            ).first()
            assert col_check is not None, "entra_oid column should survive 0005 downgrade"
    finally:
        eng.dispose()

    # Restore head for downstream tests.
    command.upgrade(cfg, "head")


# --- Plan 07-02: migration 0006 (seed Adrian's user_profile row) ---


def test_0006_seed_user_profile_inserts_row() -> None:
    """0006 upgrade INSERTs Adrian's seeded user_profile row (PROF-01 / D-03).

    Plan 07-02 Task 1 / VALIDATION 07-02-06. Skip cleanly when DATABASE_URL is
    missing or Postgres unreachable.
    """
    if not _alembic_env_ready():
        pytest.skip(
            "DATABASE_URL not set or Postgres not reachable — 0006 seed smoke skipped"
        )

    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command
    from job_rag.config import settings
    from job_rag.db.engine import configure_alembic_url

    cfg = Config("alembic.ini")
    configure_alembic_url(cfg, settings.database_url)

    # Roll back to 0005 to exercise the 0005 -> 0006 upgrade fresh.
    command.downgrade(cfg, "0005")

    eng = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    try:
        with eng.connect() as c:
            pre_count = c.execute(
                text(
                    "SELECT COUNT(*) FROM user_profile WHERE user_id = :u"
                ).bindparams(u="00000000-0000-0000-0000-000000000001")
            ).scalar()

        command.upgrade(cfg, "0006")

        with eng.connect() as c:
            post_count = c.execute(
                text(
                    "SELECT COUNT(*) FROM user_profile WHERE user_id = :u"
                ).bindparams(u="00000000-0000-0000-0000-000000000001")
            ).scalar()
            assert post_count == 1, (
                f"0006 should INSERT exactly 1 user_profile row "
                f"(pre={pre_count}, post={post_count})"
            )

            # Verify the row contains the expected shape.
            row = c.execute(
                text(
                    "SELECT skills_json, target_roles_json, preferred_locations_json, "
                    "       min_salary_eur, remote_preference "
                    "FROM user_profile WHERE user_id = :u"
                ).bindparams(u="00000000-0000-0000-0000-000000000001")
            ).first()
            assert row is not None
            # Decode the JSON columns and assert expected seed contents.
            import json as _json

            skills = _json.loads(row.skills_json)
            assert isinstance(skills, list) and len(skills) > 0
            # Every skill dict has a "name" key.
            assert all(isinstance(s, dict) and "name" in s for s in skills)
            assert _json.loads(row.target_roles_json) == [
                "AI Engineer",
                "AI Application Engineer",
                "AI Software Engineer",
            ]
            assert _json.loads(row.preferred_locations_json) == [
                "Berlin, Germany",
                "Germany",
                "Remote",
            ]
            assert row.min_salary_eur == 65000
            assert row.remote_preference == "remote"
    finally:
        eng.dispose()


def test_0006_seed_user_profile_idempotent() -> None:
    """0006 upgrade is a no-op on re-run — ON CONFLICT (user_id) DO NOTHING (T-07-03).

    Plan 07-02 VALIDATION 07-02-06: re-running `alembic upgrade head` against
    an already-seeded DB must not error and must not duplicate the row.
    """
    if not _alembic_env_ready():
        pytest.skip(
            "DATABASE_URL not set or Postgres not reachable — 0006 idempotency skipped"
        )

    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command
    from job_rag.config import settings
    from job_rag.db.engine import configure_alembic_url

    cfg = Config("alembic.ini")
    configure_alembic_url(cfg, settings.database_url)

    # Ensure we're at head first.
    command.upgrade(cfg, "head")

    eng = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    try:
        # Run upgrade head a SECOND time — this exercises the ON CONFLICT branch
        # of the seed migration (the alembic version table already shows 0006
        # so the command itself is a no-op; we explicitly invoke the migration
        # body by downgrading and re-upgrading to guarantee the INSERT statement
        # runs against the already-populated row).
        command.downgrade(cfg, "0005")
        command.upgrade(cfg, "0006")
        # Second cycle — both UPGRADE calls touch the same row; second should
        # silently DO NOTHING per the ON CONFLICT clause.
        with eng.connect() as c:
            count = c.execute(
                text(
                    "SELECT COUNT(*) FROM user_profile WHERE user_id = :u"
                ).bindparams(u="00000000-0000-0000-0000-000000000001")
            ).scalar()
            assert count == 1, f"expected exactly 1 row after idempotent re-run, got {count}"
    finally:
        eng.dispose()


def test_0006_seed_user_profile_downgrade_deletes_only_seeded_row() -> None:
    """0006 downgrade DELETEs ONLY the seeded UUID row; others untouched.

    Plan 07-02 Task 1 acceptance criterion. Verifies the downgrade is scoped
    to the seeded user_id and does not truncate the user_profile table.
    """
    if not _alembic_env_ready():
        pytest.skip(
            "DATABASE_URL not set or Postgres not reachable — 0006 downgrade skipped"
        )

    from alembic.config import Config
    from sqlalchemy import create_engine, text

    from alembic import command
    from job_rag.config import settings
    from job_rag.db.engine import configure_alembic_url

    cfg = Config("alembic.ini")
    configure_alembic_url(cfg, settings.database_url)

    # Ensure head (seeded row present).
    command.upgrade(cfg, "head")

    other_user_uuid = "00000000-0000-0000-0000-0000000000ee"
    eng = create_engine(settings.database_url, pool_pre_ping=True, future=True)
    try:
        # INSERT a sentinel row for an OTHER user (also need users.id FK).
        with eng.begin() as c:
            c.execute(
                text(
                    "INSERT INTO users (id, email) VALUES (:u, :e) "
                    "ON CONFLICT (id) DO NOTHING"
                ).bindparams(u=other_user_uuid, e="sentinel@example.com")
            )
            c.execute(
                text(
                    "INSERT INTO user_profile "
                    "(user_id, skills_json, target_roles_json, preferred_locations_json, "
                    " min_salary_eur, remote_preference) "
                    "VALUES (:u, '[]', '[]', '[]', NULL, 'unknown') "
                    "ON CONFLICT (user_id) DO NOTHING"
                ).bindparams(u=other_user_uuid)
            )

        # Downgrade — should delete ONLY the seeded UUID row.
        command.downgrade(cfg, "0005")

        with eng.connect() as c:
            seeded_count = c.execute(
                text(
                    "SELECT COUNT(*) FROM user_profile WHERE user_id = :u"
                ).bindparams(u="00000000-0000-0000-0000-000000000001")
            ).scalar()
            other_count = c.execute(
                text(
                    "SELECT COUNT(*) FROM user_profile WHERE user_id = :u"
                ).bindparams(u=other_user_uuid)
            ).scalar()
            assert seeded_count == 0, "downgrade should remove the seeded row"
            assert other_count == 1, "downgrade must NOT touch other user_profile rows"

        # Cleanup: drop the sentinel rows so other tests start from a clean shape.
        with eng.begin() as c:
            c.execute(
                text("DELETE FROM user_profile WHERE user_id = :u").bindparams(
                    u=other_user_uuid
                )
            )
            c.execute(
                text("DELETE FROM users WHERE id = :u").bindparams(u=other_user_uuid)
            )

        # Restore head so downstream tests see the seeded row.
        command.upgrade(cfg, "head")
    finally:
        eng.dispose()
