import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import select

from job_rag.db.models import JobPostingDB
from job_rag.services.retrieval import (
    apply_posting_filters,
    load_filtered_postings,
    rerank,
)


def _make_result(title: str, company: str, skills: list[str]) -> dict:
    """Create a mock search result."""
    posting = MagicMock()
    posting.id = uuid.uuid4()
    posting.title = title
    posting.company = company
    posting.responsibilities = "Build AI systems, design RAG pipelines"

    requirements = []
    for skill in skills:
        req = MagicMock()
        req.skill = skill
        req.required = True
        requirements.append(req)
    posting.requirements = requirements

    return {"posting": posting, "distance": 0.3, "similarity": 0.7}


class TestRerank:
    @patch("job_rag.services.retrieval._get_reranker")
    def test_rerank_sorts_by_score(self, mock_get_reranker):
        mock_reranker = MagicMock()
        mock_reranker.predict.return_value = [0.1, 0.9, 0.5]
        mock_get_reranker.return_value = mock_reranker

        results = [
            _make_result("Junior Dev", "Corp A", ["Python"]),
            _make_result("Senior AI Eng", "Corp B", ["Python", "LangChain", "RAG"]),
            _make_result("ML Engineer", "Corp C", ["PyTorch", "ML"]),
        ]

        reranked = rerank("AI engineer with RAG experience", results, top_k=3)

        assert len(reranked) == 3
        assert reranked[0]["posting"].title == "Senior AI Eng"
        assert reranked[0]["rerank_score"] == 0.9
        assert reranked[1]["rerank_score"] == 0.5
        assert reranked[2]["rerank_score"] == 0.1

    @patch("job_rag.services.retrieval._get_reranker")
    def test_rerank_top_k(self, mock_get_reranker):
        mock_reranker = MagicMock()
        mock_reranker.predict.return_value = [0.1, 0.9, 0.5]
        mock_get_reranker.return_value = mock_reranker

        results = [
            _make_result("A", "Corp A", ["Python"]),
            _make_result("B", "Corp B", ["LangChain"]),
            _make_result("C", "Corp C", ["ML"]),
        ]

        reranked = rerank("query", results, top_k=2)
        assert len(reranked) == 2

    def test_rerank_empty(self):
        assert rerank("query", []) == []

    @patch("job_rag.services.retrieval._get_reranker")
    def test_rerank_adds_score_field(self, mock_get_reranker):
        mock_reranker = MagicMock()
        mock_reranker.predict.return_value = [0.8]
        mock_get_reranker.return_value = mock_reranker

        results = [_make_result("AI Eng", "Corp", ["Python"])]
        reranked = rerank("query", results, top_k=1)

        assert "rerank_score" in reranked[0]
        assert reranked[0]["rerank_score"] == pytest.approx(0.8)


def _where_sql(stmt) -> str:
    """Render a select's WHERE clause to lower-cased SQL (or '' if none)."""
    wc = stmt.whereclause
    if wc is None:
        return ""
    return str(wc.compile(compile_kwargs={"literal_binds": True})).lower()


class TestApplyPostingFilters:
    """Coercion + location semantics shared by search + gaps (analyze_gaps bug)."""

    def test_no_filters_adds_no_whereclause(self):
        stmt = apply_posting_filters(select(JobPostingDB))
        assert stmt.whereclause is None

    @pytest.mark.parametrize("junk", ["null", "", "   ", "any", "banana", "principal"])
    def test_junk_seniority_adds_no_clause(self, junk):
        # An invalid seniority must fall back to UNFILTERED, not match zero rows.
        stmt = apply_posting_filters(select(JobPostingDB), seniority=junk)
        assert stmt.whereclause is None

    def test_valid_seniority_filters(self):
        stmt = apply_posting_filters(select(JobPostingDB), seniority="Senior")
        sql = _where_sql(stmt)
        assert "seniority" in sql
        assert "senior" in sql

    @pytest.mark.parametrize("junk", ["true", "false", "null", "", "yes"])
    def test_junk_remote_adds_no_clause(self, junk):
        # The LLM's "true"/"false" strings must NOT become remote_policy filters.
        stmt = apply_posting_filters(select(JobPostingDB), remote=junk)
        assert stmt.whereclause is None

    def test_valid_remote_filters(self):
        stmt = apply_posting_filters(select(JobPostingDB), remote="remote")
        sql = _where_sql(stmt)
        assert "remote_policy" in sql
        assert "remote" in sql

    def test_location_matches_city_country_region(self):
        stmt = apply_posting_filters(select(JobPostingDB), location="Berlin")
        sql = _where_sql(stmt)
        assert "location_city" in sql
        assert "location_country" in sql
        assert "location_region" in sql
        assert "berlin" in sql

    def test_blank_location_adds_no_clause(self):
        stmt = apply_posting_filters(select(JobPostingDB), location="   ")
        assert stmt.whereclause is None

    def test_all_filters_combined(self):
        stmt = apply_posting_filters(
            select(JobPostingDB), seniority="senior", remote="remote", location="Berlin"
        )
        sql = _where_sql(stmt)
        assert "seniority" in sql
        assert "remote_policy" in sql
        assert "location_city" in sql


@pytest.mark.asyncio
class TestLoadFilteredPostings:
    async def test_returns_postings_and_tolerates_junk_filters(self):
        posting = MagicMock()
        session = AsyncMock()
        execute_result = MagicMock()
        scalars = MagicMock()
        scalars.all.return_value = [posting]
        execute_result.scalars.return_value = scalars
        session.execute = AsyncMock(return_value=execute_result)

        # Junk seniority + a location must not raise and must return the rows.
        result = await load_filtered_postings(
            session, seniority="null", remote="false", location="Berlin"
        )

        assert result == [posting]
        session.execute.assert_awaited_once()
