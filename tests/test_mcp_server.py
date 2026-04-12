import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from job_rag.mcp_server import tools


@pytest.fixture
def mock_async_session():
    session = AsyncMock()
    session.__aenter__.return_value = session
    session.__aexit__.return_value = None
    return session


def _make_posting(**overrides):
    posting = MagicMock()
    posting.id = uuid.uuid4()
    posting.title = "Senior AI Engineer"
    posting.company = "TestCorp"
    posting.location = "Berlin"
    posting.remote_policy = "remote"
    posting.seniority = "senior"
    posting.salary_min = 70000
    posting.salary_max = 90000
    posting.salary_raw = "€70k-€90k"
    posting.source_url = "https://linkedin.com/jobs/view/1/"
    must_have = MagicMock(skill="Python", required=True)
    nice = MagicMock(skill="Rust", required=False)
    posting.requirements = [must_have, nice]
    for k, v in overrides.items():
        setattr(posting, k, v)
    return posting


@pytest.mark.asyncio
class TestSearchPostings:
    async def test_returns_serialized_results(self):
        posting = _make_posting()
        mock_results = [{"posting": posting, "distance": 0.2, "similarity": 0.8}]
        reranked = [{**mock_results[0], "rerank_score": 1.5}]

        with (
            patch("job_rag.mcp_server.tools.AsyncSessionLocal") as mock_factory,
            patch(
                "job_rag.mcp_server.tools._search_postings", new_callable=AsyncMock
            ) as mock_search,
            patch("job_rag.mcp_server.tools.rerank") as mock_rerank,
        ):
            session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None
            mock_search.return_value = mock_results
            mock_rerank.return_value = reranked

            result = await tools.search_postings("rag experience", limit=5)

        assert result["count"] == 1
        assert result["query"] == "rag experience"
        assert result["results"][0]["company"] == "TestCorp"
        assert result["results"][0]["must_have"] == ["Python"]
        assert result["results"][0]["nice_to_have"] == ["Rust"]
        assert "rerank_score" in result["results"][0]

    async def test_remote_only_filter(self):
        with (
            patch("job_rag.mcp_server.tools.AsyncSessionLocal") as mock_factory,
            patch(
                "job_rag.mcp_server.tools._search_postings", new_callable=AsyncMock
            ) as mock_search,
            patch("job_rag.mcp_server.tools.rerank") as mock_rerank,
        ):
            session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None
            mock_search.return_value = []
            mock_rerank.return_value = []

            await tools.search_postings("foo", remote_only=True)

        mock_search.assert_awaited_once()
        kwargs = mock_search.await_args.kwargs
        assert kwargs["remote"] == "remote"

    async def test_empty_results(self):
        with (
            patch("job_rag.mcp_server.tools.AsyncSessionLocal") as mock_factory,
            patch(
                "job_rag.mcp_server.tools._search_postings", new_callable=AsyncMock
            ) as mock_search,
        ):
            session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None
            mock_search.return_value = []

            result = await tools.search_postings("nothing here")

        assert result == {"query": "nothing here", "count": 0, "results": []}


@pytest.mark.asyncio
class TestMatchSkills:
    async def test_returns_match_report(self):
        posting = _make_posting()

        with (
            patch("job_rag.mcp_server.tools.AsyncSessionLocal") as mock_factory,
            patch("job_rag.mcp_server.tools.load_profile") as mock_load,
            patch("job_rag.mcp_server.tools.match_posting") as mock_match,
        ):
            session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None
            execute_result = MagicMock()
            execute_result.scalar_one_or_none.return_value = posting
            session.execute = AsyncMock(return_value=execute_result)
            mock_load.return_value = MagicMock()
            mock_match.return_value = {"score": 0.85, "company": "TestCorp"}

            result = await tools.match_skills(str(posting.id))

        assert result["score"] == 0.85
        mock_match.assert_called_once()

    async def test_posting_not_found(self):
        with patch("job_rag.mcp_server.tools.AsyncSessionLocal") as mock_factory:
            session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None
            execute_result = MagicMock()
            execute_result.scalar_one_or_none.return_value = None
            session.execute = AsyncMock(return_value=execute_result)

            result = await tools.match_skills(str(uuid.uuid4()))

        assert result["error"] == "posting_not_found"


@pytest.mark.asyncio
class TestSkillGaps:
    async def test_returns_aggregated_gaps(self):
        posting = _make_posting()

        with (
            patch("job_rag.mcp_server.tools.AsyncSessionLocal") as mock_factory,
            patch("job_rag.mcp_server.tools.load_profile") as mock_load,
            patch("job_rag.mcp_server.tools.aggregate_gaps") as mock_agg,
        ):
            session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None
            execute_result = MagicMock()
            scalars = MagicMock()
            scalars.all.return_value = [posting]
            execute_result.scalars.return_value = scalars
            session.execute = AsyncMock(return_value=execute_result)
            mock_load.return_value = MagicMock()
            mock_agg.return_value = {"total_postings_analyzed": 1, "must_have_gaps": []}

            result = await tools.skill_gaps(seniority="senior")

        assert result["total_postings_analyzed"] == 1

    async def test_no_postings_returns_error(self):
        with patch("job_rag.mcp_server.tools.AsyncSessionLocal") as mock_factory:
            session = AsyncMock()
            mock_factory.return_value.__aenter__.return_value = session
            mock_factory.return_value.__aexit__.return_value = None
            execute_result = MagicMock()
            scalars = MagicMock()
            scalars.all.return_value = []
            execute_result.scalars.return_value = scalars
            session.execute = AsyncMock(return_value=execute_result)

            result = await tools.skill_gaps()

        assert result["error"] == "no_postings_found"


@pytest.mark.asyncio
class TestIngestPosting:
    async def test_requires_path_or_content(self):
        result = await tools.ingest_posting()
        assert result["error"] == "must_provide_file_path_or_content"

    async def test_file_not_found(self):
        result = await tools.ingest_posting(file_path="/no/such/file.md")
        assert result["error"] == "file_not_found"

    async def test_ingest_content(self, tmp_path):
        with patch("job_rag.mcp_server.tools._ingest_path_sync") as mock_sync:
            mock_sync.return_value = {"ingested": True, "embedded": True, "reason": "ok"}
            result = await tools.ingest_posting(content="# Sample posting")

        assert result["ingested"] is True
        assert result["embedded"] is True
        mock_sync.assert_called_once()

    async def test_ingest_existing_path(self, tmp_path):
        f = tmp_path / "posting.md"
        f.write_text("# Sample", encoding="utf-8")

        with (
            patch("job_rag.mcp_server.tools._ingest_path_sync") as mock_sync,
            patch("job_rag.mcp_server.tools._allowed_path", return_value=True),
        ):
            mock_sync.return_value = {"ingested": True, "embedded": True, "reason": "ok"}
            result = await tools.ingest_posting(file_path=str(f))

        assert result["ingested"] is True
        mock_sync.assert_called_once_with(f)

    async def test_ingest_path_not_allowed(self, tmp_path):
        f = tmp_path / "posting.md"
        f.write_text("# Sample", encoding="utf-8")

        result = await tools.ingest_posting(file_path=str(f))
        assert result["error"] == "path_not_allowed"
