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
    async def test_ingest_from_source_roundtrip(self, tmp_path, ingestion_module):
        """BACK-10: ingest_from_source executes end-to-end (D-24).

        Requires DB - Plan 03 will mock the async session + _store_posting_async
        to keep this unit-speed. Plan 01 provides the skip stub.
        """
        if not hasattr(ingestion_module, "ingest_from_source"):
            pytest.skip("ingest_from_source not yet added (Plan 03)")
        pytest.skip(
            "Full roundtrip deferred - Plan 03 provides mocks + concrete assertions"
        )


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
