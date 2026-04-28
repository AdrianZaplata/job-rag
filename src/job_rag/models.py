from enum import StrEnum

from pydantic import BaseModel, Field


class SkillType(StrEnum):
    """The 8-value taxonomy of skill kinds (renamed from SkillCategory per D-01).

    SkillType is LLM-extracted; SkillCategory (below) is derived from it deterministically
    in Python via derive_skill_category() per D-03. The two axes are orthogonal: SkillType
    captures kind (language vs framework vs cloud), SkillCategory captures aggregate
    (hard vs soft vs domain) for the Phase 5 dashboard filter.
    """

    LANGUAGE = "language"
    FRAMEWORK = "framework"
    CLOUD = "cloud"
    DATABASE = "database"
    CONCEPT = "concept"
    TOOL = "tool"
    SOFT_SKILL = "soft_skill"
    DOMAIN = "domain"


class SkillCategory(StrEnum):
    """The 3-value categorization (NEW per D-02). Phase 5 dashboard hides 'soft' by
    default with a 'show soft skills' toggle (DASH-01)."""

    HARD = "hard"
    SOFT = "soft"
    DOMAIN = "domain"


def derive_skill_category(skill_type: SkillType) -> SkillCategory:
    """Deterministic mapping (D-03).

    Hard:   language, framework, cloud, database, concept, tool
    Soft:   soft_skill
    Domain: domain

    SkillType.LANGUAGE includes spoken languages (English, German, ...) per D-21 — they
    map to HARD because spoken-language proficiency is binary-checkable. The conceptual
    mismatch (`language` originally meant programming languages) is acknowledged and
    deferred (see CONTEXT.md Deferred Ideas — SkillType.NATURAL_LANGUAGE split).
    """
    if skill_type is SkillType.SOFT_SKILL:
        return SkillCategory.SOFT
    if skill_type is SkillType.DOMAIN:
        return SkillCategory.DOMAIN
    return SkillCategory.HARD


class Location(BaseModel):
    """Structured location replacing free-text str (D-06, D-07). All fields nullable
    (D-09: 'Worldwide' / 'Remote (EU)' → country=null, region populated).
    Stored as 3 flat DB columns location_country / location_city / location_region per D-11.
    """

    country: str | None = Field(
        default=None, description="ISO-3166 alpha-2 code (DE, PL, US, GB, ...)"
    )
    city: str | None = Field(default=None, description="City name (e.g., Berlin)")
    region: str | None = Field(
        default=None,
        description="Region/state/area (e.g., Bavaria, EU, Worldwide). Used when country is null.",
    )


class RemotePolicy(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class Seniority(StrEnum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    LEAD = "lead"
    UNKNOWN = "unknown"


class SalaryPeriod(StrEnum):
    HOUR = "hour"
    MONTH = "month"
    YEAR = "year"
    UNKNOWN = "unknown"


class JobRequirement(BaseModel):
    """A single skill or requirement extracted from a job posting.

    skill_type is LLM-extracted (the 8-value taxonomy).
    skill_category is derived deterministically from skill_type via derive_skill_category()
    at write time (in services/extraction.py and services/ingestion.py per D-03 / D-13).
    """

    skill: str = Field(description="Name of the skill, tool, or qualification")
    skill_type: SkillType = Field(
        description="Skill kind (language, framework, cloud, database, concept, tool, soft_skill, domain)"
    )
    skill_category: SkillCategory = Field(
        description="Derived category (hard / soft / domain) — populated by code, not the LLM"
    )
    required: bool = Field(description="True if must-have, False if nice-to-have")


class JobPosting(BaseModel):
    """Structured representation of an AI Engineer job posting."""

    title: str = Field(description="Job title as written in the posting")
    company: str = Field(description="Company name")
    location: Location = Field(
        description="Structured location: country (ISO-3166 alpha-2), city, region (all nullable)"
    )
    remote_policy: RemotePolicy = Field(description="Remote work policy")
    salary_min: int | None = Field(default=None, description="Minimum salary in EUR/year, or None")
    salary_max: int | None = Field(default=None, description="Maximum salary in EUR/year, or None")
    salary_raw: str | None = Field(
        default=None, description="Raw salary string exactly as written in the posting"
    )
    salary_period: SalaryPeriod = Field(
        default=SalaryPeriod.UNKNOWN, description="Pay period: hour, month, year, or unknown"
    )
    seniority: Seniority = Field(description="Seniority level of the role")
    employment_type: str = Field(description="Full-time, contract, freelance, etc.")
    requirements: list[JobRequirement] = Field(
        description="All skills and qualifications mentioned"
    )
    responsibilities: list[str] = Field(description="Key responsibilities as short bullet points")
    benefits: list[str] = Field(default_factory=list, description="Benefits mentioned, if any")
    source_url: str = Field(description="URL where this posting was found")
    raw_text: str = Field(description="Original unprocessed text of the posting")


class UserSkill(BaseModel):
    """A skill in the user's profile."""

    name: str = Field(description="Skill name")


class UserSkillProfile(BaseModel):
    """User's skill profile for matching against job postings."""

    skills: list[UserSkill] = Field(description="User skills")
    target_roles: list[str] = Field(default_factory=list, description="Target job titles")
    preferred_locations: list[str] = Field(default_factory=list, description="Preferred locations")
    min_salary: int | None = Field(
        default=None, description="Minimum acceptable salary in EUR/year"
    )
    remote_preference: RemotePolicy = Field(
        default=RemotePolicy.UNKNOWN, description="Preferred remote policy"
    )
