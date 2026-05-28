"""Profile diff service (Phase 7 D-17..D-20).

Pure-Python helpers + Pydantic models for the resume-upload review loop:

- :func:`compute_skills_diff` classifies extracted skills against the
  current profile into added / removed / unchanged buckets, ordered
  alphabetically per bucket (added first, then removed, then unchanged
  per D-19). Equality is defined via
  :func:`job_rag.services.matching._normalize_skill` so casing and
  hyphen/underscore variants collapse (Python == python ==
  fast api).
- :class:`SkillDiffItem` — wire-format item in the
  :class:`ResumeUploadResponse` envelope.
- :class:`ResumeUploadResponse` — the
  ``POST /profile/upload`` response body.
- :class:`UserProfileUpdate` — the ``PATCH /profile`` request body
  (skills REQUIRED; other fields default to None = no change).
"""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

from job_rag.models import (
    RemotePolicy,
    ResumeExtraction,
    UserSkill,
    UserSkillProfile,
)
from job_rag.services.matching import _normalize_skill


class SkillDiffItem(BaseModel):
    """One row in the upload-review diff (D-17).

    ``editable=True`` only for ``source="added"`` chips per D-26 — the user
    can rename newly-discovered skills before they are persisted. Removed
    and unchanged chips are read-only at the wire level.
    """

    name: str
    source: Literal["added", "removed", "unchanged"]
    editable: bool


class ResumeUploadResponse(BaseModel):
    """Wire shape returned by ``POST /profile/upload`` (D-13).

    ``extraction_id`` ties the upload to a Langfuse trace (D-32) and is
    echoed back on the subsequent PATCH so the ``profile_save`` span can
    attach to the same trace.
    """

    extracted: ResumeExtraction
    skills_diff: list[SkillDiffItem]
    prompt_version: str
    extraction_id: UUID


class UserProfileUpdate(BaseModel):
    """PATCH /profile body (D-21).

    ``skills`` is REQUIRED and REPLACES the row's ``skills_json`` entirely.
    Other fields default to ``None`` and are treated as "no change" by the
    handler so the existing DB value is preserved. ``extraction_id`` is the
    Langfuse correlation token from the prior upload response — passing it
    back lets the ``profile_save`` span attach to the same trace.
    """

    skills: list[UserSkill]
    target_roles: list[str] | None = None
    preferred_locations: list[str] | None = None
    min_salary_eur: int | None = None
    remote_preference: RemotePolicy | None = None
    extraction_id: UUID | None = Field(
        default=None,
        description="Langfuse correlation token (D-21).",
    )


def compute_skills_diff(
    current: UserSkillProfile, extracted_skills: list[UserSkill]
) -> list[SkillDiffItem]:
    """Diff extracted skills against the current profile (D-17..D-20).

    Two skills are 'the same' iff
    ``_normalize_skill(a) == _normalize_skill(b)``. Output ordering: added
    (alphabetical) then removed (alphabetical) then unchanged
    (alphabetical). Casing: extracted casing for added rows; the user's
    existing canonical casing for removed AND unchanged rows. The
    unchanged bucket reuses the user's stored casing (rather than the
    extracted casing) so a round-trip save through ``PATCH /profile``
    cannot silently rename a persisted skill — important because
    ``editable=False`` for unchanged rows (D-26) gives the user no
    Pencil affordance to opt into a rename (WR-03).

    ``_ALIAS_GROUPS`` in matching.py is empty in v1 (Phase 1 D-12); the
    diff is normalize-equality only. Future alias support would swap
    membership tests for :func:`_skill_matches` semantics.
    """
    current_map = {_normalize_skill(s.name): s.name for s in current.skills}
    extracted_map = {
        _normalize_skill(s.name): s.name for s in extracted_skills
    }

    cur_keys = set(current_map)
    ext_keys = set(extracted_map)

    added = sorted(extracted_map[k] for k in (ext_keys - cur_keys))
    removed = sorted(current_map[k] for k in (cur_keys - ext_keys))
    # WR-03: keep the user's canonical casing for unchanged rows.
    unchanged = sorted(current_map[k] for k in (ext_keys & cur_keys))

    return [
        *(SkillDiffItem(name=n, source="added", editable=True) for n in added),
        *(
            SkillDiffItem(name=n, source="removed", editable=False)
            for n in removed
        ),
        *(
            SkillDiffItem(name=n, source="unchanged", editable=False)
            for n in unchanged
        ),
    ]


__all__ = [
    "ResumeUploadResponse",
    "SkillDiffItem",
    "UserProfileUpdate",
    "compute_skills_diff",
]
