"""IngestionSource Protocol + MarkdownFileSource tests.

Covers BACK-10 (D-20 Protocol shape with __aiter__, D-21 frozen RawPosting
dataclass, D-22 service-side content_hash, D-23 same-module location,
D-24 ingest_from_source consumer + sync ingest_file compat).

Plan 03 lands the Protocol, the dataclass, and MarkdownFileSource. Until then
each test guards behind hasattr() and pytest.skip().
"""

from pathlib import Path

import pytest


@pytest.fixture
def ingestion_module():
    try:
        from job_rag.services import ingestion

        return ingestion
    except ImportError as e:
        pytest.skip(f"services/ingestion.py missing Plan 03 additions: {e}")


class TestIngestionSourceProtocol:
    def test_markdown_file_source_satisfies_protocol(
        self, tmp_path: Path, ingestion_module
    ):
        """BACK-10: isinstance check on runtime_checkable Protocol (D-20)."""
        if not hasattr(ingestion_module, "MarkdownFileSource"):
            pytest.skip("MarkdownFileSource not yet added (Plan 03 provides it)")
        src = ingestion_module.MarkdownFileSource(tmp_path)
        assert isinstance(src, ingestion_module.IngestionSource)

    def test_raw_posting_is_frozen_dataclass(self, ingestion_module):
        """BACK-10: RawPosting is frozen (D-21) - no in-place mutation allowed."""
        from dataclasses import FrozenInstanceError
        from datetime import datetime

        if not hasattr(ingestion_module, "RawPosting"):
            pytest.skip("RawPosting not yet added")
        rp = ingestion_module.RawPosting(
            raw_text="x",
            source_url="file:///a",
            source_id=None,
            fetched_at=datetime.now(),
        )
        with pytest.raises(FrozenInstanceError):
            rp.raw_text = "y"  # type: ignore[misc]


@pytest.mark.asyncio
class TestMarkdownFileSource:
    async def test_markdown_file_source_yields(self, tmp_path: Path, ingestion_module):
        """BACK-10: MarkdownFileSource yields one RawPosting per .md file (D-20).

        source_id must be set to the LinkedIn job-id when one is present in
        the file body (regex extraction); None otherwise.
        """
        if not hasattr(ingestion_module, "MarkdownFileSource"):
            pytest.skip("MarkdownFileSource not yet added")
        (tmp_path / "a.md").write_text("# A\nhttps://linkedin.com/jobs/view/12345/\n")
        (tmp_path / "b.md").write_text("# B\nNo linkedin URL here\n")
        src = ingestion_module.MarkdownFileSource(tmp_path)
        items = [rp async for rp in src]
        assert len(items) == 2
        # Order is deterministic (sorted by name) - 'a.md' first
        assert items[0].source_id == "12345"
        assert items[1].source_id is None


@pytest.mark.asyncio
class TestIngestFromSource:
    """ingest_from_source unit tests — DB layer + LLM mocked.

    These exercise the consumer's contract (counts, posting_ids, error capture,
    dedup-on-second-run) without spinning up a real Postgres or calling OpenAI.
    The full DB-integration path is exercised by the CLI smoke flow
    (`job-rag ingest data/postings/`) and Plan 06's /ingest tests.
    """

    @staticmethod
    def _make_posting():
        """Minimal valid JobPosting for mock extraction returns."""
        from job_rag.models import (
            JobPosting,
            JobRequirement,
            RemotePolicy,
            SalaryPeriod,
            Seniority,
            SkillCategory,
        )

        return JobPosting(
            title="AI Engineer",
            company="ACME",
            location="Berlin",
            remote_policy=RemotePolicy.REMOTE,
            salary_min=70000,
            salary_max=90000,
            salary_raw="70k-90k EUR",
            salary_period=SalaryPeriod.YEAR,
            seniority=Seniority.MID,
            employment_type="full-time",
            requirements=[
                JobRequirement(
                    skill="Python", category=SkillCategory.LANGUAGE, required=True
                )
            ],
            responsibilities=["Build RAG pipelines"],
            benefits=["Remote-friendly"],
            source_url="https://example.com/job/1",
            raw_text="placeholder",
        )

    async def test_ingest_from_source_roundtrip(
        self, tmp_path, ingestion_module, monkeypatch
    ):
        """BACK-10: ingest_from_source returns IngestResult with expected counts
        and posting_ids on the happy path (D-24). DB layer + LLM mocked."""
        if not hasattr(ingestion_module, "ingest_from_source"):
            pytest.skip("ingest_from_source not yet added (Plan 03)")

        from unittest.mock import AsyncMock, MagicMock

        # Two markdown files, both yielding new RawPosting objects
        (tmp_path / "a.md").write_text(
            "# A\nhttps://linkedin.com/jobs/view/100/\n"
        )
        (tmp_path / "b.md").write_text("# B\nNo linkedin URL\n")

        # Mock the DB-touching helpers and the LLM
        async def _exists(*args, **kwargs):
            return False

        store_calls = {"n": 0}

        async def _store(session, posting, c_hash, linkedin_id):
            store_calls["n"] += 1
            db = MagicMock()
            db.id = f"posting-{store_calls['n']}"
            return db

        async def _embed(session, db_posting):
            return None

        monkeypatch.setattr(ingestion_module, "_posting_exists_async", _exists)
        monkeypatch.setattr(ingestion_module, "_store_posting_async", _store)
        monkeypatch.setattr(ingestion_module, "_embed_and_store_async", _embed)
        # extract_posting is sync + retry-decorated; replace with a fast stub
        monkeypatch.setattr(
            ingestion_module,
            "extract_posting",
            lambda raw: (self._make_posting(), {"cost_usd": 0.001}),
        )

        async_session = MagicMock()
        async_session.commit = AsyncMock()
        async_session.rollback = AsyncMock()

        src = ingestion_module.MarkdownFileSource(tmp_path)
        result = await ingestion_module.ingest_from_source(async_session, src)

        assert result.total == 2
        assert result.ingested == 2
        assert result.skipped == 0
        assert result.errors == 0
        assert len(result.posting_ids) == 2
        # cost float-summed; allow tiny FP drift
        assert abs(result.total_cost_usd - 0.002) < 1e-9

    async def test_ingest_from_source_dedup_second_run(
        self, tmp_path, ingestion_module, monkeypatch
    ):
        """BACK-10: a second run over the same source returns ingested=0,
        skipped=N because content_hash dedup hits (D-22)."""
        if not hasattr(ingestion_module, "ingest_from_source"):
            pytest.skip("ingest_from_source not yet added (Plan 03)")

        from unittest.mock import AsyncMock, MagicMock

        (tmp_path / "a.md").write_text("# A\n")
        (tmp_path / "b.md").write_text("# B\n")

        # Simulate "already exists" for every check
        async def _exists(*args, **kwargs):
            return True

        monkeypatch.setattr(ingestion_module, "_posting_exists_async", _exists)

        async_session = MagicMock()
        async_session.commit = AsyncMock()
        async_session.rollback = AsyncMock()

        src = ingestion_module.MarkdownFileSource(tmp_path)
        result = await ingestion_module.ingest_from_source(async_session, src)

        assert result.total == 2
        assert result.ingested == 0
        assert result.skipped == 2
        assert result.errors == 0

    async def test_ingest_from_source_extract_error_counted(
        self, tmp_path, ingestion_module, monkeypatch
    ):
        """BACK-10: when extract_posting raises, IngestResult.errors increments
        and error_details captures (source_url, str(exc))."""
        if not hasattr(ingestion_module, "ingest_from_source"):
            pytest.skip("ingest_from_source not yet added (Plan 03)")

        from unittest.mock import AsyncMock, MagicMock

        (tmp_path / "a.md").write_text("# A\n")

        async def _exists(*args, **kwargs):
            return False

        def _bad_extract(raw):
            raise RuntimeError("LLM is sad")

        monkeypatch.setattr(ingestion_module, "_posting_exists_async", _exists)
        monkeypatch.setattr(ingestion_module, "extract_posting", _bad_extract)

        async_session = MagicMock()
        async_session.commit = AsyncMock()
        async_session.rollback = AsyncMock()

        src = ingestion_module.MarkdownFileSource(tmp_path)
        result = await ingestion_module.ingest_from_source(async_session, src)

        assert result.total == 1
        assert result.errors == 1
        assert len(result.error_details) == 1
        url, msg = result.error_details[0]
        assert url.startswith("file://")
        assert "LLM is sad" in msg


def test_ingest_file_sync_compat(ingestion_module):
    """BACK-10: sync ingest_file signature must stay (session, file_path, ...)
    so the existing CLI and /ingest endpoint keep working unchanged (D-24)."""
    import inspect

    if not hasattr(ingestion_module, "ingest_file"):
        pytest.skip("ingest_file refactor deferred")
    sig = inspect.signature(ingestion_module.ingest_file)
    params = list(sig.parameters.keys())
    assert params[0] == "session"
    assert "file_path" in params
