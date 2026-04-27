import asyncio
from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest

from job_rag.models import (
    JobPosting,
    JobRequirement,
    RemotePolicy,
    SalaryPeriod,
    Seniority,
    SkillCategory,
)


@pytest.fixture
def sample_raw_text() -> str:
    path = "tests/fixtures/sample_posting.md"
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def sample_posting() -> JobPosting:
    return JobPosting(
        title="Senior AI Engineer",
        company="TestCorp",
        location="Berlin, Germany",
        remote_policy=RemotePolicy.HYBRID,
        salary_min=70000,
        salary_max=90000,
        salary_raw="€70,000-€90,000/year",
        salary_period=SalaryPeriod.YEAR,
        seniority=Seniority.SENIOR,
        employment_type="Full-time",
        requirements=[
            JobRequirement(skill="Python", category=SkillCategory.LANGUAGE, required=True),
            JobRequirement(skill="LLM", category=SkillCategory.CONCEPT, required=True),
            JobRequirement(skill="RAG", category=SkillCategory.CONCEPT, required=True),
            JobRequirement(skill="Docker", category=SkillCategory.TOOL, required=True),
            JobRequirement(skill="SQL", category=SkillCategory.LANGUAGE, required=True),
            JobRequirement(skill="Kubernetes", category=SkillCategory.TOOL, required=False),
            JobRequirement(skill="TypeScript", category=SkillCategory.LANGUAGE, required=False),
            JobRequirement(skill="LangChain", category=SkillCategory.FRAMEWORK, required=False),
        ],
        responsibilities=[
            "Design and implement RAG pipelines",
            "Build and deploy LLM-powered applications",
            "Collaborate with product teams",
        ],
        benefits=["30 vacation days", "Remote flexibility", "Learning budget"],
        source_url="https://www.linkedin.com/jobs/view/1234567890/",
        raw_text="sample raw text",
    )


@pytest.fixture
def mock_openai_client():
    return MagicMock()


@pytest.fixture
def fake_slow_agent():
    """Simulates stream_agent that pauses between yields.

    Used by BACK-05 test to observe heartbeat emission during active reasoning.
    Yields one token then a final event with a 100ms delay each — short enough
    to keep CI tests fast, long enough to interleave with a heartbeat task.
    """

    async def _impl(query: str) -> AsyncIterator[dict]:
        await asyncio.sleep(0.1)
        yield {"type": "token", "content": "slow"}
        await asyncio.sleep(0.1)
        yield {"type": "final", "content": "slow"}

    return _impl


@pytest.fixture
def fake_hanging_agent():
    """Simulates stream_agent that never yields — triggers agent_timeout.

    Used by BACK-06 test. The body sleeps 3600s before each (unreachable)
    yield, so any consumer MUST wrap iteration in a timeout (combine with
    monkeypatched settings.agent_timeout_seconds = 0.5 in CI to keep
    wall-time bounded). Otherwise the test runner will hang.
    """

    async def _impl(query: str) -> AsyncIterator[dict]:
        while True:
            await asyncio.sleep(3600)
            yield {"type": "token", "content": "never"}  # unreachable

    return _impl
