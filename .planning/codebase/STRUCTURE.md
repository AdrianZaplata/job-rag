# Codebase Structure

**Analysis Date:** 2026-04-21

## Directory Layout

```
src/job_rag/
├── __init__.py              # Package marker
├── cli.py                   # Typer CLI commands (7 commands)
├── config.py                # Pydantic-settings for env vars
├── models.py                # Domain Pydantic models (JobPosting, JobRequirement, UserSkillProfile, enums)
├── logging.py               # Structlog setup
├── observability.py         # Langfuse integration (optional, fail-open)
│
├── db/                      # Database layer
│   ├── __init__.py
│   ├── engine.py            # SQLAlchemy sync + async engines, session factories, init_db()
│   └── models.py            # ORM models: JobPostingDB, JobRequirementDB, JobChunkDB
│
├── extraction/              # Ingestion: markdown → structured data
│   ├── __init__.py
│   ├── extractor.py         # Instructor + OpenAI integration, cost computation
│   └── prompt.py            # System prompt, few-shot examples, PROMPT_VERSION
│
├── services/                # Business logic (ingestion, retrieval, matching, embedding)
│   ├── __init__.py
│   ├── ingestion.py         # Read markdown → dedupe → extract → store pipeline
│   ├── embedding.py         # Batch embedding, section-based chunking
│   ├── retrieval.py         # pgvector search, cross-encoder reranking, RAG generation
│   └── matching.py          # Profile loading, skill matching, gap analysis
│
├── api/                     # FastAPI service layer
│   ├── __init__.py
│   ├── app.py               # FastAPI app factory, lifespan manager
│   ├── routes.py            # 8 endpoints (/health, /search, /match, /gaps, /ingest, /agent, /agent/stream)
│   ├── auth.py              # Bearer token auth, rate limiting per endpoint
│   └── deps.py              # Dependency injection (async session)
│
├── agent/                   # LangGraph ReAct agent
│   ├── __init__.py
│   ├── graph.py             # build_agent(), run_agent() — LangGraph + LLM integration
│   ├── stream.py            # stream_agent() — astream_events adapter
│   └── tools.py             # LangChain @tool wrappers around job_tools.*
│
└── mcp_server/              # FastMCP server for Claude Code
    ├── __init__.py
    ├── server.py            # FastMCP app factory, tool decorators (@mcp.tool())
    └── tools.py             # 4 async tool implementations (search_postings, match_skills, skill_gaps, ingest_posting)
```

## Directory Purposes

**`db/`:**
- Purpose: All database access and schema management
- Contains: SQLAlchemy sync/async engines, ORM models, session factories
- Key files: `engine.py` (entry point for DB setup), `models.py` (three tables)

**`extraction/`:**
- Purpose: Transform raw markdown into structured `JobPosting` objects
- Contains: Instructor client wrapper, OpenAI integration, extraction prompt, cost tracking
- Key files: `extractor.py` (main extraction function), `prompt.py` (versioned system prompt)

**`services/`:**
- Purpose: Core business logic independent of entry points
- Contains: Ingestion pipeline, vector search, profile matching, embedding generation
- Organized by concern, not by entry point (no duplication across API/agent/MCP)
- Key files: `ingestion.py` (ingest_directory, ingest_file), `retrieval.py` (search_postings, rerank, rag_query), `matching.py` (load_profile, match_posting, aggregate_gaps)

**`api/`:**
- Purpose: HTTP REST interface with FastAPI
- Contains: Route handlers, authentication middleware, rate limiting, async session dependency
- Key files: `routes.py` (endpoint implementations), `auth.py` (Bearer token + rate limit logic)

**`agent/`:**
- Purpose: LangGraph agent orchestration
- Contains: Agent graph construction, LLM model wiring, tool invocation
- Key files: `graph.py` (build_agent, run_agent), `tools.py` (LangChain @tool decorators)

**`mcp_server/`:**
- Purpose: MCP protocol server for Claude Code and other clients
- Contains: FastMCP app factory, tool definitions, session management
- Key files: `server.py` (app factory, tool decorators), `tools.py` (async implementations)

## Key File Locations

**Entry Points:**
- `src/job_rag/cli.py`: CLI commands (init-db, ingest, embed, serve, agent, mcp, reset, list, stats)
- `src/job_rag/api/app.py`: FastAPI app instance
- `src/job_rag/mcp_server/server.py`: MCP server instance
- `src/job_rag/agent/graph.py`: Agent graph factory

**Configuration:**
- `src/job_rag/config.py`: All settings from env vars (database URLs, OpenAI keys, Langfuse keys, model choices)
- Environment files: `.env` (not tracked) and `.env.example` (checked in)

**Core Logic:**
- Vector search: `src/job_rag/services/retrieval.py` (`search_postings`, `rerank`, `rag_query`)
- Profile matching: `src/job_rag/services/matching.py` (`match_posting`, `aggregate_gaps`)
- Extraction: `src/job_rag/extraction/extractor.py` (`extract_posting`)
- Ingestion: `src/job_rag/services/ingestion.py` (`ingest_directory`, `ingest_file`)

**Data Models:**
- API/Pydantic models: `src/job_rag/models.py` (JobPosting, JobRequirement, UserSkillProfile)
- ORM models: `src/job_rag/db/models.py` (JobPostingDB, JobRequirementDB, JobChunkDB)

**Tool Implementations (reused by all entry points):**
- Shared tool layer: `src/job_rag/mcp_server/tools.py` (search_postings, match_skills, skill_gaps, ingest_posting)
- Agent tools wrapper: `src/job_rag/agent/tools.py` (@tool decorators wrapping mcp_server.tools)
- API routes: `src/job_rag/api/routes.py` (HTTP endpoints calling same services)

**Testing:**
- Test directory: `tests/` (89 unit tests + 50 extraction accuracy tests)
- Fixtures and test data: `tests/fixtures/` (markdown samples, JSON profiles)

## Naming Conventions

**Files:**
- Modules: `snake_case.py` (e.g., `ingestion.py`, `embedding.py`)
- Classes: `PascalCase` (e.g., `JobPosting`, `AsyncSessionLocal`)
- Functions: `snake_case` (e.g., `extract_posting`, `search_postings`)

**Directories:**
- Feature areas: `snake_case` (e.g., `extraction`, `services`, `mcp_server`)
- No underscore prefix for private modules (Python convention; all are "private" to the package)

**Database Objects:**
- ORM models: Suffix `DB` (e.g., `JobPostingDB`, `JobRequirementDB`) to distinguish from Pydantic models
- Tables: Plural, snake_case (e.g., `job_postings`, `job_requirements`, `job_chunks`)

**Pydantic Models (API/domain):**
- No suffix; named by domain concept (e.g., `JobPosting`, `UserSkillProfile`)
- Enums: All caps (e.g., `SkillCategory`, `RemotePolicy`, `Seniority`)

## Where to Add New Code

**New Tool or Service:**
- If it performs retrieval/matching/analysis: Add to `src/job_rag/services/` as a pure async function
- Wire it into all three entry points:
  1. `src/job_rag/mcp_server/tools.py` — AsyncSessionLocal wrapper + serialization
  2. `src/job_rag/agent/tools.py` — LangChain `@tool` wrapper calling (1)
  3. `src/job_rag/api/routes.py` — HTTP endpoint calling (1)

**New Endpoint:**
- File: `src/job_rag/api/routes.py`
- Pattern: `@router.get(path, dependencies=[Depends(require_api_key), Depends(rate_limit)])` + async handler
- Access session via `session: Annotated[AsyncSession, Depends(get_session)]`
- Return dict (FastAPI serializes to JSON)

**New CLI Command:**
- File: `src/job_rag/cli.py`
- Pattern: `@app.command()` decorated function using Typer's `typer.echo()` for output
- Use sync `SessionLocal` from `src/job_rag/db/engine.py`
- Always close session in try/finally block

**New API Model:**
- File: `src/job_rag/models.py` (domain Pydantic models only)
- Example: `class MyRequest(BaseModel): field: str = Field(description="...")`

**New ORM Model:**
- File: `src/job_rag/db/models.py`
- Pattern: Inherit from `Base`, use `Mapped` type hints, declare indexes in `__table_args__`
- Remember to run `job-rag init-db` to apply migrations

**New Service Function:**
- File: Create or extend existing file in `src/job_rag/services/`
- Pattern: Pure async function, take `AsyncSession` as first param, return JSON-serializable dict or list
- Never import from `api/`, `agent/`, or `mcp_server/` (services are the bottom layer)

## Special Directories

**`data/`:**
- Purpose: Local data files (job postings, user profile)
- Generated: `data/postings/` populated by `job-rag ingest`
- `data/profile.json` — user skill profile (manually maintained JSON file)
- Committed: Only `.gitkeep` and example profile; actual data gitignored

**`tests/`:**
- Purpose: Unit tests and evaluation fixtures
- Generated: No
- Committed: All test code and fixtures checked in
- Coverage: 89 unit tests (mocked, no DB/API keys needed) + 50 extraction accuracy tests (marked as eval)

**`.planning/codebase/`:**
- Purpose: Architecture documentation (generated by gsd-map-codebase)
- Generated: Yes
- Committed: Yes (this directory)
- Files: ARCHITECTURE.md, STRUCTURE.md, CONVENTIONS.md, TESTING.md, CONCERNS.md, STACK.md, INTEGRATIONS.md

**`scripts/`:**
- Purpose: One-off utilities and evaluation
- Generated: No
- Committed: Yes
- Example: `scripts/evaluate.py` (RAGAS evaluation against golden dataset)

## Import Organization

**Pattern:**
1. Standard library (`import json`, `from pathlib import Path`)
2. Third-party packages (`import sqlalchemy`, `from pydantic import BaseModel`)
3. Local imports (`from job_rag.config import settings`)

**Path Aliases:**
- No custom aliases configured; all imports are relative to package root (`from job_rag.services.ingestion import ...`)

**Relative vs. Absolute:**
- All imports absolute within the package (no relative imports like `from . import ...`)

---

*Structure analysis: 2026-04-21*
