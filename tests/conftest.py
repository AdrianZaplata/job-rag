import asyncio
import uuid
from collections.abc import AsyncIterator
from unittest.mock import MagicMock

import pytest

from job_rag.models import (
    JobPosting,
    JobRequirement,
    Location,
    RemotePolicy,
    SalaryPeriod,
    Seniority,
    SkillType,
    derive_skill_category,
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
        location=Location(country="DE", city="Berlin", region=None),
        remote_policy=RemotePolicy.HYBRID,
        salary_min=70000,
        salary_max=90000,
        salary_raw="€70,000-€90,000/year",
        salary_period=SalaryPeriod.YEAR,
        seniority=Seniority.SENIOR,
        employment_type="Full-time",
        requirements=[
            JobRequirement(
                skill="Python",
                skill_type=SkillType.LANGUAGE,
                skill_category=derive_skill_category(SkillType.LANGUAGE),
                required=True,
            ),
            JobRequirement(
                skill="LLM",
                skill_type=SkillType.CONCEPT,
                skill_category=derive_skill_category(SkillType.CONCEPT),
                required=True,
            ),
            JobRequirement(
                skill="RAG",
                skill_type=SkillType.CONCEPT,
                skill_category=derive_skill_category(SkillType.CONCEPT),
                required=True,
            ),
            JobRequirement(
                skill="Docker",
                skill_type=SkillType.TOOL,
                skill_category=derive_skill_category(SkillType.TOOL),
                required=True,
            ),
            JobRequirement(
                skill="SQL",
                skill_type=SkillType.LANGUAGE,
                skill_category=derive_skill_category(SkillType.LANGUAGE),
                required=True,
            ),
            JobRequirement(
                skill="Kubernetes",
                skill_type=SkillType.TOOL,
                skill_category=derive_skill_category(SkillType.TOOL),
                required=False,
            ),
            JobRequirement(
                skill="TypeScript",
                skill_type=SkillType.LANGUAGE,
                skill_category=derive_skill_category(SkillType.LANGUAGE),
                required=False,
            ),
            JobRequirement(
                skill="LangChain",
                skill_type=SkillType.FRAMEWORK,
                skill_category=derive_skill_category(SkillType.FRAMEWORK),
                required=False,
            ),
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

    Plan 04 typed the stream contract: stream_agent now yields Pydantic
    AgentEvent instances (TokenEvent / FinalEvent / etc.). The fixture yields
    typed events so the Plan 06 route handler's `to_sse(event)` call works.
    """

    async def _impl(query: str) -> AsyncIterator[object]:
        from job_rag.api.sse import FinalEvent, TokenEvent

        await asyncio.sleep(0.1)
        yield TokenEvent(type="token", content="slow")
        await asyncio.sleep(0.1)
        yield FinalEvent(type="final", content="slow")

    return _impl


@pytest.fixture
def fake_hanging_agent():
    """Simulates stream_agent that never yields — triggers agent_timeout.

    Used by BACK-06 test. The body sleeps 3600s before each (unreachable)
    yield, so any consumer MUST wrap iteration in a timeout (combine with
    monkeypatched settings.agent_timeout_seconds = 0.5 in CI to keep
    wall-time bounded). Otherwise the test runner will hang.

    Plan 04 typed the stream contract; the unreachable yield is a typed
    TokenEvent for shape-correctness even though it never executes.
    """

    async def _impl(query: str) -> AsyncIterator[object]:
        from job_rag.api.sse import TokenEvent

        while True:
            await asyncio.sleep(3600)
            yield TokenEvent(type="token", content="never")  # unreachable

    return _impl


# ===== Phase 5 Wave 0 - dashboard fixture =====


@pytest.fixture
def dashboard_postings_factory():
    """Return a callable that produces list[JobPostingDB] with controlled variety.

    Default variety covers E1-E12 edge cases per VALIDATION.md:
      - 5 DE postings (3 with salary_period=year, 1 NULL salary, 1 salary_period=month)
      - 3 PL postings (varied seniority)
      - 2 region='EU' / country=NULL (DASH-04 EU-NULL branch - E2)
      - 1 region='Worldwide' / country=NULL (D-09 corpus shape)
      - 1 hourly contract posting (salary_period=hour - E4, excluded from percentiles)
      - Mix of skill_category=hard|soft|domain across requirements (E6, E7)
      - Mix of remote_policy=remote|hybrid|onsite

    Plan 05-02 / 05-03 wires this against the real analytics module; for
    Wave 0 the factory exists so the skip-guarded test classes can collect
    without a NameError on the fixture parameter.

    Tests can override the default set via dashboard_postings_factory(custom=[...]).
    """
    from job_rag.db.models import JobPostingDB, JobRequirementDB

    def _build_posting(
        *,
        country: str | None,
        region: str | None = None,
        seniority: str = "senior",
        remote_policy: str = "hybrid",
        salary_min: int | None = 70000,
        salary_period: str | None = "year",
        skills: list[tuple[str, str, bool]] | None = None,
    ) -> JobPostingDB:
        # skill_type: map "hard" -> "language" (a valid SkillType), keep "soft" / "domain" as-is.
        # JobRequirementDB.skill_type is a non-null string from the 8-value taxonomy.
        posting_id = uuid.uuid4()
        user_id = uuid.uuid4()
        requirements = [
            JobRequirementDB(
                id=uuid.uuid4(),
                posting_id=posting_id,
                skill=skill_name,
                skill_type="language" if cat == "hard" else cat,
                skill_category=cat,
                required=req,
            )
            for (skill_name, cat, req) in (skills or [("Python", "hard", True)])
        ]
        return JobPostingDB(
            id=posting_id,
            user_id=user_id,
            title="AI Engineer",
            company="TestCorp",
            location_country=country,
            location_city=None,
            location_region=region,
            remote_policy=remote_policy,
            seniority=seniority,
            salary_min=salary_min,
            salary_max=None,
            salary_period=salary_period,
            requirements=requirements,
            career_id="ai_engineer",
            prompt_version="2.0",
        )

    def _factory(*, custom: list[dict] | None = None) -> list:
        if custom is not None:
            return [_build_posting(**kwargs) for kwargs in custom]
        return [
            # 5 DE postings (3 year, 1 NULL salary, 1 month)
            _build_posting(
                country="DE",
                seniority="senior",
                salary_min=80000,
                skills=[
                    ("Python", "hard", True),
                    ("AWS", "hard", True),
                    ("communication", "soft", False),
                ],
            ),
            _build_posting(
                country="DE",
                seniority="mid",
                salary_min=65000,
                skills=[("Python", "hard", True), ("SQL", "hard", True)],
            ),
            _build_posting(
                country="DE",
                seniority="senior",
                salary_min=6000,
                salary_period="month",
                skills=[("AWS", "hard", True), ("Docker", "hard", False)],
            ),
            _build_posting(
                country="DE",
                seniority="staff",
                salary_min=None,
                skills=[("Kubernetes", "hard", True)],
            ),
            _build_posting(
                country="DE",
                seniority="junior",
                salary_min=50000,
                skills=[("Python", "hard", True)],
            ),
            # 3 PL postings, varied seniority
            _build_posting(
                country="PL",
                seniority="mid",
                salary_min=40000,
                skills=[("Python", "hard", True), ("Django", "hard", False)],
            ),
            _build_posting(
                country="PL",
                seniority="senior",
                salary_min=55000,
                skills=[("SQL", "hard", True)],
            ),
            _build_posting(
                country="PL",
                seniority="junior",
                salary_min=35000,
                skills=[("JavaScript", "hard", True)],
            ),
            # 2 EU-region / country=NULL (E2)
            _build_posting(
                country=None,
                region="EU",
                seniority="senior",
                remote_policy="remote",
                skills=[("Python", "hard", True), ("AWS", "hard", True)],
            ),
            _build_posting(
                country=None,
                region="EU",
                seniority="mid",
                remote_policy="remote",
                skills=[("SQL", "hard", True), ("teamwork", "soft", False)],
            ),
            # 1 Worldwide / country=NULL (D-09)
            _build_posting(
                country=None,
                region="Worldwide",
                seniority="lead",
                remote_policy="remote",
                salary_min=120000,
                skills=[("Python", "hard", True), ("Leadership", "domain", True)],
            ),
            # 1 hourly contract (E4, excluded from percentiles)
            _build_posting(
                country="US",
                seniority="senior",
                salary_min=40,
                salary_period="hour",
                skills=[("Python", "hard", True)],
            ),
        ]

    return _factory
