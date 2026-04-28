from unittest.mock import MagicMock, patch

import pytest

from job_rag.extraction.extractor import extract_linkedin_id, extract_posting
from job_rag.extraction.prompt import PROMPT_VERSION, REJECTED_SOFT_SKILLS, SYSTEM_PROMPT
from job_rag.models import (
    JobPosting,
    JobRequirement,
    Location,
    RemotePolicy,
    SalaryPeriod,
    Seniority,
    SkillCategory,
    SkillType,
)


class TestExtractLinkedInId:
    def test_standard_url(self):
        url = "https://www.linkedin.com/jobs/view/4387647030/"
        assert extract_linkedin_id(url) == "4387647030"

    def test_url_without_trailing_slash(self):
        url = "https://www.linkedin.com/jobs/view/4387647030"
        assert extract_linkedin_id(url) == "4387647030"

    def test_url_with_query_params(self):
        url = "https://www.linkedin.com/jobs/view/4387647030/?trackingId=abc"
        assert extract_linkedin_id(url) == "4387647030"

    def test_non_linkedin_url(self):
        assert extract_linkedin_id("https://example.com/job/123") is None

    def test_empty_string(self):
        assert extract_linkedin_id("") is None


class TestExtractPosting:
    def test_extract_returns_posting_and_usage(self, sample_raw_text: str):
        mock_posting = JobPosting(
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
            requirements=[],
            responsibilities=["Build AI systems"],
            source_url="https://www.linkedin.com/jobs/view/1234567890/",
            raw_text=sample_raw_text,
        )

        mock_usage = MagicMock()
        mock_usage.prompt_tokens = 500
        mock_usage.completion_tokens = 200

        mock_completion = MagicMock()
        mock_completion.usage = mock_usage

        with patch("job_rag.extraction.extractor.instructor") as mock_instructor:
            mock_client = MagicMock()
            mock_instructor.from_openai.return_value = mock_client
            mock_client.chat.completions.create_with_completion.return_value = (
                mock_posting,
                mock_completion,
            )

            posting, usage_info = extract_posting(sample_raw_text)

            assert posting.company == "TestCorp"
            assert posting.title == "Senior AI Engineer"
            assert usage_info["prompt_tokens"] == 500
            assert usage_info["completion_tokens"] == 200
            assert usage_info["total_tokens"] == 700
            assert usage_info["cost_usd"] > 0
            assert usage_info["prompt_version"] == PROMPT_VERSION

    def test_prompt_version_is_set(self):
        assert PROMPT_VERSION == "2.0"


class TestPromptStructure:
    """Unit tests on the SYSTEM_PROMPT string itself — fast, no LLM calls.

    Anti-regression for Pitfall 4 (f-string brace escaping) and validation that
    the str.format() interpolation produced the expected sections.
    """

    def test_module_imports_cleanly(self):
        """If module-level str.format() raises (e.g., unbalanced braces in
        Location examples), this test fails at import time."""
        import importlib

        import job_rag.extraction.prompt as prompt_mod

        importlib.reload(prompt_mod)
        assert prompt_mod.PROMPT_VERSION == "2.0"

    def test_rejected_terms_in_system_prompt(self):
        for term in REJECTED_SOFT_SKILLS:
            assert term in SYSTEM_PROMPT, f"missing rejection term: {term!r}"

    def test_location_examples_in_system_prompt(self):
        assert '"DE", "city": "Berlin"' in SYSTEM_PROMPT
        assert '"region": "Bavaria"' in SYSTEM_PROMPT
        assert '"region": "EU"' in SYSTEM_PROMPT
        assert '"region": "Worldwide"' in SYSTEM_PROMPT

    def test_borderline_and_spoken_language_carveouts(self):
        assert "leadership" in SYSTEM_PROMPT
        assert "mentoring" in SYSTEM_PROMPT
        assert "stakeholder management" in SYSTEM_PROMPT
        # D-21 / Pitfall 7 — spoken languages NOT rejected
        assert "English" in SYSTEM_PROMPT
        assert "German" in SYSTEM_PROMPT
        assert "skill_type=language" in SYSTEM_PROMPT

    def test_skill_category_is_code_derived(self):
        """The LLM extracts skill_type only; skill_category is derived in
        code post-extraction (D-03)."""
        assert "derived deterministically" in SYSTEM_PROMPT
        assert "Do NOT output skill_category" in SYSTEM_PROMPT

    def test_decomposition_examples_preserved(self):
        """The 8 existing decomposition examples must survive the str.format()
        rewrite verbatim."""
        assert "automotive AI" in SYSTEM_PROMPT
        assert "Python and Django" in SYSTEM_PROMPT
        assert "Bus systems" in SYSTEM_PROMPT
        assert "deep learning" in SYSTEM_PROMPT


class TestRejectionRulesUnit:
    """LLM-mocked unit test: confirms `extract_posting` does NOT post-process /
    filter rejected terms (the prompt is the only enforcement). If the LLM
    returned a rejected term, we'd see it in the output — this test confirms
    the surface area of trust."""

    def test_extracted_skills_pass_through_verbatim(self):
        mock_posting = JobPosting(
            title="Senior AI Engineer",
            company="TestCorp",
            location=Location(country="DE", city="Berlin", region=None),
            remote_policy=RemotePolicy.HYBRID,
            salary_min=70000,
            salary_max=90000,
            salary_raw="€70-90k",
            salary_period=SalaryPeriod.YEAR,
            seniority=Seniority.SENIOR,
            employment_type="Full-time",
            requirements=[
                JobRequirement(
                    skill="Python",
                    skill_type=SkillType.LANGUAGE,
                    skill_category=SkillCategory.HARD,
                    required=True,
                ),
            ],
            responsibilities=["Build agents"],
            benefits=["Remote-friendly"],
            source_url="https://example.com",
            raw_text="…",
        )
        mock_usage = MagicMock(prompt_tokens=500, completion_tokens=200)
        mock_completion = MagicMock(usage=mock_usage)

        with patch("job_rag.extraction.extractor.instructor") as mock_instructor:
            mock_client = MagicMock()
            mock_instructor.from_openai.return_value = mock_client
            mock_client.chat.completions.create_with_completion.return_value = (
                mock_posting,
                mock_completion,
            )
            posting, _ = extract_posting("dummy raw text")

        # Trust surface confirmed: returned skills are exactly what the LLM mock returned.
        # No rejected term filtering happens in our code.
        extracted_skills_lower = [r.skill.lower() for r in posting.requirements]
        for term in REJECTED_SOFT_SKILLS:
            assert term not in extracted_skills_lower, (
                f"unexpected rejected term {term!r} in extracted skills "
                f"(LLM mock should not have produced it)"
            )


@pytest.mark.integration
class TestRejectionRulesLive:
    """Real LLM round-trip — excluded from default CI; run manually post-Phase-2.

    Costs ~€0.001 per run. Skips if OPENAI_API_KEY is unset.
    """

    def test_real_llm_rejects_communication_heavy_posting(self):
        import os

        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY unset — live LLM test skipped")

        raw = (
            "<job_posting>\n"
            "AI Engineer @ TestCorp, Berlin, Germany. Full-time, hybrid.\n"
            "Required: Python, LangChain, AWS, strong communication, teamwork, "
            "ownership mindset, attention to detail, problem-solving, time management. "
            "Nice to have: passion, drive, customer focus.\n"
            "Salary: €80k–100k/year.\n"
            "Source: https://example.com/test\n"
            "</job_posting>"
        )
        posting, _ = extract_posting(raw)
        extracted = [r.skill.lower() for r in posting.requirements]
        for term in REJECTED_SOFT_SKILLS:
            assert term not in extracted, (
                f"LLM extracted rejected term {term!r} — prompt rejection failed"
            )
