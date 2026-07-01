from enum import StrEnum

from pydantic import BaseModel, Field, field_validator


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


# Tokens the agent LLM (or an MCP client) uses to mean "no filter". The LLM
# tends to invent string sentinels like "null"/"any" for an omitted optional
# arg; treating them as None keeps an unspecified filter UNFILTERED instead of
# matching the literal value (which matches zero rows — the analyze_gaps
# "no postings" bug). See services/retrieval.apply_posting_filters.
_NO_FILTER_TOKENS: frozenset[str] = frozenset(
    {"", "null", "none", "any", "all", "n/a", "na", "undefined"}
)
_SENIORITY_VALUES: frozenset[str] = frozenset(s.value for s in Seniority)
_REMOTE_POLICY_VALUES: frozenset[str] = frozenset(r.value for r in RemotePolicy)


def _coerce_enum_value(value: object, valid: frozenset[str]) -> str | None:
    """Lower-case ``value`` and return it only if it is a known enum value.

    Sentinel "no filter" tokens and any out-of-domain string return ``None`` so
    callers fall back to UNFILTERED rather than filtering on a value no column
    ever holds.
    """
    if value is None:
        return None
    token = str(value).strip().lower()
    if token in _NO_FILTER_TOKENS:
        return None
    return token if token in valid else None


def coerce_seniority(value: object) -> str | None:
    """Coerce an arbitrary seniority filter to a valid Seniority value, or None.

    The agent LLM and MCP clients pass free text — ``"null"``/``"any"``/``""``
    to mean "no filter", or values outside the enum. Anything unrecognized
    returns ``None`` (no filter) rather than a value that would match zero
    postings. Accepts the :class:`Seniority` enum itself unchanged.
    """
    return _coerce_enum_value(value, _SENIORITY_VALUES)


def coerce_remote_policy(value: object) -> str | None:
    """Coerce an arbitrary remote filter to a valid RemotePolicy value, or None.

    Accepts the :class:`RemotePolicy` strings (remote/hybrid/onsite/unknown). A
    ``bool`` maps ``True`` -> ``"remote"`` and ``False`` -> ``None`` so a
    caller can pass a remote-only flag. Junk — including the LLM's stray
    ``"true"``/``"false"`` strings — returns ``None`` (no filter).
    """
    if isinstance(value, bool):
        return RemotePolicy.REMOTE.value if value else None
    return _coerce_enum_value(value, _REMOTE_POLICY_VALUES)


class JobRequirement(BaseModel):
    """A single skill or requirement extracted from a job posting.

    skill_type is LLM-extracted (the 8-value taxonomy).
    skill_category is derived deterministically from skill_type via derive_skill_category()
    at write time (in services/extraction.py and services/ingestion.py per D-03 / D-13).
    """

    skill: str = Field(description="Name of the skill, tool, or qualification")
    skill_type: SkillType = Field(
        description=(
            "Skill kind (language, framework, cloud, database, concept, tool, "
            "soft_skill, domain)"
        )
    )
    # Defaulted (NOT required) on purpose. The extraction prompt instructs the LLM
    # to NOT emit skill_category (it is overwritten in code via derive_skill_category()
    # at store time). When this field was required, every time the model obeyed that
    # instruction the whole posting failed Pydantic validation — only instructor's
    # reask loop recovered it, and ~25% of postings never converged on a fresh ingest
    # (prod seeded 88/118; see services/ingestion.py overwrite at store time). A
    # default keeps the field present without forcing the LLM to produce a value.
    skill_category: SkillCategory = Field(
        default=SkillCategory.HARD,
        description="Derived category (hard / soft / domain) — populated by code, not the LLM",
    )
    required: bool = Field(description="True if must-have, False if nice-to-have")

    @field_validator("skill_type", mode="before")
    @classmethod
    def _fallback_unknown_skill_type(cls, v: object) -> object:
        """Coerce an out-of-taxonomy skill_type to CONCEPT — the prompt's own
        fallback ('When uncertain, use concept'). The LLM occasionally emits a
        value outside the 8-member SkillType enum (e.g. 'mlops', 'other'); without
        this, that single bad value would fail validation and drop the whole posting.
        """
        if isinstance(v, str):
            for candidate in (v, v.strip().lower()):
                try:
                    return SkillType(candidate)
                except ValueError:
                    continue
            return SkillType.CONCEPT
        return v


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


class ResumeExtraction(BaseModel):
    """LLM-extracted resume contents (Phase 7 D-13).

    Sibling of :class:`UserSkillProfile`. Decoupled so the extraction format can
    evolve (e.g. add ``companies_worked_at``) without coupling the canonical
    user-state shape. Adds ``years_experience``, which the resume-review UI
    surfaces back to the user, and renames ``min_salary`` to ``min_salary_eur``
    so the Instructor prompt has an explicit unit hint (otherwise GPT-4o-mini
    tends to drop the currency conversion step).
    """

    skills: list[UserSkill] = Field(description="Extracted user skills")
    target_roles: list[str] = Field(
        default_factory=list, description="Target job titles inferred from the resume"
    )
    preferred_locations: list[str] = Field(
        default_factory=list, description="Preferred locations stated in the resume"
    )
    min_salary_eur: int | None = Field(
        default=None, description="Minimum acceptable salary in EUR/year"
    )
    remote_preference: RemotePolicy = Field(
        default=RemotePolicy.UNKNOWN, description="Preferred remote policy"
    )
    years_experience: int | None = Field(
        default=None, description="Years of professional experience"
    )
