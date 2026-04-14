from enum import StrEnum

from pydantic import BaseModel, Field


class SkillCategory(StrEnum):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    CLOUD = "cloud"
    DATABASE = "database"
    CONCEPT = "concept"
    TOOL = "tool"
    SOFT_SKILL = "soft_skill"
    DOMAIN = "domain"


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
    """A single skill or requirement extracted from a job posting."""

    skill: str = Field(description="Name of the skill, tool, or qualification")
    category: SkillCategory = Field(description="Category this skill belongs to")
    required: bool = Field(description="True if must-have, False if nice-to-have")


class JobPosting(BaseModel):
    """Structured representation of an AI Engineer job posting."""

    title: str = Field(description="Job title as written in the posting")
    company: str = Field(description="Company name")
    location: str = Field(description="City/country where the job is based")
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
