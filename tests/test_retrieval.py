import uuid
from unittest.mock import MagicMock, patch

import pytest

from job_rag.services.retrieval import rerank


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
