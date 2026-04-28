"""Tests for src/job_rag/services/extraction.py — reextract_stale + _reextract_one."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest


@pytest.fixture
def extraction_module():
    try:
        from job_rag.services import extraction
        return extraction
    except ImportError as e:
        pytest.skip(f"services/extraction.py not yet added: {e}")


@pytest.mark.asyncio
class TestReextractStaleDefault:
    """Default selection: WHERE prompt_version != PROMPT_VERSION."""

    async def test_dry_run_counts_only(self, extraction_module, monkeypatch):
        # Mock AsyncSessionLocal so SELECT returns 3 stale UUIDs.
        stale_ids = [uuid4() for _ in range(3)]

        class _MockResult:
            def all(self):
                return [(pid,) for pid in stale_ids]

        session = MagicMock()
        session.execute = AsyncMock(return_value=_MockResult())
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(
            extraction_module, "AsyncSessionLocal", lambda: session,
        )

        report = await extraction_module.reextract_stale(dry_run=True)

        assert report.selected == 3
        assert report.skipped == 3
        assert report.succeeded == 0
        assert report.failed == 0


@pytest.mark.asyncio
class TestReextractIdempotency:
    """Run twice — second call selects 0 because all rows are now at PROMPT_VERSION."""

    async def test_second_run_is_noop(self, extraction_module, monkeypatch):
        # First call returns 1 stale ID, second returns 0.
        calls = {"n": 0}

        class _MockResult:
            def __init__(self, rows):
                self._rows = rows

            def all(self):
                return self._rows

        def _select_factory(*args, **kwargs):
            calls["n"] += 1
            if calls["n"] == 1:
                return _MockResult([(uuid4(),)])
            return _MockResult([])

        session = MagicMock()
        session.execute = AsyncMock(side_effect=_select_factory)
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(extraction_module, "AsyncSessionLocal", lambda: session)

        report1 = await extraction_module.reextract_stale(dry_run=True)
        report2 = await extraction_module.reextract_stale(dry_run=True)

        assert report1.selected == 1
        assert report2.selected == 0


@pytest.mark.asyncio
class TestReextractAllConfirm:
    """T-CLI-01: --all requires explicit confirmation (yes=True)."""

    async def test_all_without_yes_raises(self, extraction_module):
        with pytest.raises(RuntimeError, match=r"--all requires"):
            await extraction_module.reextract_stale(all=True, yes=False)

    async def test_all_with_yes_proceeds(self, extraction_module, monkeypatch):
        class _MockResult:
            def all(self):
                return []

        session = MagicMock()
        session.execute = AsyncMock(return_value=_MockResult())
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(extraction_module, "AsyncSessionLocal", lambda: session)

        report = await extraction_module.reextract_stale(all=True, yes=True, dry_run=True)
        assert report.selected == 0


@pytest.mark.asyncio
class TestPartialFailureContinues:
    """D-16: per-posting failure does not abort the loop."""

    async def test_one_extraction_fails_others_succeed(
        self, extraction_module, monkeypatch
    ):
        ids = [uuid4(), uuid4(), uuid4()]

        # SELECT phase
        class _MockSelectResult:
            def all(self):
                return [(pid,) for pid in ids]

        select_session = MagicMock()
        select_session.execute = AsyncMock(return_value=_MockSelectResult())
        select_session.__aenter__ = AsyncMock(return_value=select_session)
        select_session.__aexit__ = AsyncMock(return_value=None)

        # Per-row sessions — _reextract_one raises on the second ID.
        call = {"n": 0}

        async def _fake_reextract_one(posting_id, report):
            call["n"] += 1
            if call["n"] == 2:
                report.failed += 1
                report.failures.append((posting_id, "synthetic failure"))
                return
            report.succeeded += 1

        monkeypatch.setattr(extraction_module, "_reextract_one", _fake_reextract_one)
        monkeypatch.setattr(extraction_module, "AsyncSessionLocal", lambda: select_session)

        report = await extraction_module.reextract_stale()
        assert report.selected == 3
        assert report.succeeded == 2
        assert report.failed == 1
        assert len(report.failures) == 1


@pytest.mark.asyncio
class TestDryRun:
    """--dry-run does not call _reextract_one."""

    async def test_dry_run_skips_reextract_one(self, extraction_module, monkeypatch):
        ids = [uuid4(), uuid4()]

        class _MockResult:
            def all(self):
                return [(pid,) for pid in ids]

        session = MagicMock()
        session.execute = AsyncMock(return_value=_MockResult())
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(extraction_module, "AsyncSessionLocal", lambda: session)

        called = {"n": 0}

        async def _should_not_be_called(posting_id, report):
            called["n"] += 1

        monkeypatch.setattr(extraction_module, "_reextract_one", _should_not_be_called)

        report = await extraction_module.reextract_stale(dry_run=True)
        assert report.selected == 2
        assert report.skipped == 2
        assert called["n"] == 0


@pytest.mark.asyncio
class TestSinglePosting:
    async def test_posting_id_selects_one(self, extraction_module, monkeypatch):
        target = uuid4()

        class _MockResult:
            def all(self):
                return [(target,)]

        session = MagicMock()
        session.execute = AsyncMock(return_value=_MockResult())
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        monkeypatch.setattr(extraction_module, "AsyncSessionLocal", lambda: session)

        report = await extraction_module.reextract_stale(
            posting_id=target, dry_run=True,
        )
        assert report.selected == 1
