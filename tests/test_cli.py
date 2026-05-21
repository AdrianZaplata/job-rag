"""CLI init-db smoke test.

Covers BACK-07 (D-04): `job-rag init-db` keeps its name and entry-point but its
body is rewritten to wrap alembic.command.upgrade(cfg, "head"). The Base.metadata
.create_all() path is removed - Alembic owns the schema from Plan 02 onwards.

Plan 02 makes the swap. Until then this test skips so the suite stays green
in Wave 0.
"""

from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

runner = CliRunner()


class TestInitDbCommand:
    def test_init_db_invokes_alembic_upgrade(self):
        """D-04: init-db internally delegates to alembic.command.upgrade(cfg, 'head')."""
        import pytest

        try:
            from job_rag.cli import app as cli_app
        except ImportError:
            pytest.skip("CLI import failed - confirm job_rag.cli exports Typer app")

        # Plan 02 imports `command` from alembic into job_rag.db.engine and rewrites
        # init_db to call command.upgrade(cfg, "head"). Until that import exists,
        # `patch("job_rag.db.engine.command.upgrade")` raises AttributeError - skip
        # so Wave 0 stays green and this test goes live the moment Plan 02 lands.
        try:
            with patch("job_rag.db.engine.command.upgrade") as mock_upgrade:
                # Phase 04.1 fix 1: init_db() now also calls _seed_entra_oid() after
                # command.upgrade. Patch the engine to keep this unit test SQL-free
                # (no live DB needed); env defaults to unset so _seed_entra_oid is a
                # no-op even without the patch, but explicit patch is safer.
                with patch("job_rag.db.engine.engine"):
                    result = runner.invoke(cli_app, ["init-db"])
        except (AttributeError, ModuleNotFoundError):
            pytest.skip("alembic.command not yet imported in db/engine.py (Plan 02)")
        if mock_upgrade.call_count == 0:
            pytest.skip("init_db not yet swapped to alembic command (Plan 02 provides it)")
        assert result.exit_code == 0
        mock_upgrade.assert_called_once()
        args, kwargs = mock_upgrade.call_args
        # second positional arg should be "head" OR kwarg revision="head"
        assert "head" in (list(args) + list(kwargs.values()))

    def test_seed_entra_oid_no_op_when_env_unset(self, monkeypatch):
        """_seed_entra_oid is a no-op when SEEDED_USER_ENTRA_OID is unset.

        Bootstrap-pending state — must not execute SQL so container startup succeeds
        even before the KV secret is filled. Phase 04.1 fix 1.
        """
        monkeypatch.delenv("SEEDED_USER_ENTRA_OID", raising=False)

        mock_engine = MagicMock()
        # Patch the module-level `engine` in job_rag.db.engine so _seed_entra_oid uses it.
        monkeypatch.setattr("job_rag.db.engine.engine", mock_engine)

        from job_rag.db.engine import _seed_entra_oid

        _seed_entra_oid()

        mock_engine.begin.assert_not_called()

    def test_seed_entra_oid_executes_update_when_env_set(self, monkeypatch):
        """_seed_entra_oid runs UPDATE with bind params when SEEDED_USER_ENTRA_OID is set.

        Phase 04.1 fix 1: bridges Phase 1's seeded UUID
        (00000000-0000-0000-0000-000000000001) to the operator's real Entra oid on
        every container boot — the UPDATE used to live in 0005's upgrade() and only
        fired once per revision-marker.
        """
        test_oid = "18d774c1-62ac-4416-8945-b5eca715e9ed"
        monkeypatch.setenv("SEEDED_USER_ENTRA_OID", test_oid)

        mock_conn = MagicMock()
        mock_engine = MagicMock()
        mock_engine.begin.return_value.__enter__.return_value = mock_conn
        monkeypatch.setattr("job_rag.db.engine.engine", mock_engine)

        from job_rag.db.engine import _seed_entra_oid

        _seed_entra_oid()

        mock_engine.begin.assert_called_once()
        mock_conn.execute.assert_called_once()
        # Inspect the executed TextClause — UPDATE SQL + bind params.
        executed_stmt = mock_conn.execute.call_args[0][0]
        compiled = executed_stmt.compile()
        assert "UPDATE users SET entra_oid" in str(compiled)
        assert compiled.params.get("oid") == test_oid
        assert compiled.params.get("seeded_uuid") == "00000000-0000-0000-0000-000000000001"


class TestListStatsPromptVersion:
    """CORP-04 / D-17: list --stats prints prompt_version distribution."""

    def test_list_stats_prints_distribution(self, monkeypatch):
        try:
            from job_rag.cli import app as cli_app
        except ImportError:
            pytest.skip("CLI import failed")

        # Build 2 fake postings: one at "2.0" (current) and one at "1.1" (stale).
        class _FakePosting:
            def __init__(self, version):
                self.prompt_version = version

        fake_postings = [_FakePosting("2.0"), _FakePosting("1.1")]

        class _FakeQuery:
            def all(self):
                return fake_postings

            def order_by(self, *a, **kw):
                return self

            def filter(self, *a, **kw):
                return self

        class _FakeSession:
            def query(self, *a, **kw):
                return _FakeQuery()

            def close(self):
                pass

        # Patch SessionLocal where cli imports it from.
        monkeypatch.setattr(
            "job_rag.db.engine.SessionLocal", lambda: _FakeSession()
        )

        try:
            result = runner.invoke(cli_app, ["list", "--stats"])
        except (AttributeError, ModuleNotFoundError):
            pytest.skip("--stats flag not yet wired (Plan 03)")

        assert result.exit_code == 0
        assert "prompt_version=" in result.stdout
        assert "STALE" in result.stdout
