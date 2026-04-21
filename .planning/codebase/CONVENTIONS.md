# Coding Conventions

**Analysis Date:** 2026-04-21

## Naming Patterns

**Files:**
- Modules use lowercase with underscores: `extractor.py`, `retrieval.py`, `matching.py`
- Database model files: `models.py` (SQLAlchemy tables) vs `models.py` (Pydantic schemas in different modules)
- Entry points: `cli.py`, `app.py` (FastAPI), `server.py` (MCP)
- Test files: `test_<module>.py` pattern (e.g., `test_extraction.py`)
- Config/setup: `config.py`, `logging.py`, `observability.py`

**Functions:**
- Camel case for public functions: `extract_posting()`, `search_postings()`, `match_posting()`
- Snake case consistently throughout: `get_logger()`, `get_openai_client()`, `get_reranker()`
- Async functions prefixed with async keyword, otherwise no naming distinction: `async def run_agent()`, `async def search_postings()`
- Private functions prefixed with single underscore: `_embed_query()`, `_normalize_skill()`, `_sanitize_delimiters()`, `_skill_matches()`
- Factory/builder functions: `build_agent()`, `get_session()`, `get_logger()`

**Variables:**
- Camel case for module-level constants used as config: `PROMPT_VERSION`, `AGENT_SYSTEM_PROMPT`, `RAG_SYSTEM_PROMPT`
- Snake case for all local variables: `user_skills`, `must_have`, `nice_to_have`, `posting_id`
- Global module state prefixed with underscore: `_reranker`, `_ALIAS_GROUPS`, `_ALIAS_INDEX`
- Type hints on function parameters and returns always present

**Types:**
- Pydantic models for data structures: `JobPosting`, `JobRequirement`, `UserSkillProfile`, `UserSkill`
- Enums for fixed sets: `SkillCategory`, `RemotePolicy`, `Seniority`, `SalaryPeriod` (use `StrEnum` for string enums)
- Return type annotations required: `dict[str, Any]`, `list[dict[str, Any]]`, `tuple[JobPosting, dict]`
- Union types use `|` operator (Python 3.10+ syntax): `str | None`, `list[str] | None`

## Code Style

**Formatting:**
- Line length: 100 characters (enforced by ruff, see `pyproject.toml`)
- Indentation: 4 spaces (Python standard)
- No trailing commas except in multiline collections
- Imports organized by ruff's import rules (see Import Organization below)

**Linting:**
- Tool: ruff (see `.github/workflows/ci.yml` and `pyproject.toml`)
- Selected rules: `E` (pycodestyle errors), `F` (Pyflakes), `I` (isort/import sorting), `UP` (pyupgrade)
- Target version: Python 3.12
- Run via CI: `uv run ruff check src/ tests/`
- Fix mode available: `uv run ruff check --fix`

**Type Checking:**
- Tool: pyright
- Mode: "basic" (see `pyproject.toml` `[tool.pyright]`)
- Python version: 3.12
- Run via CI: `uv run pyright src/`
- Type hints are expected on public functions; private functions benefit from hints but stricter enforcement is at "basic" level

## Import Organization

**Order:**
1. Standard library imports: `import json`, `from pathlib import Path`, `from typing import Any`
2. Third-party imports: `import pytest`, `from pydantic import BaseModel`, `from sqlalchemy import select`
3. Local imports: `from job_rag.config import settings`, `from job_rag.models import JobPosting`

**Path Aliases:**
- No path aliases configured; all imports use absolute paths from package root
- Example: `from job_rag.services.retrieval import search_postings` (not relative imports like `from ..services`)

**Lazy Imports:**
- Used in observability module to defer expensive imports when not enabled: see `src/job_rag/observability.py` lines 47, 62
- Pattern: conditional import inside a function to delay import cost until actually needed
```python
if is_enabled():
    from langfuse.openai import OpenAI as LangfuseOpenAI
```

## Error Handling

**Patterns:**
- Tenacity for automatic retries with exponential backoff: `@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))` in `src/job_rag/extraction/extractor.py` line 36
- Try-except with logging for best-effort operations: `src/job_rag/observability.py` lines 78-83 (Langfuse flush)
- HTTPException for API responses: `raise HTTPException(status_code=404, detail="Posting not found")` in `src/job_rag/api/routes.py` line 93
- Validation errors via Pydantic: `ValidationError` raised automatically for schema violations
- Fail-open observability: when Langfuse is disabled, functions return empty lists or None-safe defaults (no errors)
- Error dictionaries returned from tools (MCP server): `{"error": "posting_not_found", "posting_id": posting_id}` in `src/job_rag/mcp_server/tools.py` line 98

**Error Handling Principle:**
- Extraction and LLM calls fail gracefully with retries; if all retries exhausted, exception propagates to API/CLI caller
- Search and retrieval operations return empty results rather than raising (fail-open for UX)
- Security validations (file path, content size) return error objects to MCP tools
- API endpoints use FastAPI's HTTPException for clean error responses

## Logging

**Framework:** structlog

**Configuration (src/job_rag/logging.py):**
- Configured with: contextvars merge, log level processor, ISO timestamp, ConsoleRenderer for dev-friendly output
- Factory: `PrintLoggerFactory` (logs to stdout)
- Context type: dict

**Patterns:**
- Get logger: `log = get_logger(__name__)` at module top level
- Structured logging with keyword arguments: `log.info("extraction_complete", company=posting.company, title=posting.title, requirements_count=len(posting.requirements), **usage_info)`
- Event name as first positional arg: `log.info("event_name", key1=value1, key2=value2)`
- Examples from codebase:
  - `src/job_rag/extraction/extractor.py` line 75: logs extraction completion with structured data
  - `src/job_rag/services/retrieval.py` line 238: logs RAG query completion with stats
  - `src/job_rag/observability.py` line 49: logs client initialization with provider
  - `src/job_rag/agent/graph.py` line 56: logs agent build with model and tool count

**When to Log:**
- Significant operations: LLM calls, database queries, agent tool invocations
- Configuration changes: observability initialization, model selection
- Errors and warnings: via `log.warning()` for recoverable issues (e.g., Langfuse flush failure)
- Do not log: individual loop iterations, internal helper function calls, sensitive user data

## Comments

**When to Comment:**
- Explain the "why" when logic is not obvious: see `src/job_rag/services/matching.py` line 25 (alias groups explanation)
- Document formula/scoring logic: see `src/job_rag/services/matching.py` line 63 (match score formula as docstring)
- Security-sensitive code: see `src/job_rag/extraction/extractor.py` line 32 (prompt injection prevention explanation)
- Workarounds and known limitations: see `.github/workflows/ci.yml` line 36 (CVE note)

**JSDoc/TSDoc:**
- Not used; Python uses docstrings instead
- Docstrings: triple-quoted strings on function/class definitions
- Style: One-liner summary followed by blank line, then description and return type info
- Examples:
  ```python
  def extract_posting(raw_text: str) -> tuple[JobPosting, dict]:
      """Extract structured data from a job posting using Instructor.

      Returns a tuple of (JobPosting, usage_info) where usage_info contains
      token counts and cost.
      """
  ```

## Function Design

**Size:** 
- Aim for single responsibility; most functions 10-50 lines
- Extraction function (`extract_posting`) is ~50 lines including docstring and logging
- Retrieval pipeline (`rag_query`) is ~80 lines for full orchestration
- Utility functions (`_skill_matches`, `_normalize_skill`) are 5-10 lines

**Parameters:**
- Required parameters first, then keyword-only arguments after `*` if appropriate
- Examples: `search_postings(session, query, *, top_k=20, seniority=None, remote=None, min_salary=None)`
- Type hints on all parameters
- Use Annotated for dependency injection in FastAPI: `Session = Annotated[AsyncSession, Depends(get_session)]`

**Return Values:**
- Explicit return type annotation required
- Dictionary returns favor `dict[str, Any]` for flexibility, with clear documentation of keys
- Tuple returns used for multi-value returns: `tuple[JobPosting, dict]` for extraction results
- Async functions return same types as sync equivalents, wrapped in coroutine
- Empty result safety: functions return empty list/dict rather than None (except when None is semantically meaningful like `salary_min: int | None`)

## Module Design

**Exports:**
- Explicit `__all__` only in package-level `__init__.py` files: see `src/job_rag/agent/__init__.py`
- Otherwise, all public functions/classes importable by convention (no leading underscore)

**Barrel Files:**
- Minimal use; agent module has one: `src/job_rag/agent/__init__.py` re-exports `build_agent` and `run_agent`
- Most modules imported directly: `from job_rag.services.retrieval import search_postings`

**Async/Sync Split:**
- Services layer has async functions for database operations: `search_postings(session, ...)`, `rag_query(session, ...)`
- Extraction is sync but wrapped with `@retry` decorator for robustness
- API routes all async: `async def search(...)`
- Utility/helper functions (matching logic, normalization) are sync; they don't call I/O
- CLI commands call async code via `asyncio.run()` or similar event loop management

## Code Examples

**Type hints with union and defaults:**
```python
async def search_postings(
    session: AsyncSession,
    query: str,
    *,
    top_k: int = 20,
    seniority: str | None = None,
    remote: str | None = None,
    min_salary: int | None = None,
) -> list[dict[str, Any]]:
```

**Tenacity retry pattern:**
```python
@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))
def extract_posting(raw_text: str) -> tuple[JobPosting, dict]:
    """Extract structured data from a job posting."""
```

**Structured logging:**
```python
log.info(
    "extraction_complete",
    company=posting.company,
    title=posting.title,
    requirements_count=len(posting.requirements),
    **usage_info,
)
```

**Private helper with prefix:**
```python
def _normalize_skill(name: str) -> str:
    """Normalize skill name for fuzzy matching."""
    return name.lower().strip().replace("-", " ").replace("_", " ")
```

**Pydantic model with StrEnum:**
```python
class RemotePolicy(StrEnum):
    REMOTE = "remote"
    HYBRID = "hybrid"
    ONSITE = "onsite"
    UNKNOWN = "unknown"
```

---

*Convention analysis: 2026-04-21*
