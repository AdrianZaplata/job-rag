"""Phase 5 - dashboard analytics service module (DASH-01/02/03).

Three async functions that compute the dashboard's three analytical surfaces:
  - top_skills:   GROUP BY skill aggregation with must/nice split, soft-skill filter
  - salary_bands: percentile_cont(p25/p50/p75) with salary-period normalization
  - cv_match:     hybrid SQL pre-filter + Python fold over match_posting()

Sharing a private _apply_filters(stmt, *, country, seniority, remote) helper that
mutates a SQLAlchemy select with the canonical 4-value country / Seniority enum /
3-state remote filter shapes (CONTEXT.md D-07, D-08, D-09).

All three functions accept the auth-dep'd user_id for forward-compat with Phase 7
PROF-01 (which flips load_profile() body to DB lookup keyed on user_id). v1 corpus
is global (career_id='ai_engineer'); only cv_match() uses user_id today (for the
profile lookup).
"""

import uuid
from collections import Counter
from typing import Any

from sqlalchemy import Select, case, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_rag.db.models import JobPostingDB, JobRequirementDB
from job_rag.logging import get_logger
from job_rag.services.matching import load_profile, match_posting

log = get_logger(__name__)


# ISO-3166 alpha-2 codes for the 27 EU member states.
# Source: https://en.wikipedia.org/wiki/Member_state_of_the_European_Union
# Snapshot 2026-05-22 (UK departed 2020-01-31; no membership change since 2023).
# Note: ISO uses "GR" for Greece; EU protocol uses "EL". Corpus stores ISO.
# Refresh this constant if EU membership changes (rare; check accession-pending list).
EU_COUNTRY_CODES: frozenset[str] = frozenset({
    "AT", "BE", "BG", "HR", "CY", "CZ", "DK", "EE", "FI", "FR",
    "DE", "GR", "HU", "IE", "IT", "LV", "LT", "LU", "MT", "NL",
    "PL", "PT", "RO", "SK", "SI", "ES", "SE",
})


def _apply_filters(
    stmt: Select[Any],
    *,
    country: str = "WW",
    seniority: str | None = None,
    remote: str = "any",
) -> Select[Any]:
    """Mutate a SQLAlchemy select with country/seniority/remote WHERE clauses.

    Country values (D-07):
      - "PL" / "DE": exact location_country match
      - "EU":        location_country IN EU_COUNTRY_CODES OR location_region == "EU"
                     (the OR branch catches D-09 NULL-country "Remote (EU)" rows)
      - "WW":        no filter (default)

    Seniority: optional value from Seniority enum; None = no filter (D-08).

    Remote (D-09):
      - "any":        no filter (default)
      - "remote":     remote_policy == "remote"
      - "non_remote": remote_policy IN ("hybrid", "onsite")
    """
    # Country
    if country == "PL":
        stmt = stmt.where(JobPostingDB.location_country == "PL")
    elif country == "DE":
        stmt = stmt.where(JobPostingDB.location_country == "DE")
    elif country == "EU":
        stmt = stmt.where(
            or_(
                JobPostingDB.location_country.in_(EU_COUNTRY_CODES),
                JobPostingDB.location_region == "EU",
            )
        )
    # "WW" -> no filter

    # Seniority
    if seniority is not None:
        stmt = stmt.where(JobPostingDB.seniority == seniority)

    # Remote
    if remote == "remote":
        stmt = stmt.where(JobPostingDB.remote_policy == "remote")
    elif remote == "non_remote":
        stmt = stmt.where(JobPostingDB.remote_policy.in_(["hybrid", "onsite"]))
    # "any" -> no filter

    return stmt


async def top_skills(
    session: AsyncSession,
    *,
    country: str = "WW",
    seniority: str | None = None,
    remote: str = "any",
    include_soft: bool = False,
    limit: int = 50,
) -> dict[str, Any]:
    """Top-N skills with must/nice split.

    DASH-01: server-side SQL GROUP BY aggregation; soft skills hidden by default
    via WHERE skill_category != 'soft' (D-13). Backend accepts ?include_soft=true
    for future flexibility.

    Returns:
        {
            "skills": [{"skill": str, "must_count": int, "nice_count": int, "total": int}, ...],
            "total_postings": int,
            "unique_skills": int,
        }
    """
    # Build base aggregation
    stmt = (
        select(
            JobRequirementDB.skill.label("skill"),
            func.sum(case((JobRequirementDB.required.is_(True), 1), else_=0)).label("must_count"),
            func.sum(case((JobRequirementDB.required.is_(False), 1), else_=0)).label("nice_count"),
            func.count().label("total"),
        )
        .join(JobPostingDB, JobRequirementDB.posting_id == JobPostingDB.id)
    )

    if not include_soft:
        stmt = stmt.where(JobRequirementDB.skill_category != "soft")  # D-13

    stmt = _apply_filters(stmt, country=country, seniority=seniority, remote=remote)
    stmt = stmt.group_by(JobRequirementDB.skill).order_by(func.count().desc()).limit(limit)

    result = await session.execute(stmt)
    rows = result.all()

    skills = [
        {
            "skill": row.skill,
            "must_count": int(row.must_count or 0),
            "nice_count": int(row.nice_count or 0),
            "total": int(row.total),
        }
        for row in rows
    ]

    # Sample-size counts: separate query with same filters
    posting_stmt = select(func.count()).select_from(JobPostingDB)
    posting_stmt = _apply_filters(
        posting_stmt, country=country, seniority=seniority, remote=remote
    )
    total_postings = int((await session.execute(posting_stmt)).scalar_one())

    # Unique skills count uses the same JOIN + filter; counts distinct skills
    unique_stmt = (
        select(func.count(func.distinct(JobRequirementDB.skill)))
        .join(JobPostingDB, JobRequirementDB.posting_id == JobPostingDB.id)
    )
    if not include_soft:
        unique_stmt = unique_stmt.where(JobRequirementDB.skill_category != "soft")
    unique_stmt = _apply_filters(
        unique_stmt, country=country, seniority=seniority, remote=remote
    )
    unique_skills = int((await session.execute(unique_stmt)).scalar_one())

    log.info(
        "dashboard_query",
        endpoint="top-skills",
        country=country,
        seniority=seniority,
        remote=remote,
        include_soft=include_soft,
        n_skills=len(skills),
        total_postings=total_postings,
        unique_skills=unique_skills,
    )

    return {
        "skills": skills,
        "total_postings": total_postings,
        "unique_skills": unique_skills,
    }


async def salary_bands(
    session: AsyncSession,
    *,
    country: str = "WW",
    seniority: str | None = None,
    remote: str = "any",
) -> dict[str, Any]:
    """Salary percentiles p25/p50/p75.

    DASH-02: server-side via PostgreSQL percentile_cont. Salary-period normalization:
    salary_period='month' rows normalized x12 (treated as annual); salary_period='hour'
    rows EXCLUDED (too noisy without hours/week assumption - deferred idea).

    Pitfalls:
      - func.percentile_cont(...) MUST chain .within_group(<sort_expr>.asc()) (Pitfall 1)
      - Empty result set yields NULL percentiles; response model declares int|None (Pitfall 2)
      - Mind salary_period='hour' exclusion (Pitfall 3); document hourly is deferred

    Returns:
        {"p25": int|None, "p50": int|None, "p75": int|None,
         "postings_with_salary": int, "total_postings": int, "currency": "EUR"}
    """
    # Normalize month -> year via x12 in the percentile sort expression
    normalized_salary = case(
        (JobPostingDB.salary_period == "month", JobPostingDB.salary_min * 12),
        else_=JobPostingDB.salary_min,
    )

    stmt = select(
        func.percentile_cont(0.25).within_group(normalized_salary.asc()).label("p25"),
        func.percentile_cont(0.50).within_group(normalized_salary.asc()).label("p50"),
        func.percentile_cont(0.75).within_group(normalized_salary.asc()).label("p75"),
        func.count().label("postings_with_salary"),
    ).where(
        JobPostingDB.salary_min.isnot(None),
        JobPostingDB.salary_period.in_(["year", "month"]),  # exclude 'hour' (Pitfall 3)
    )
    stmt = _apply_filters(stmt, country=country, seniority=seniority, remote=remote)

    row = (await session.execute(stmt)).one()

    # Total postings (no salary filter) - for the footnote n/m
    total_stmt = select(func.count()).select_from(JobPostingDB)
    total_stmt = _apply_filters(
        total_stmt, country=country, seniority=seniority, remote=remote
    )
    total_postings = int((await session.execute(total_stmt)).scalar_one())

    def _int_or_none(v: Any) -> int | None:
        return int(v) if v is not None else None

    log.info(
        "dashboard_query",
        endpoint="salary-bands",
        country=country,
        seniority=seniority,
        remote=remote,
        postings_with_salary=int(row.postings_with_salary),
        total_postings=total_postings,
    )

    return {
        "p25": _int_or_none(row.p25),
        "p50": _int_or_none(row.p50),
        "p75": _int_or_none(row.p75),
        "postings_with_salary": int(row.postings_with_salary),
        "total_postings": total_postings,
        "currency": "EUR",
    }


async def cv_match(
    session: AsyncSession,
    user_id: uuid.UUID,
    *,
    country: str = "WW",
    seniority: str | None = None,
    remote: str = "any",
) -> dict[str, Any]:
    """CV-vs-market aggregate match score.

    DASH-03: hybrid SQL pre-filter + Python per-posting fold. The fuzzy alias-aware
    skill matching in matching.py cannot trivially be SQL; SQL pre-filter +
    selectinload + Python loop is the right shape for v1 corpus size (<= 108 rows).

    Pattern: mirrors the existing /gaps handler at src/job_rag/api/routes.py:186
    (selectinload mandatory per Pitfall 14 - avoids N+1).

    D-12 zero-postings case: returns {mean_score: None, postings_compared: 0,
    top_missing_must_have: []}, HTTP 200 (NOT 404 like /gaps).

    Returns:
        {"mean_score": float|None, "postings_compared": int,
         "top_missing_must_have": [{"skill": str, "count": int, "percentage": float}, ...] (<=3)}
    """
    stmt = select(JobPostingDB).options(selectinload(JobPostingDB.requirements))
    stmt = _apply_filters(stmt, country=country, seniority=seniority, remote=remote)

    result = await session.execute(stmt)
    postings = list(result.scalars().all())

    if not postings:
        # D-12: zero-state with HTTP 200, NOT 404
        log.info("dashboard_query", endpoint="cv-vs-market", postings_compared=0)
        return {
            "mean_score": None,
            "postings_compared": 0,
            "top_missing_must_have": [],
        }

    profile = load_profile(user_id=user_id)
    scores: list[float] = []
    missing: Counter[str] = Counter()
    for posting in postings:
        m = match_posting(profile, posting)
        scores.append(m["score"])
        for skill in m["missed_must_have"]:
            missing[skill] += 1

    total = len(postings)
    mean_score = round(sum(scores) / total, 3)  # Q8 server-side 3 decimals; UI displays 2

    top_3 = [
        {"skill": s, "count": c, "percentage": round(c / total * 100, 1)}
        for s, c in missing.most_common(3)  # D-11: cap at 3
    ]

    log.info(
        "dashboard_query",
        endpoint="cv-vs-market",
        country=country,
        seniority=seniority,
        remote=remote,
        postings_compared=total,
        mean_score=mean_score,
        top_missing_count=len(top_3),
    )

    return {
        "mean_score": mean_score,
        "postings_compared": total,
        "top_missing_must_have": top_3,
    }
