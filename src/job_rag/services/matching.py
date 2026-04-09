import json
from pathlib import Path
from typing import Any

from job_rag.config import settings
from job_rag.db.models import JobPostingDB
from job_rag.logging import get_logger
from job_rag.models import UserSkillProfile

log = get_logger(__name__)


def load_profile(path: str | None = None) -> UserSkillProfile:
    """Load user skill profile from JSON file."""
    profile_path = Path(path or settings.profile_path)
    data = json.loads(profile_path.read_text(encoding="utf-8"))
    return UserSkillProfile(**data)


def _normalize_skill(name: str) -> str:
    """Normalize skill name for fuzzy matching."""
    return name.lower().strip().replace("-", " ").replace("_", " ")


def _skill_matches(user_skills: set[str], job_skill: str) -> bool:
    """Check if a job skill matches any user skill (case-insensitive, fuzzy)."""
    normalized = _normalize_skill(job_skill)

    # Direct match
    if normalized in user_skills:
        return True

    # Common aliases
    aliases: dict[str, list[str]] = {
        "python": ["python"],
        "typescript": ["typescript", "ts"],
        "javascript": ["javascript", "js"],
        "react": ["react", "react.js", "reactjs"],
        "sql": ["sql", "postgresql", "postgres", "mysql"],
        "docker": ["docker", "containerization", "containers"],
        "git": ["git", "version control"],
        "openai api": ["openai api", "openai", "gpt", "gpt 4", "chatgpt"],
        "claude api": ["claude api", "claude", "anthropic"],
        "pytorch": ["pytorch", "torch"],
        "llm": ["llm", "large language model", "large language models"],
        "rag": ["rag", "retrieval augmented generation"],
        "rest api": ["rest api", "rest", "api design", "api development"],
        "ci/cd": ["ci/cd", "ci cd", "github actions", "continuous integration"],
        "agile": ["agile", "scrum", "kanban"],
        "communication": ["communication", "collaboration", "teamwork", "team player"],
        "ml": ["ml", "machine learning"],
        "nlp": ["nlp", "natural language processing"],
        "prompt engineering": ["prompt engineering", "prompting"],
        "pydantic": ["pydantic", "structured outputs"],
        "mcp": ["mcp", "model context protocol"],
        "hugging face": ["hugging face", "huggingface", "hf"],
        "fine tuning": ["fine tuning", "finetuning", "lora", "qlora"],
        "c++": ["c++", "cpp"],
        "c#": ["c#", "csharp"],
    }

    for user_skill in user_skills:
        user_aliases = aliases.get(user_skill, [user_skill])
        job_aliases = aliases.get(normalized, [normalized])
        if set(user_aliases) & set(job_aliases):
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
