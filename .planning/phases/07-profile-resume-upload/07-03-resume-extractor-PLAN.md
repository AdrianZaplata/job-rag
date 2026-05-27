---
phase: 07-profile-resume-upload
plan: 03
type: execute
wave: 1
depends_on: [01]
files_modified:
  - src/job_rag/extraction/resume_prompt.py
  - src/job_rag/extraction/resume_extractor.py
  - src/job_rag/models.py
  - tests/test_resume_extractor.py
autonomous: true
requirements: [PROF-02, PROF-03]
requirements_addressed: [PROF-02, PROF-03]

must_haves:
  truths:
    - "RESUME_PROMPT_VERSION constant equals '1.0' and is importable from src/job_rag/extraction/resume_prompt.py"
    - "RESUME_SYSTEM_PROMPT references the REJECTED_SOFT_SKILLS tuple imported from extraction/prompt.py"
    - "ResumeExtraction Pydantic model exists in src/job_rag/models.py with all 6 fields per D-13 (skills, target_roles, preferred_locations, min_salary_eur, remote_preference, years_experience)"
    - "extract_resume(text) returns (ResumeExtraction, usage_info) tuple after a successful Instructor call"
    - "tenacity @retry decorator retries 3 times with exponential backoff then re-raises"
    - "Prompt explicitly carves out 'English', 'German', 'Polish' as spoken-language exceptions to the soft-skill rejection"
  artifacts:
    - path: "src/job_rag/extraction/resume_prompt.py"
      provides: "RESUME_PROMPT_VERSION + RESUME_SYSTEM_PROMPT constants"
      contains: "RESUME_PROMPT_VERSION"
    - path: "src/job_rag/extraction/resume_extractor.py"
      provides: "extract_resume(text) sync function with @retry"
      contains: "def extract_resume"
    - path: "src/job_rag/models.py"
      provides: "ResumeExtraction Pydantic model"
      contains: "class ResumeExtraction"
    - path: "tests/test_resume_extractor.py"
      provides: "Structured-output + retry behavior + prompt-structure tests"
      contains: "test_extract_resume"
  key_links:
    - from: "src/job_rag/extraction/resume_extractor.py"
      to: "src/job_rag/extraction/resume_prompt.py"
      via: "import RESUME_SYSTEM_PROMPT, RESUME_PROMPT_VERSION"
      pattern: "from job_rag.extraction.resume_prompt import"
    - from: "src/job_rag/extraction/resume_prompt.py"
      to: "src/job_rag/extraction/prompt.py"
      via: "import REJECTED_SOFT_SKILLS"
      pattern: "from job_rag.extraction.prompt import REJECTED_SOFT_SKILLS"
    - from: "src/job_rag/extraction/resume_extractor.py"
      to: "src/job_rag/models.py"
      via: "response_model=ResumeExtraction"
      pattern: "response_model=ResumeExtraction"
---

<objective>
Land the resume extraction primitives: the pinned-version system prompt, the Instructor-wrapped sync extractor function, the `ResumeExtraction` Pydantic model, and the prompt+retry+structured-output test coverage. This plan delivers PROF-02 (parser deps already in Plan 01) and PROF-03 (versioned prompt + Instructor + structured output) so Plan 04 can wire the route handler against these primitives.

Purpose: Reuse the Phase 2 extraction pattern verbatim — `@retry(wait_exponential, stop_after_attempt(3))` + `instructor.from_openai` + `chat.completions.create_with_completion`. Soft-skill rejection rules are imported from `extraction/prompt.py::REJECTED_SOFT_SKILLS` (D-14) with spoken-language carve-outs (English/German/Polish per D-14).
Output: 2 new extraction modules + 1 model addition + 1 new test file.
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/STATE.md
@.planning/phases/07-profile-resume-upload/07-CONTEXT.md
@.planning/phases/07-profile-resume-upload/07-RESEARCH.md
@.planning/phases/07-profile-resume-upload/07-PATTERNS.md
@.planning/phases/07-profile-resume-upload/07-VALIDATION.md
@src/job_rag/extraction/extractor.py
@src/job_rag/extraction/prompt.py
@src/job_rag/models.py
@src/job_rag/config.py
@src/job_rag/observability.py
@tests/test_extraction.py

<interfaces>
<!-- Existing pattern in extractor.py:36-83 — Instructor + @retry shape -->
```python
@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def extract_posting(raw_text: str) -> tuple[JobPosting, dict]:
    client = instructor.from_openai(get_openai_client())
    posting, completion = client.chat.completions.create_with_completion(
        model=settings.openai_model,
        response_model=JobPosting,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"<job_posting>\n{_sanitize_delimiters(raw_text)}\n</job_posting>"},
        ],
    )
    # ... usage_info ...
    return posting, usage_info
```

<!-- Existing prompt.py shape (lines 22-50, 137-141) -->
```python
PROMPT_VERSION = "2.0"

REJECTED_SOFT_SKILLS: tuple[str, ...] = (
    "communication", "teamwork", "problem-solving",
    # ... ~22 terms total
)

SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(
    rejected_terms=", ".join(REJECTED_SOFT_SKILLS),
)
```

<!-- Existing UserSkillProfile (models.py:147-158) — the analog for ResumeExtraction -->
```python
class UserSkillProfile(BaseModel):
    skills: list[UserSkill] = Field(description="User skills")
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    min_salary: int | None = Field(default=None)
    remote_preference: RemotePolicy = Field(default=RemotePolicy.UNKNOWN)
```

<!-- D-13 target ResumeExtraction shape -->
```python
class ResumeExtraction(BaseModel):
    skills: list[UserSkill]
    target_roles: list[str] = []
    preferred_locations: list[str] = []
    min_salary_eur: int | None = None    # NOTE: _eur suffix differs from UserSkillProfile.min_salary
    remote_preference: RemotePolicy = RemotePolicy.UNKNOWN
    years_experience: int | None = None
```
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| extracted resume text → LLM system prompt | User-controlled content reaches the LLM; prompt injection could attempt to override extraction rules |
| LLM response → Pydantic schema | Untrusted LLM output must be type-validated before reaching the response handler |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-04 | Tampering (Prompt injection) | extract_resume / RESUME_SYSTEM_PROMPT | mitigate | Instructor + structured Pydantic `response_model=ResumeExtraction` constrains LLM output to typed fields; malicious instructions cannot exfiltrate or alter response shape. Prompt does NOT wrap user text in delimiter tags (extractor.py uses `<job_posting>` for that path; resume text is passed bare since the structured output schema is the guardrail). Validated by `test_extract_resume_returns_resume_extraction` (07-03-04) and `test_extract_resume_retries_3x_then_raises` (07-03-05). |
</threat_model>

<tasks>

<task type="auto" id="07-03-01">
  <name>Task 1: Author resume_prompt.py + ResumeExtraction model + resume_extractor.py</name>
  <files>src/job_rag/extraction/resume_prompt.py, src/job_rag/models.py, src/job_rag/extraction/resume_extractor.py</files>
  <read_first>
    - src/job_rag/extraction/prompt.py (FULL file — REJECTED_SOFT_SKILLS tuple at lines 27-50; SYSTEM_PROMPT template structure lines 137-141; brace-doubling caveat lines 53-60)
    - src/job_rag/extraction/extractor.py (FULL file — Instructor + @retry pattern lines 36-83; usage_info structure lines 75-83)
    - src/job_rag/models.py (lines 141-158 — UserSkill, UserSkillProfile, RemotePolicy)
    - src/job_rag/observability.py (get_openai_client lines 39-54)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §3 lines 109-152 (extract_resume shape)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §1 lines 49-114 (resume_extractor analog)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §2 lines 117-141 (resume_prompt analog)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §8 lines 415-450 (ResumeExtraction sibling pattern)
  </read_first>
  <action>
**Step A — Create `src/job_rag/extraction/resume_prompt.py`:**

```python
"""Resume extraction system prompt (Phase 7 D-12, D-14).

Pinned version travels in usage_info and Langfuse trace metadata; bump on
prompt changes (Phase 2 D-22 pattern).
"""
from job_rag.extraction.prompt import REJECTED_SOFT_SKILLS

RESUME_PROMPT_VERSION = "1.0"

# Spoken-language carve-outs per D-14: Adrian's profile lists English/German/
# Polish as language skills, which would otherwise pattern-match the soft-skill
# reject list (e.g. "communication") in user-language-skill contexts.
_SPOKEN_LANGUAGES = ("English", "German", "Polish")

_SYSTEM_PROMPT_TEMPLATE = """\
You extract structured profile data from a resume / CV.

Return ONLY the fields in the `ResumeExtraction` schema:
- skills: a list of UserSkill objects {{name, level, category}}. Hard/technical/
  domain skills only. Tools, frameworks, programming languages, cloud services,
  databases, methodologies (e.g. RAG, MLOps), domain expertise (e.g. NLP, RecSys).
- target_roles: list of role titles the person targets (e.g. "AI Engineer",
  "ML Engineer"). Infer from "objective" / "target" / "looking for" sections.
- preferred_locations: list of city/country/region preferences.
- min_salary_eur: integer EUR/year if explicitly stated; otherwise null.
- remote_preference: one of "remote" | "hybrid" | "onsite" | "unknown".
- years_experience: integer years of professional experience if computable
  from work history; otherwise null.

DO NOT extract soft skills. Reject these terms (case-insensitive): {rejected_terms}.

EXCEPTION — spoken-language proficiencies are LEGITIMATE hard skills. Include
"{english}", "{german}", "{polish}" (and other spoken languages) as skills if
the resume lists language proficiency. They are not the soft-skill
"communication" — they are language abilities.

Where information is absent or ambiguous, prefer empty lists / null over guessing.
"""

RESUME_SYSTEM_PROMPT = _SYSTEM_PROMPT_TEMPLATE.format(
    rejected_terms=", ".join(REJECTED_SOFT_SKILLS),
    english=_SPOKEN_LANGUAGES[0],
    german=_SPOKEN_LANGUAGES[1],
    polish=_SPOKEN_LANGUAGES[2],
)

__all__ = ["RESUME_PROMPT_VERSION", "RESUME_SYSTEM_PROMPT"]
```

Note: `.format(...)` only. NO f-string. The template literal `{{name, level, category}}` brace-doubling avoids `KeyError` during `.format()` — same caveat called out in `extraction/prompt.py:53-60`.

**Step B — Add `ResumeExtraction` to `src/job_rag/models.py`:**

Place AFTER `UserSkillProfile` (around line 158). Per D-13:

```python
class ResumeExtraction(BaseModel):
    """LLM-extracted resume contents (Phase 7 D-13).

    Sibling of UserSkillProfile. Decoupled so extraction format can evolve
    (e.g. add companies_worked_at) without coupling the canonical user state.
    Note: uses `min_salary_eur` (not `min_salary`) because Instructor needs
    explicit unit hints to parse salary numbers correctly.
    """

    skills: list[UserSkill] = Field(description="Extracted user skills")
    target_roles: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    min_salary_eur: int | None = Field(
        default=None, description="Minimum acceptable salary in EUR/year"
    )
    remote_preference: RemotePolicy = Field(default=RemotePolicy.UNKNOWN)
    years_experience: int | None = Field(
        default=None, description="Years of professional experience"
    )
```

**Step C — Create `src/job_rag/extraction/resume_extractor.py`:**

```python
"""Resume extractor — Instructor + tenacity + structured output (Phase 7 D-15)."""

import instructor
from tenacity import retry, stop_after_attempt, wait_exponential

from job_rag.config import settings
from job_rag.extraction.resume_prompt import RESUME_PROMPT_VERSION, RESUME_SYSTEM_PROMPT
from job_rag.logging import get_logger
from job_rag.models import ResumeExtraction
from job_rag.observability import get_openai_client

log = get_logger(__name__)


@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def extract_resume(text: str) -> tuple[ResumeExtraction, dict]:
    """Extract structured ResumeExtraction from raw resume text.

    Sync function (mirrors extract_posting). Called from the async upload route
    via `await asyncio.to_thread(extract_resume, text)` to avoid blocking the
    event loop (Phase 1 D-05 reranker pattern).

    After 3 retries, tenacity re-raises the underlying exception:
    - `pydantic.ValidationError` → upload route maps to 422 `extraction_failed`
    - `openai.APIError` family → 503 `llm_unavailable`
    """
    client = instructor.from_openai(get_openai_client())

    extraction, completion = client.chat.completions.create_with_completion(
        model=settings.openai_model,
        response_model=ResumeExtraction,
        messages=[
            {"role": "system", "content": RESUME_SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
    )

    usage = completion.usage
    prompt_tokens = usage.prompt_tokens if usage else 0
    completion_tokens = usage.completion_tokens if usage else 0

    usage_info = {
        "model": settings.openai_model,
        "prompt_version": RESUME_PROMPT_VERSION,
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }
    log.info(
        "resume_extraction_complete",
        skills_count=len(extraction.skills),
        **usage_info,
    )
    return extraction, usage_info
```

NOTE: do NOT include the `_sanitize_delimiters` wrap and `<job_posting>` tags from `extract_posting`. Per RESEARCH §3 line 111 and PATTERNS §1 line 111, "Drop the `<job_posting>` delimiter (resume text has no injection-prone tag; D-15 doesn't mention sanitisation)." The structured output schema is the prompt-injection guardrail (T-07-04 disposition).

**Step D — Smoke-test imports:**

```bash
uv run python -c "
from job_rag.extraction.resume_prompt import RESUME_PROMPT_VERSION, RESUME_SYSTEM_PROMPT
from job_rag.extraction.resume_extractor import extract_resume
from job_rag.models import ResumeExtraction

assert RESUME_PROMPT_VERSION == '1.0'
assert 'communication' in RESUME_SYSTEM_PROMPT
assert 'English' in RESUME_SYSTEM_PROMPT
assert 'German' in RESUME_SYSTEM_PROMPT
assert 'Polish' in RESUME_SYSTEM_PROMPT

m = ResumeExtraction.model_json_schema()
required_fields = {'skills', 'target_roles', 'preferred_locations', 'min_salary_eur', 'remote_preference', 'years_experience'}
assert required_fields <= m['properties'].keys(), m['properties'].keys()

print('OK')
"
```

`uv run pyright src/job_rag/extraction/resume_extractor.py src/job_rag/extraction/resume_prompt.py src/job_rag/models.py` must exit 0.
  </action>
  <verify>
    <automated>uv run python -c "from job_rag.extraction.resume_prompt import RESUME_PROMPT_VERSION, RESUME_SYSTEM_PROMPT; assert RESUME_PROMPT_VERSION == '1.0'; assert 'communication' in RESUME_SYSTEM_PROMPT and 'English' in RESUME_SYSTEM_PROMPT and 'German' in RESUME_SYSTEM_PROMPT and 'Polish' in RESUME_SYSTEM_PROMPT; from job_rag.models import ResumeExtraction; m = ResumeExtraction.model_json_schema(); assert {'skills','target_roles','preferred_locations','min_salary_eur','remote_preference','years_experience'} <= m['properties'].keys()" && uv run pyright src/job_rag/extraction/resume_extractor.py src/job_rag/extraction/resume_prompt.py src/job_rag/models.py</automated>
  </verify>
  <acceptance_criteria>
    - `RESUME_PROMPT_VERSION == "1.0"` (VALIDATION 07-03-01)
    - `grep REJECTED_SOFT_SKILLS src/job_rag/extraction/resume_prompt.py` returns the import line (VALIDATION 07-03-02)
    - `ResumeExtraction.model_json_schema()["properties"]` includes all 6 required fields (VALIDATION 07-03-03)
    - "English", "German", "Polish" all appear verbatim in `RESUME_SYSTEM_PROMPT`
    - `pyright src/` exits 0 for the three new/modified files
  </acceptance_criteria>
  <done>
    - 3 production files committed
    - Smoke-test command above prints "OK"
  </done>
</task>

<task type="auto" id="07-03-02" tdd="true">
  <name>Task 2: Write resume_extractor tests (structured output + 3x retry + prompt structure)</name>
  <files>tests/test_resume_extractor.py</files>
  <read_first>
    - tests/test_extraction.py (lines 39-189 — analog mock-Instructor pattern + TestPromptStructure + TestRejectionRules)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §12 lines 547-579 (resume_extractor test analog)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md Validation Architecture PROF-03 table (lines 542-548)
    - src/job_rag/extraction/resume_extractor.py (just-written; tests target this)
    - src/job_rag/extraction/resume_prompt.py (just-written; prompt-structure tests target this)
    - src/job_rag/extraction/prompt.py (REJECTED_SOFT_SKILLS source — test asserts all terms passed through to RESUME_SYSTEM_PROMPT)
  </read_first>
  <behavior>
    - Test 1 (test_extract_resume_returns_resume_extraction_and_usage): mock Instructor; assert `extract_resume("fake text")` returns `(ResumeExtraction, dict)` tuple; `usage_info["prompt_version"] == "1.0"`
    - Test 2 (test_extract_resume_retries_3x_then_raises): mock the OpenAI client to raise `pydantic.ValidationError` on every call; assert `extract_resume()` is called 3 times then re-raises; verify via mock call_count
    - Test 3 (test_rejected_terms_in_resume_system_prompt): for term in REJECTED_SOFT_SKILLS, assert `term in RESUME_SYSTEM_PROMPT`
    - Test 4 (test_spoken_language_carveouts): assert "English", "German", "Polish" appear in RESUME_SYSTEM_PROMPT
    - Test 5 (test_resume_extraction_schema_shape): assert ResumeExtraction has all 6 D-13 fields
  </behavior>
  <action>
Create `tests/test_resume_extractor.py`. Mirror the structure of `tests/test_extraction.py::TestExtractPosting + TestPromptStructure + TestRejectionRulesUnit`. Use `unittest.mock.patch` + `MagicMock` for the Instructor wrapper.

```python
"""Tests for src/job_rag/extraction/resume_extractor.py (PROF-03)."""

from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from job_rag.extraction.prompt import REJECTED_SOFT_SKILLS
from job_rag.extraction.resume_extractor import extract_resume
from job_rag.extraction.resume_prompt import RESUME_PROMPT_VERSION, RESUME_SYSTEM_PROMPT
from job_rag.models import ResumeExtraction, RemotePolicy, UserSkill


class TestExtractResume:
    def test_extract_resume_returns_resume_extraction_and_usage(self):
        """structured_output: Instructor returns ResumeExtraction + usage_info dict (D-15)."""
        mock_extraction = ResumeExtraction(
            skills=[UserSkill(name="Python")],
            target_roles=["AI Engineer"],
            preferred_locations=["Berlin"],
            min_salary_eur=70000,
            remote_preference=RemotePolicy.REMOTE,
            years_experience=5,
        )
        mock_completion = MagicMock()
        mock_completion.usage.prompt_tokens = 100
        mock_completion.usage.completion_tokens = 50

        with patch("job_rag.extraction.resume_extractor.instructor") as mock_instructor:
            mock_client = MagicMock()
            mock_instructor.from_openai.return_value = mock_client
            mock_client.chat.completions.create_with_completion.return_value = (
                mock_extraction,
                mock_completion,
            )
            extraction, usage_info = extract_resume("TEST FIXTURE — synthetic resume text")

        assert isinstance(extraction, ResumeExtraction)
        assert extraction.skills[0].name == "Python"
        assert usage_info["prompt_version"] == RESUME_PROMPT_VERSION
        assert usage_info["prompt_tokens"] == 100
        assert usage_info["completion_tokens"] == 50

    def test_extract_resume_retries_3x_then_raises(self):
        """retries_3x: tenacity retries on ValidationError 3 times then re-raises (D-15, D-16)."""
        # ValidationError needs at least one line item — fabricate via a dummy model
        from pydantic import BaseModel

        class _Dummy(BaseModel):
            x: int

        try:
            _Dummy(x="not-an-int")
        except ValidationError as e:
            sample_error = e

        with patch("job_rag.extraction.resume_extractor.instructor") as mock_instructor:
            mock_client = MagicMock()
            mock_instructor.from_openai.return_value = mock_client
            mock_client.chat.completions.create_with_completion.side_effect = sample_error

            with pytest.raises(ValidationError):
                extract_resume("anything")

            # 3 attempts per tenacity @retry(stop_after_attempt(3))
            assert mock_client.chat.completions.create_with_completion.call_count == 3


class TestResumePromptStructure:
    def test_rejected_terms_in_system_prompt(self):
        """D-14: every REJECTED_SOFT_SKILLS term flows into RESUME_SYSTEM_PROMPT."""
        for term in REJECTED_SOFT_SKILLS:
            assert term in RESUME_SYSTEM_PROMPT, f"missing rejection term: {term!r}"

    def test_spoken_language_carveouts(self):
        """D-14 carve-out: English/German/Polish are explicitly allowed as skills."""
        assert "English" in RESUME_SYSTEM_PROMPT
        assert "German" in RESUME_SYSTEM_PROMPT
        assert "Polish" in RESUME_SYSTEM_PROMPT

    def test_prompt_version_is_string(self):
        """D-12: RESUME_PROMPT_VERSION is a string and is pinned to '1.0' for v1."""
        assert isinstance(RESUME_PROMPT_VERSION, str)
        assert RESUME_PROMPT_VERSION == "1.0"


class TestResumeExtractionSchema:
    def test_six_fields_present(self):
        """D-13: ResumeExtraction has the 6 documented fields."""
        schema = ResumeExtraction.model_json_schema()
        expected = {
            "skills",
            "target_roles",
            "preferred_locations",
            "min_salary_eur",
            "remote_preference",
            "years_experience",
        }
        assert expected <= set(schema["properties"].keys()), schema["properties"].keys()

    def test_defaults_match_d13(self):
        """D-13: target_roles/preferred_locations default to empty list; salary/years_experience nullable."""
        m = ResumeExtraction(skills=[])
        assert m.target_roles == []
        assert m.preferred_locations == []
        assert m.min_salary_eur is None
        assert m.years_experience is None
        assert m.remote_preference == RemotePolicy.UNKNOWN
```

Run RED→GREEN cycle:
1. Initial run (Plan 01 created an empty scaffold): `uv run pytest tests/test_resume_extractor.py -x` — empty file should pass with 0 tests.
2. Write the tests above. Re-run: `uv run pytest tests/test_resume_extractor.py -x`. All 7 tests should pass (assuming Task 1 production code is committed first).
3. If any test fails, fix the production code in Task 1 — tests are the contract.
  </action>
  <verify>
    <automated>uv run pytest tests/test_resume_extractor.py -x -v 2>&1 | tail -20 && uv run pytest tests/test_resume_extractor.py -k 'structured_output or retries_3x' -x</automated>
  </verify>
  <acceptance_criteria>
    - `uv run pytest tests/test_resume_extractor.py -k structured_output -x` passes (VALIDATION 07-03-04)
    - `uv run pytest tests/test_resume_extractor.py -k retries_3x -x` passes (VALIDATION 07-03-05)
    - All `TestResumePromptStructure` tests pass
    - All `TestResumeExtractionSchema` tests pass
    - Total: 7 tests, all green, runtime <5 seconds
  </acceptance_criteria>
  <done>
    - `tests/test_resume_extractor.py` committed with 3 test classes / 7 tests
    - `uv run pytest tests/test_resume_extractor.py -x` exits 0
  </done>
</task>

</tasks>

<verification>
After both tasks land:

```bash
# Static — modules importable + constants pinned
uv run python -c "from job_rag.extraction.resume_prompt import RESUME_PROMPT_VERSION; assert RESUME_PROMPT_VERSION == '1.0'"
uv run python -c "from job_rag.models import ResumeExtraction; ResumeExtraction(skills=[])"
uv run python -c "from job_rag.extraction.resume_extractor import extract_resume"

# Targeted tests
uv run pytest tests/test_resume_extractor.py -x

# Static type check
uv run pyright src/job_rag/extraction/

# Full backend suite (regression)
uv run pytest tests/ -x
```

All commands must exit 0.
</verification>

<success_criteria>
- PROF-03 closed at the extractor primitives level: pinned prompt version, structured Pydantic output, tenacity retry behavior
- Soft-skill rejection passes through from `prompt.py` (no duplication)
- Spoken-language carve-out explicit in prompt (Adrian's English/German/Polish skills won't be filtered)
- T-07-04 prompt-injection threat mitigated via structured response_model guardrail
</success_criteria>

<output>
After completion, create `.planning/phases/07-profile-resume-upload/07-03-SUMMARY.md` capturing:
- Final RESUME_SYSTEM_PROMPT character count
- Number of REJECTED_SOFT_SKILLS terms that flowed through
- Token/cost estimate for a typical resume extraction (use the `usage_info` from a manual test call against a fixture if budget allows)
</output>
