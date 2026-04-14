import uuid
from unittest.mock import MagicMock

import pytest

from job_rag.models import RemotePolicy, UserSkill, UserSkillProfile
from job_rag.services.matching import (
    _normalize_skill,
    _skill_matches,
    aggregate_gaps,
    match_posting,
)


@pytest.fixture
def profile() -> UserSkillProfile:
    return UserSkillProfile(
        skills=[
            UserSkill(name="Python"),
            UserSkill(name="Docker"),
            UserSkill(name="SQL"),
            UserSkill(name="React"),
            UserSkill(name="LLM"),
        ],
        target_roles=["AI Engineer"],
        preferred_locations=["Berlin, Germany"],
        min_salary=65000,
        remote_preference=RemotePolicy.REMOTE,
    )


def _make_posting(
    must_have: list[str],
    nice_to_have: list[str],
    remote_policy: str = "remote",
    salary_min: int | None = None,
    salary_max: int | None = None,
) -> MagicMock:
    """Create a mock posting with requirements."""
    posting = MagicMock()
    posting.id = uuid.uuid4()
    posting.title = "AI Engineer"
    posting.company = "TestCorp"
    posting.remote_policy = remote_policy
    posting.salary_min = salary_min
    posting.salary_max = salary_max

    requirements = []
    for skill in must_have:
        req = MagicMock()
        req.skill = skill
        req.required = True
        requirements.append(req)
    for skill in nice_to_have:
        req = MagicMock()
        req.skill = skill
        req.required = False
        requirements.append(req)

    posting.requirements = requirements
    return posting


class TestNormalizeSkill:
    def test_lowercase(self):
        assert _normalize_skill("Python") == "python"

    def test_strip_whitespace(self):
        assert _normalize_skill("  Docker  ") == "docker"

    def test_replace_hyphens(self):
        assert _normalize_skill("ci-cd") == "ci cd"

    def test_replace_underscores(self):
        assert _normalize_skill("soft_skill") == "soft skill"


class TestSkillMatches:
    def test_exact_match(self):
        skills = {"python", "docker"}
        assert _skill_matches(skills, "Python") is True

    def test_no_match(self):
        skills = {"python", "docker"}
        assert _skill_matches(skills, "Kubernetes") is False


class TestMatchPosting:
    def test_perfect_must_have_match(self, profile):
        posting = _make_posting(
            must_have=["Python", "Docker", "SQL"],
            nice_to_have=["React"],
        )
        result = match_posting(profile, posting)
        assert result["must_have_score"] == 1.0
        assert result["nice_to_have_score"] == 1.0
        assert result["score"] == 1.0
        assert result["gaps"] == []

    def test_partial_must_have_match(self, profile):
        posting = _make_posting(
            must_have=["Python", "Kubernetes", "Terraform"],
            nice_to_have=[],
        )
        result = match_posting(profile, posting)
        assert result["must_have_score"] == pytest.approx(1 / 3, abs=0.01)
        assert len(result["missed_must_have"]) == 2

    def test_no_match(self, profile):
        posting = _make_posting(
            must_have=["Kubernetes", "Terraform", "Go"],
            nice_to_have=["Rust"],
        )
        result = match_posting(profile, posting)
        assert result["score"] == 0.0
        assert len(result["gaps"]) == 4

    def test_no_must_have_defaults_to_one(self, profile):
        posting = _make_posting(must_have=[], nice_to_have=["Python"])
        result = match_posting(profile, posting)
        assert result["must_have_score"] == 1.0

    def test_no_nice_to_have_defaults_to_one(self, profile):
        posting = _make_posting(must_have=["Python"], nice_to_have=[])
        result = match_posting(profile, posting)
        assert result["nice_to_have_score"] == 1.0

    def test_score_formula(self, profile):
        # 2/3 must-have, 1/2 nice-to-have
        posting = _make_posting(
            must_have=["Python", "Docker", "Kubernetes"],
            nice_to_have=["React", "Go"],
        )
        result = match_posting(profile, posting)
        expected = (2 / 3) * 0.7 + (1 / 2) * 0.3
        assert result["score"] == pytest.approx(expected, abs=0.01)

    def test_bonus_remote_match(self, profile):
        posting = _make_posting(must_have=["Python"], nice_to_have=[], remote_policy="remote")
        result = match_posting(profile, posting)
        assert "remote_match" in result["bonus"]

    def test_bonus_salary_ok(self, profile):
        posting = _make_posting(
            must_have=["Python"], nice_to_have=[], salary_max=80000, salary_min=60000
        )
        result = match_posting(profile, posting)
        assert "salary_range_ok" in result["bonus"]


class TestAggregateGaps:
    def test_aggregation(self, profile):
        postings = [
            _make_posting(must_have=["Python", "LangChain"], nice_to_have=["Go"]),
            _make_posting(must_have=["Python", "LangChain", "Kubernetes"], nice_to_have=[]),
        ]
        result = aggregate_gaps(profile, postings)
        assert result["total_postings_analyzed"] == 2

        must_skills = [g["skill"] for g in result["must_have_gaps"]]
        assert "LangChain" in must_skills

    def test_empty_postings(self, profile):
        result = aggregate_gaps(profile, [])
        assert result["total_postings_analyzed"] == 0
        assert result["must_have_gaps"] == []
