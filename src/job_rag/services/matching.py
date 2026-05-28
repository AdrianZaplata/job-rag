import json
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from job_rag.config import settings
from job_rag.db.models import JobPostingDB, UserProfileDB
from job_rag.logging import get_logger
from job_rag.models import RemotePolicy, UserSkill, UserSkillProfile

log = get_logger(__name__)


async def load_profile(
    session: AsyncSession, *, user_id: UUID | None = None,
) -> UserSkillProfile:
    """Load user skill profile from the ``user_profile`` DB row (PROF-01).

    Phase 7 D-01/D-02 body-flip: replaces the Phase 1 ``data/profile.json``
    read with an async DB query. The Phase 1 D-07 signature
    ``(*, user_id, path)`` collapses to ``(session, *, user_id)`` because
    the ``path`` kwarg was a forward-compat hook with no production caller.

    The seed migration ``alembic/versions/0006_seed_user_profile.py``
    guarantees the row exists. Missing row = data-integrity bug, not a
    user error — raise ``RuntimeError`` so the surface fails loudly rather
    than silently returning an empty profile that would destroy the user's
    skill list on the next PATCH save.

    Args:
        session: An open ``AsyncSession`` bound to the live engine.
        user_id: Defaults to ``settings.seeded_user_id`` for the v1
            single-user fallback.

    Raises:
        RuntimeError: If no ``user_profile`` row exists for ``user_id``.

    Returns:
        A validated ``UserSkillProfile`` reconstituted from the JSON columns.
    """
    uid = user_id or settings.seeded_user_id
    stmt = select(UserProfileDB).where(UserProfileDB.user_id == uid)
    row = (await session.execute(stmt)).scalar_one_or_none()
    if row is None:
        raise RuntimeError(f"user_profile row missing for user_id={uid}")
    return UserSkillProfile(
        skills=[UserSkill(**s) for s in json.loads(row.skills_json)],
        target_roles=json.loads(row.target_roles_json),
        preferred_locations=json.loads(row.preferred_locations_json),
        min_salary=row.min_salary_eur,
        remote_preference=RemotePolicy(row.remote_preference),
    )


def _normalize_skill(name: str) -> str:
    """Normalize skill name for fuzzy matching."""
    return name.lower().strip().replace("-", " ").replace("_", " ")


# Each inner list is an equivalence class — any term in the list matches any other.
# Add a new group to teach the matcher about a new family of synonyms.
_ALIAS_GROUPS: list[list[str]] = []


def _build_alias_index(groups: list[list[str]]) -> dict[str, frozenset[str]]:
    """Map every term to the frozenset of its synonyms (including itself)."""
    index: dict[str, frozenset[str]] = {}
    for group in groups:
        members = frozenset(group)
        for term in group:
            index[term] = members
    return index


_ALIAS_INDEX = _build_alias_index(_ALIAS_GROUPS)


def _skill_matches(user_skills: set[str], job_skill: str) -> bool:
    """Check if a job skill matches any user skill (case-insensitive, fuzzy)."""
    normalized = _normalize_skill(job_skill)

    # Direct match
    if normalized in user_skills:
        return True

    job_aliases = _ALIAS_INDEX.get(normalized, frozenset({normalized}))
    for user_skill in user_skills:
        user_aliases = _ALIAS_INDEX.get(user_skill, frozenset({user_skill}))
        if user_aliases & job_aliases:
            return True

    return False


def match_posting(profile: UserSkillProfile, posting: JobPostingDB) -> dict[str, Any]:
    """Score how well a user profile matches a job posting.

    Formula: score = (matched_must / total_must) * 0.7 + (matched_nice / total_nice) * 0.3
    """
    user_skills = {_normalize_skill(s.name) for s in profile.skills}

    must_have = [r for r in posting.requirements if r.required]
    nice_to_have = [r for r in posting.requirements if not r.required]

    matched_must = [r.skill for r in must_have if _skill_matches(user_skills, r.skill)]
    missed_must = [r.skill for r in must_have if not _skill_matches(user_skills, r.skill)]
    matched_nice = [r.skill for r in nice_to_have if _skill_matches(user_skills, r.skill)]
    missed_nice = [r.skill for r in nice_to_have if not _skill_matches(user_skills, r.skill)]

    must_score = len(matched_must) / len(must_have) if must_have else 1.0
    nice_score = len(matched_nice) / len(nice_to_have) if nice_to_have else 1.0
    score = must_score * 0.7 + nice_score * 0.3

    # Bonus signals
    bonus: list[str] = []
    if posting.remote_policy == profile.remote_preference.value:
        bonus.append("remote_match")
    if posting.salary_min and profile.min_salary:
        if posting.salary_min >= profile.min_salary:
            bonus.append("salary_meets_minimum")
    if posting.salary_max and profile.min_salary:
        if posting.salary_max >= profile.min_salary:
            bonus.append("salary_range_ok")

    return {
        "posting_id": str(posting.id),
        "title": posting.title,
        "company": posting.company,
        "score": round(score, 3),
        "must_have_score": round(must_score, 3),
        "nice_to_have_score": round(nice_score, 3),
        "matched_must_have": matched_must,
        "missed_must_have": missed_must,
        "matched_nice_to_have": matched_nice,
        "missed_nice_to_have": missed_nice,
        "gaps": missed_must + missed_nice,
        "bonus": bonus,
    }


def aggregate_gaps(
    profile: UserSkillProfile,
    postings: list[JobPostingDB],
) -> dict[str, Any]:
    """Aggregate skill gaps across all postings.

    Returns top missing skills ranked by frequency.
    """
    from collections import Counter

    must_have_gaps: Counter[str] = Counter()
    nice_to_have_gaps: Counter[str] = Counter()

    user_skills = {_normalize_skill(s.name) for s in profile.skills}

    for posting in postings:
        for req in posting.requirements:
            if not _skill_matches(user_skills, req.skill):
                if req.required:
                    must_have_gaps[req.skill] += 1
                else:
                    nice_to_have_gaps[req.skill] += 1

    return {
        "total_postings_analyzed": len(postings),
        "must_have_gaps": [
            {"skill": skill, "count": count, "percentage": round(count / len(postings) * 100, 1)}
            for skill, count in must_have_gaps.most_common(20)
        ],
        "nice_to_have_gaps": [
            {"skill": skill, "count": count, "percentage": round(count / len(postings) * 100, 1)}
            for skill, count in nice_to_have_gaps.most_common(20)
        ],
    }
