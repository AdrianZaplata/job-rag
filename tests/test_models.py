import pytest
from pydantic import ValidationError

from job_rag.models import (
    JobPosting,
    JobRequirement,
    RemotePolicy,
    SalaryPeriod,
    Seniority,
    SkillCategory,
    UserSkill,
    UserSkillProfile,
)


class TestJobRequirement:
    def test_valid_requirement(self):
        req = JobRequirement(skill="Python", category=SkillCategory.LANGUAGE, required=True)
        assert req.skill == "Python"
        assert req.category == SkillCategory.LANGUAGE
        assert req.required is True

    def test_nice_to_have(self):
        req = JobRequirement(skill="Kubernetes", category=SkillCategory.TOOL, required=False)
        assert req.required is False

    def test_all_categories(self):
        for cat in SkillCategory:
            req = JobRequirement(skill="test", category=cat, required=True)
            assert req.category == cat


class TestJobPosting:
    def test_valid_posting(self, sample_posting: JobPosting):
        assert sample_posting.title == "Senior AI Engineer"
        assert sample_posting.company == "TestCorp"
        assert len(sample_posting.requirements) == 8

    def test_salary_fields(self, sample_posting: JobPosting):
        assert sample_posting.salary_min == 70000
        assert sample_posting.salary_max == 90000
        assert sample_posting.salary_raw == "€70,000-€90,000/year"
        assert sample_posting.salary_period == SalaryPeriod.YEAR

    def test_salary_defaults_to_none(self):
        posting = JobPosting(
            title="Test",
            company="Test",
            location="Berlin",
            remote_policy=RemotePolicy.UNKNOWN,
            seniority=Seniority.UNKNOWN,
            employment_type="Full-time",
            requirements=[],
            responsibilities=[],
            source_url="https://example.com",
            raw_text="test",
        )
        assert posting.salary_min is None
        assert posting.salary_max is None
        assert posting.salary_raw is None
        assert posting.salary_period == SalaryPeriod.UNKNOWN

    def test_requirements_must_have_count(self, sample_posting: JobPosting):
        must_have = [r for r in sample_posting.requirements if r.required]
        nice_to_have = [r for r in sample_posting.requirements if not r.required]
        assert len(must_have) == 5
        assert len(nice_to_have) == 3

    def test_remote_policy_values(self):
        assert RemotePolicy.REMOTE.value == "remote"
        assert RemotePolicy.HYBRID.value == "hybrid"
        assert RemotePolicy.ONSITE.value == "onsite"
        assert RemotePolicy.UNKNOWN.value == "unknown"

    def test_seniority_values(self):
        assert Seniority.JUNIOR.value == "junior"
        assert Seniority.SENIOR.value == "senior"
        assert Seniority.STAFF.value == "staff"
        assert Seniority.LEAD.value == "lead"

    def test_missing_required_field_raises(self):
        with pytest.raises(ValidationError):
            JobPosting(
                title="Test",
                # missing company
                location="Berlin",
                remote_policy=RemotePolicy.UNKNOWN,
                seniority=Seniority.UNKNOWN,
                employment_type="Full-time",
                requirements=[],
                responsibilities=[],
                source_url="https://example.com",
                raw_text="test",
            )

    def test_benefits_default_empty(self):
        posting = JobPosting(
            title="Test",
            company="Test",
            location="Berlin",
            remote_policy=RemotePolicy.UNKNOWN,
            seniority=Seniority.UNKNOWN,
            employment_type="Full-time",
            requirements=[],
            responsibilities=[],
            source_url="https://example.com",
            raw_text="test",
        )
        assert posting.benefits == []


class TestUserSkillProfile:
    def test_valid_profile(self):
        profile = UserSkillProfile(
            skills=[
                UserSkill(name="Python"),
                UserSkill(name="LangChain"),
            ],
            target_roles=["AI Engineer", "ML Engineer"],
            preferred_locations=["Berlin", "Remote"],
            min_salary=80000,
            remote_preference=RemotePolicy.REMOTE,
        )
        assert len(profile.skills) == 2
        assert profile.min_salary == 80000

    def test_profile_defaults(self):
        profile = UserSkillProfile(skills=[])
        assert profile.target_roles == []
        assert profile.preferred_locations == []
        assert profile.min_salary is None
        assert profile.remote_preference == RemotePolicy.UNKNOWN
