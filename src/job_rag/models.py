from enum import Enum

from pydantic import BaseModel, Field


class SkillCategory(str, Enum):
    LANGUAGE = "language"
    FRAMEWORK = "framework"
    CLOUD = "cloud"
    DATABASE = "database"
    CONCEPT = "concept"
    TOOL = "tool"
    SOFT_SKILL = "soft_skill"
    DOMAIN = "domain"


class RemotePolicy(str, Enum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"


class Seniority(str, Enum):
    JUNIOR = "junior"
    MID = "mid"
    SENIOR = "senior"
    STAFF = "staff"
    LEAD = "lead"
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
    seniority: Seniority = Field(description="Seniority level of the role")
    employment_type: str = Field(description="Full-time, contract, freelance, etc.")
    requirements: list[JobRequirement] = Field(description="All skills and qualifications mentioned")
    responsibilities: list[str] = Field(description="Key responsibilities as short bullet points")
    benefits: list[str] = Field(default_factory=list, description="Benefits mentioned, if any")
    source_url: str = Field(description="URL where this posting was found")
    raw_text: str = Field(description="Original unprocessed text of the posting")
