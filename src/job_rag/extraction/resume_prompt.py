"""Resume extraction system prompt (Phase 7 D-12, D-14).

Pinned version travels in usage_info and Langfuse trace metadata; bump on
prompt changes (Phase 2 D-22 pattern).
"""

from job_rag.extraction.prompt import REJECTED_SOFT_SKILLS

RESUME_PROMPT_VERSION = "1.0"

# Spoken-language carve-outs per D-14: Adrian's profile lists English/German/
# Polish as language skills, which would otherwise pattern-match the
# soft-skill reject list (e.g. "communication") in user-language-skill
# contexts.
_SPOKEN_LANGUAGES = ("English", "German", "Polish")


# str.format() template — NOT an f-string. The `{{name}}` literal in the
# `skills` bullet below is brace-doubled so .format() emits a single brace
# pair into the rendered prompt (same caveat as extraction/prompt.py:53-60).
_SYSTEM_PROMPT_TEMPLATE = """\
You extract structured profile data from a resume / CV.

Return ONLY the fields in the `ResumeExtraction` schema:
- skills: a list of UserSkill objects with a single field {{name}}. Hard,
  technical, or domain skills only — tools, frameworks, programming
  languages, cloud services, databases, methodologies (e.g. RAG, MLOps),
  domain expertise (e.g. NLP, RecSys).
- target_roles: list of role titles the person targets (e.g. "AI Engineer",
  "ML Engineer"). Infer from "objective" / "target" / "looking for" sections.
- preferred_locations: list of city / country / region preferences.
- min_salary_eur: integer EUR/year if explicitly stated; otherwise null.
- remote_preference: one of "remote" | "hybrid" | "onsite" | "unknown".
- years_experience: integer years of professional experience if computable
  from the work history; otherwise null.

DO NOT extract soft skills. Reject these terms (case-insensitive): {rejected_terms}.

EXCEPTION — spoken-language proficiencies are LEGITIMATE hard skills.
Include "{english}", "{german}", "{polish}" (and other spoken languages) as
skills if the resume lists language proficiency. They are not the soft-skill
"communication" — they are language abilities.

Where information is absent or ambiguous, prefer empty lists / null over
guessing.
"""


RESUME_SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(
    rejected_terms=", ".join(REJECTED_SOFT_SKILLS),
    english=_SPOKEN_LANGUAGES[0],
    german=_SPOKEN_LANGUAGES[1],
    polish=_SPOKEN_LANGUAGES[2],
)


__all__ = ["RESUME_PROMPT_VERSION", "RESUME_SYSTEM_PROMPT"]
