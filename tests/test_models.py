import pytest
from pydantic import ValidationError

from job_rag.models import (
    JobPosting,
    JobRequirement,
    Location,
    RemotePolicy,
    SalaryPeriod,
    Seniority,
    SkillCategory,
    SkillType,
    UserSkill,
    UserSkillProfile,
    derive_skill_category,
)


class TestJobRequirement:
    def test_valid_requirement(self):
        req = JobRequirement(
            skill="Python",
            skill_type=SkillType.LANGUAGE,
            skill_category=SkillCategory.HARD,
            required=True,
        )
        assert req.skill == "Python"
        assert req.skill_type == SkillType.LANGUAGE
        assert req.skill_category == SkillCategory.HARD
        assert req.required is True

    def test_nice_to_have(self):
        req = JobRequirement(
            skill="Kubernetes",
            skill_type=SkillType.TOOL,
            skill_category=SkillCategory.HARD,
            required=False,
        )
        assert req.required is False

    def test_old_category_field_rejected(self):
        """Confirms the rename: passing `category=` raises ValidationError."""
        with pytest.raises(ValidationError):
            JobRequirement(skill="Python", category=SkillType.LANGUAGE, required=True)  # type: ignore[call-arg]


class TestSkillType:
    """Renamed from SkillCategory per D-01. The 8 string values are unchanged."""

    def test_eight_members(self):
        values = [s.value for s in SkillType]
        assert len(values) == 8
        assert set(values) == {
            "language",
            "framework",
            "cloud",
            "database",
            "concept",
            "tool",
            "soft_skill",
            "domain",
        }


class TestSkillCategoryDerivation:
    """D-03 deterministic 8→3 mapping: hard/soft/domain."""

    @pytest.mark.parametrize(
        "skill_type,expected",
        [
            (SkillType.LANGUAGE, SkillCategory.HARD),
            (SkillType.FRAMEWORK, SkillCategory.HARD),
            (SkillType.CLOUD, SkillCategory.HARD),
            (SkillType.DATABASE, SkillCategory.HARD),
            (SkillType.CONCEPT, SkillCategory.HARD),
            (SkillType.TOOL, SkillCategory.HARD),
            (SkillType.SOFT_SKILL, SkillCategory.SOFT),
            (SkillType.DOMAIN, SkillCategory.DOMAIN),
        ],
    )
    def test_mapping(self, skill_type: SkillType, expected: SkillCategory):
        assert derive_skill_category(skill_type) == expected


class TestLocation:
    """Pydantic round-trip for Location submodel — covers 4 D-09 examples + null edge case."""

    @pytest.mark.parametrize(
        "location_kwargs",
        [
            {"country": "DE", "city": "Berlin", "region": None},
            {"country": "DE", "city": "Munich", "region": "Bavaria"},
            {"country": None, "city": None, "region": "EU"},
            {"country": None, "city": None, "region": "Worldwide"},
            {"country": None, "city": None, "region": None},
        ],
    )
    def test_round_trip(self, location_kwargs: dict):
        loc = Location(**location_kwargs)
        restored = Location(**loc.model_dump())
        assert restored == loc

    def test_default_all_null(self):
        loc = Location()
        assert loc.country is None
        assert loc.city is None
        assert loc.region is None


class TestJobRequirementBothFields:
    """JobRequirement carries skill_type (LLM) AND skill_category (derived)."""

    def test_hard_skill(self):
        req = JobRequirement(
            skill="Python",
            skill_type=SkillType.LANGUAGE,
            skill_category=SkillCategory.HARD,
            required=True,
        )
        assert req.skill_type == SkillType.LANGUAGE
        assert req.skill_category == SkillCategory.HARD

    def test_derive_then_construct(self):
        """Common write-time pattern: LLM provides skill_type; code derives skill_category."""
        st = SkillType.SOFT_SKILL
        req = JobRequirement(
            skill="leadership",
            skill_type=st,
            skill_category=derive_skill_category(st),
            required=False,
        )
        assert req.skill_category == SkillCategory.SOFT


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
            location=Location(country="DE", city="Berlin", region=None),
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
                location=Location(country="DE", city="Berlin", region=None),  # type: ignore[call-arg]
                remote_policy=RemotePolicy.UNKNOWN,
                seniority=Seniority.UNKNOWN,
                employment_type="Full-time",
                requirements=[],
                responsibilities=[],
                source_url="https://example.com",
                raw_text="test",
            )

    def test_string_location_rejected(self):
        """JobPosting.location is a Location submodel; bare strings must be rejected."""
        with pytest.raises(ValidationError):
            JobPosting(
                title="Test",
                company="Test",
                location="Berlin, Germany",  # type: ignore[arg-type]
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
            location=Location(country="DE", city="Berlin", region=None),
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
