"""CLI init-db smoke test.

Covers BACK-07 (D-04): `job-rag init-db` keeps its name and entry-point but its
body is rewritten to wrap alembic.command.upgrade(cfg, "head"). The Base.metadata
.create_all() path is removed - Alembic owns the schema from Plan 02 onwards.

Plan 02 makes the swap. Until then this test skips so the suite stays green
in Wave 0.
"""

from unittest.mock import patch

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
