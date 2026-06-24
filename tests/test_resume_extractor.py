"""Tests for src/job_rag/extraction/resume_extractor.py (PROF-03).

Mirrors tests/test_extraction.py::TestExtractPosting + TestPromptStructure
+ TestRejectionRulesUnit. Covers:
- structured output (extract_resume returns (ResumeExtraction, usage_info))
- tenacity 3x retry then re-raise on ValidationError
- prompt-structure invariants (REJECTED_SOFT_SKILLS pass-through, spoken-
  language carve-outs, RESUME_PROMPT_VERSION pin)
- ResumeExtraction schema shape (6 D-13 fields, defaults)
"""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import BaseModel, ValidationError

from job_rag.extraction.prompt import REJECTED_SOFT_SKILLS
from job_rag.extraction.resume_extractor import extract_resume
from job_rag.extraction.resume_prompt import (
    RESUME_PROMPT_VERSION,
    RESUME_SYSTEM_PROMPT,
)
from job_rag.models import RemotePolicy, ResumeExtraction, UserSkill


class TestExtractResume:
    def test_extract_resume_returns_resume_extraction_and_usage(self):
        """structured_output: Instructor returns ResumeExtraction + usage_info dict (D-15)."""
        mock_extraction = ResumeExtraction(
            skills=[UserSkill(name="Python")],
            target_roles=["AI Engineer"],
            preferred_locations=["Berlin"],
            min_salary_eur=70000,
            remote_preference=RemotePolicy.REMOTE,
            years_experience=5,
        )
        mock_completion = MagicMock()
        mock_completion.usage.prompt_tokens = 100
        mock_completion.usage.completion_tokens = 50

        with patch("job_rag.extraction.resume_extractor.instructor") as mock_instructor:
            mock_client = MagicMock()
            mock_instructor.from_openai.return_value = mock_client
            mock_client.chat.completions.create_with_completion.return_value = (
                mock_extraction,
                mock_completion,
            )
            extraction, usage_info = extract_resume(
                "TEST FIXTURE — synthetic resume text"
            )

        assert isinstance(extraction, ResumeExtraction)
        assert extraction.skills[0].name == "Python"
        assert usage_info["prompt_version"] == RESUME_PROMPT_VERSION
        assert usage_info["prompt_tokens"] == 100
        assert usage_info["completion_tokens"] == 50
        assert usage_info["total_tokens"] == 150

    def test_extract_resume_retries_3x_then_raises(self):
        """retries_3x: tenacity retries on ValidationError 3 times then re-raises (D-15, D-16)."""

        # ValidationError needs at least one line item — fabricate via a dummy model.
        class _Dummy(BaseModel):
            x: int

        try:
            _Dummy(x="not-an-int")  # type: ignore[arg-type]
        except ValidationError as e:
            sample_error = e
        else:  # pragma: no cover — guard against pydantic semantics drifting
            raise AssertionError("Dummy did not raise ValidationError as expected")

        with patch("job_rag.extraction.resume_extractor.instructor") as mock_instructor:
            mock_client = MagicMock()
            mock_instructor.from_openai.return_value = mock_client
            mock_client.chat.completions.create_with_completion.side_effect = sample_error

            with pytest.raises(ValidationError):
                extract_resume("anything")

            # 3 attempts per tenacity @retry(stop_after_attempt(3))
            assert (
                mock_client.chat.completions.create_with_completion.call_count == 3
            )


class TestResumePromptStructure:
    def test_rejected_terms_in_system_prompt(self):
        """D-14: every REJECTED_SOFT_SKILLS term flows into RESUME_SYSTEM_PROMPT."""
        for term in REJECTED_SOFT_SKILLS:
            assert term in RESUME_SYSTEM_PROMPT, f"missing rejection term: {term!r}"

    def test_spoken_language_carveouts(self):
        """D-14 carve-out: English / German / Polish are explicitly allowed as skills."""
        assert "English" in RESUME_SYSTEM_PROMPT
        assert "German" in RESUME_SYSTEM_PROMPT
        assert "Polish" in RESUME_SYSTEM_PROMPT

    def test_prompt_version_is_string(self):
        """D-12: RESUME_PROMPT_VERSION is a string and is pinned to '1.0' for v1."""
        assert isinstance(RESUME_PROMPT_VERSION, str)
        assert RESUME_PROMPT_VERSION == "1.0"

    def test_module_imports_cleanly(self):
        """If str.format() raises (e.g., unbalanced braces in the template),
        this test fails at import time."""
        import importlib

        import job_rag.extraction.resume_prompt as resume_prompt_mod

        importlib.reload(resume_prompt_mod)
        assert resume_prompt_mod.RESUME_PROMPT_VERSION == "1.0"


class TestResumeExtractionSchema:
    def test_six_fields_present(self):
        """D-13: ResumeExtraction has the 6 documented fields."""
        schema = ResumeExtraction.model_json_schema()
        expected = {
            "skills",
            "target_roles",
            "preferred_locations",
            "min_salary_eur",
            "remote_preference",
            "years_experience",
        }
        assert expected <= set(schema["properties"].keys()), schema["properties"].keys()

    def test_defaults_match_d13(self):
        """D-13: target_roles / preferred_locations default to empty list;
        salary / years_experience nullable; remote_preference defaults UNKNOWN."""
        m = ResumeExtraction(skills=[])
        assert m.target_roles == []
        assert m.preferred_locations == []
        assert m.min_salary_eur is None
        assert m.years_experience is None
        assert m.remote_preference == RemotePolicy.UNKNOWN
