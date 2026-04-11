import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from job_rag.agent import graph, stream
from job_rag.agent import tools as agent_tools


@pytest.fixture(autouse=True)
def _clear_agent_cache():
    graph.build_agent.cache_clear()
    yield
    graph.build_agent.cache_clear()


@pytest.mark.asyncio
class TestAgentTools:
    async def test_search_jobs_serializes_result(self):
        with patch(
            "job_rag.agent.tools.job_tools.search_postings", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = {"count": 1, "results": [{"company": "TestCorp"}]}
            raw = await agent_tools.search_jobs.ainvoke({"query": "rag"})

        data = json.loads(raw)
        assert data["count"] == 1
        assert data["results"][0]["company"] == "TestCorp"

    async def test_match_profile_serializes_result(self):
        with patch(
            "job_rag.agent.tools.job_tools.match_skills", new_callable=AsyncMock
        ) as mock_match:
            mock_match.return_value = {"score": 0.85}
            raw = await agent_tools.match_profile.ainvoke({"posting_id": "abc"})

        assert json.loads(raw)["score"] == 0.85

    async def test_analyze_gaps_serializes_result(self):
        with patch(
            "job_rag.agent.tools.job_tools.skill_gaps", new_callable=AsyncMock
        ) as mock_gaps:
            mock_gaps.return_value = {"total_postings_analyzed": 23}
            raw = await agent_tools.analyze_gaps.ainvoke({"seniority": "senior"})

        assert json.loads(raw)["total_postings_analyzed"] == 23


@pytest.mark.asyncio
class TestRunAgent:
    async def test_run_agent_returns_answer_and_tool_calls(self):
        mock_final_msg = MagicMock()
        mock_final_msg.content = "Final synthesized answer."
        mock_final_msg.tool_calls = []

        mock_tool_msg = MagicMock()
        mock_tool_msg.content = ""
        mock_tool_msg.tool_calls = [{"name": "search_jobs", "args": {"query": "rag"}}]

        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(
            return_value={"messages": [mock_tool_msg, mock_final_msg]}
        )

        with patch("job_rag.agent.graph.build_agent", return_value=mock_agent):
            result = await graph.run_agent("which jobs use rag?")

        assert result["answer"] == "Final synthesized answer."
        assert result["message_count"] == 2
        assert len(result["tool_calls"]) == 1
        assert result["tool_calls"][0]["name"] == "search_jobs"

    async def test_run_agent_handles_no_tool_calls(self):
        mock_msg = MagicMock()
        mock_msg.content = "Simple answer."
        mock_msg.tool_calls = []

        mock_agent = MagicMock()
        mock_agent.ainvoke = AsyncMock(return_value={"messages": [mock_msg]})

        with patch("job_rag.agent.graph.build_agent", return_value=mock_agent):
            result = await graph.run_agent("hello")

        assert result["answer"] == "Simple answer."
        assert result["tool_calls"] == []


@pytest.mark.asyncio
class TestStreamAgent:
    async def test_stream_agent_yields_token_tool_and_final(self):
        async def fake_events(*_args, **_kwargs):
            chunk = MagicMock()
            chunk.content = "Hello "
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk},
                "name": "ChatOpenAI",
            }
            yield {
                "event": "on_tool_start",
                "data": {"input": {"query": "rag"}},
                "name": "search_jobs",
            }
            yield {
                "event": "on_tool_end",
                "data": {"output": "tool result text"},
                "name": "search_jobs",
            }
            chunk2 = MagicMock()
            chunk2.content = "world."
            yield {
                "event": "on_chat_model_stream",
                "data": {"chunk": chunk2},
                "name": "ChatOpenAI",
            }

        mock_agent = MagicMock()
        mock_agent.astream_events = fake_events

        with patch("job_rag.agent.stream.build_agent", return_value=mock_agent):
            events = [event async for event in stream.stream_agent("hi")]

        types = [e["type"] for e in events]
        assert "token" in types
        assert "tool_start" in types
        assert "tool_end" in types
        assert types[-1] == "final"
        assert events[-1]["content"] == "Hello world."
