"""Phase 5 - dashboard endpoint Pydantic response models + filter enums.

API-specific Pydantic models live under api/ (precedent: src/job_rag/api/sse.py).
src/job_rag/models.py is reserved for domain models (JobPosting, JobRequirement,
Location, enums); transport schemas live here.

These models drive:
  - FastAPI route response-type annotations (so OpenAPI emits named schemas)
  - openapi-typescript codegen output (so the frontend imports named TS interfaces
    via paths['/dashboard/top-skills']['get']['responses']['200']['content'])
  - filter parameter validation via Pydantic enum types (CountryFilter, RemoteFilter)
    reject bad strings at FastAPI Query() boundary with HTTP 422.

Seniority filter reuses the existing Seniority enum from src/job_rag/models.py - do
NOT redeclare it here.
"""

from enum import StrEnum

from pydantic import BaseModel, Field


class CountryFilter(StrEnum):
    """Canonical 4-value country filter (D-07).

    PL/DE: exact ISO-3166 alpha-2 match.
    EU:    union of EU-27 ISO codes OR location_region == 'EU' (catches NULL-country
           "Remote (EU)" postings per Phase 2 D-09).
    WW:    no filter (default; matches Worldwide).
    """

    PL = "PL"
    DE = "DE"
    EU = "EU"
    WW = "WW"


class RemoteFilter(StrEnum):
    """3-state remote-policy tri-toggle (D-09).

    any:        no filter (default).
    remote:     remote_policy = 'remote'.
    non_remote: remote_policy IN ('hybrid', 'onsite').
    """

    ANY = "any"
    REMOTE = "remote"
    NON_REMOTE = "non_remote"


class TopSkillItem(BaseModel):
    """One row of the top-skills aggregate."""

    skill: str = Field(description="Skill identifier (technical, mono-font in UI)")
    must_count: int = Field(description="Number of postings where this skill is must-have")
    nice_count: int = Field(description="Number of postings where this skill is nice-to-have")
    total: int = Field(description="must_count + nice_count")


class DashboardTopSkillsResponse(BaseModel):
    """GET /dashboard/top-skills response."""

    skills: list[TopSkillItem] = Field(
        description="Top-N skills (capped at the `limit` query param) ordered by total DESC"
    )
    total_postings: int = Field(
        description="Total postings matching the filter (footnote denominator)"
    )
    unique_skills: int = Field(
        description="Distinct skill count (after soft-skill filter, if applied)"
    )


class DashboardSalaryBandsResponse(BaseModel):
    """GET /dashboard/salary-bands response.

    Percentile fields are `int | None` because PostgreSQL `percentile_cont` returns
    NULL on empty result sets (RESEARCH Pitfall 2). The frontend reads `p50 is null`
    as the empty-state condition.
    """

    p25: int | None = Field(description="25th percentile annual salary in EUR")
    p50: int | None = Field(description="Median (50th percentile) annual salary in EUR")
    p75: int | None = Field(description="75th percentile annual salary in EUR")
    postings_with_salary: int = Field(
        description=(
            "Number of filtered postings that had salary data "
            "(numerator of sample-size footnote)"
        )
    )
    total_postings: int = Field(
        description="Total filtered postings (denominator of sample-size footnote)"
    )
    currency: str = Field(default="EUR", description="ISO 4217 currency code; v1 hardcodes EUR")


class MissingSkillItem(BaseModel):
    """One row in the cv-vs-market top-3 missing must-have list."""

    skill: str = Field(description="Missing must-have skill identifier")
    count: int = Field(description="Number of filtered postings missing this must-have")
    percentage: float = Field(description="count / total_postings * 100, rounded to 1 decimal")


class DashboardCvMatchResponse(BaseModel):
    """GET /dashboard/cv-vs-market response.

    `mean_score` is `float | None` because D-12 zero-postings case returns
    `{mean_score: None, postings_compared: 0, top_missing_must_have: []}` with
    HTTP 200 (NOT 404).
    """

    mean_score: float | None = Field(
        description=(
            "Arithmetic mean of per-posting match_posting() scores; None when "
            "postings_compared == 0 (D-12)"
        )
    )
    postings_compared: int = Field(
        description="Number of filtered postings compared against the profile"
    )
    top_missing_must_have: list[MissingSkillItem] = Field(
        description="Top 3 missing must-have skills ranked by frequency (Counter.most_common(3))"
    )
