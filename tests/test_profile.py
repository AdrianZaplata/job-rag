"""Tests for the Phase 7 profile feature (PROF-01..06).

Coverage filled by:
- Plan 02 (07-02-*): load_profile DB read path + seed migration round-trip
- Plan 04 (07-04-*): upload route 413/415/422 + diff helper + PATCH semantics
"""

from job_rag.models import UserSkill, UserSkillProfile
from job_rag.services.profile import compute_skills_diff


def _profile(skill_names: list[str]) -> UserSkillProfile:
    return UserSkillProfile(skills=[UserSkill(name=n) for n in skill_names])


# ----------------------------------------------------------------------
# Plan 07-04 Task 1 — compute_skills_diff unit tests (D-17..D-20)
# ----------------------------------------------------------------------


def test_compute_skills_diff_classifies_correctly():
    """D-17/D-18: every extracted skill ends up in exactly one bucket."""
    current = _profile(["Python", "FastAPI", "Docker"])
    extracted = [UserSkill(name=n) for n in ["Python", "Rust", "FastAPI"]]
    diff = compute_skills_diff(current, extracted)
    sources = {item.name: item.source for item in diff}
    assert sources == {
        "Rust": "added",
        "Docker": "removed",
        "Python": "unchanged",
        "FastAPI": "unchanged",
    }


def test_compute_skills_diff_orders_added_first():
    """D-19: added (alphabetical) → removed (alphabetical) → unchanged (alphabetical)."""
    current = _profile(["B-old", "C-old"])
    extracted = [UserSkill(name=n) for n in ["A-new", "Z-new", "B-old"]]
    diff = compute_skills_diff(current, extracted)
    added_names = [d.name for d in diff if d.source == "added"]
    removed_names = [d.name for d in diff if d.source == "removed"]
    unchanged_names = [d.name for d in diff if d.source == "unchanged"]
    assert added_names == ["A-new", "Z-new"]
    assert removed_names == ["C-old"]
    assert unchanged_names == ["B-old"]
    sources_in_order = [item.source for item in diff]
    first_added = next(
        i for i, s in enumerate(sources_in_order) if s == "added"
    )
    first_removed = next(
        i for i, s in enumerate(sources_in_order) if s == "removed"
    )
    first_unchanged = next(
        i for i, s in enumerate(sources_in_order) if s == "unchanged"
    )
    assert first_added < first_removed < first_unchanged


def test_compute_skills_diff_normalizes_via_normalize_skill():
    """D-20: case + hyphen/underscore-to-space collapse via _normalize_skill.

    ``_normalize_skill`` is ``lower().strip().replace("-", " ").replace("_", " ")``;
    therefore "Python"/"python" collapse, "fast-api"/"fast api" collapse, and
    "CI_CD"/"ci cd" collapse. NOTE: "FastAPI" and "fast api" do NOT collapse
    because the normalizer does not synthesize whitespace from camelCase. The
    test exercises the documented invariants only.
    """
    current = _profile(["Python", "Fast-API", "CI_CD"])
    extracted = [
        UserSkill(name="python"),
        UserSkill(name="fast api"),
        UserSkill(name="ci cd"),
    ]
    diff = compute_skills_diff(current, extracted)
    sources = {item.name: item.source for item in diff}
    assert all(s == "unchanged" for s in sources.values()), sources
    # Extracted-side casing wins for unchanged items
    assert "python" in sources
    assert "fast api" in sources
    assert "ci cd" in sources


# ----------------------------------------------------------------------
# Plan 07-04 Tasks 2-3 — POST /profile/upload, PATCH /profile, route tests
# fill below in subsequent commits.
# ----------------------------------------------------------------------
