<!-- GSD:project-start source:PROJECT.md -->
## Project

**job-rag**

A private web app that productizes the existing job-rag backend (Python 3.12 / FastAPI / LangGraph / PostgreSQL+pgvector) into a usable tool for Adrian's AI-Engineer job hunt in the Berlin / German / remote market. Two surfaces on top of the current RAG/agent stack: a **Dashboard** for browsing the corpus at a glance (top skills, salary bands, country-filtered views, CV-vs-market match score) and a **Chat** page that streams the existing LangGraph ReAct agent. Deployed to Azure on free tier. Single-user in v1 but structurally platform-ready so it can evolve into a multi-user career-investigation product without a rewrite.

**Core Value:** Make Adrian's job-market corpus actually useful for his job hunt — browse it, question it, measure his CV against it — while simultaneously fulfilling as a portfolio artifact that maps to concrete cloud / MLOps / SQL skill gaps on real AI-Engineer job ads.

### Constraints

- **Tech stack (frozen)**: Python 3.12, FastAPI, LangGraph 1.1.x, PostgreSQL 17 + pgvector, SQLAlchemy 2.x async, Instructor, OpenAI SDK. The backend stack is inherited; this milestone doesn't introduce new backend frameworks.
- **Frontend stack (chosen)**: Vite + React 18+ + TypeScript, Tailwind CSS, shadcn/ui, MSAL React for Entra ID. Pure SPA — no SSR.
- **Cloud provider (chosen)**: Azure only. No multi-cloud.
- **Budget**: target €0/month on Azure free tier for year 1; ≤ €20/month year 2 (via DB stop + scale-to-zero).
- **IaC**: Terraform only. Bicep / ARM / CLI scripts not used.
- **Single user (structurally multi-user)**: v1 has one user (Adrian) but every table carries `user_id` and every query filters by it.
- **One cloud, one provider per concern**: managed Postgres (Azure DB), managed secrets (Key Vault), managed identity (Entra ID), managed containers (Container Apps), managed static hosting (Static Web Apps), managed CI (GitHub Actions + OIDC). Don't mix in third-party equivalents.
- **Educational goal**: the frontend and backend must remain cleanly separated. Logic that belongs in the backend cannot live in the frontend, and vice versa.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:codebase/STACK.md -->
## Technology Stack

## Languages
- Python 3.12 - All application code, CLI, API, agent, and data processing
- Markdown - Job posting corpus format (stored as markdown files in `data/postings/`)
## Runtime
- Python 3.12 (specified in `pyproject.toml` with `requires-python = ">=3.12"`)
- Docker: Python 3.12-slim-bookworm (multi-stage build for optimized image size)
- uv (ultra-fast Python package manager)
- Lockfile: `uv.lock` (frozen dependency resolution)
## Frameworks
- FastAPI 0.135.3 - REST API server with async/await support
- Uvicorn 0.38+ - ASGI server with standard extras (HTTP/2, WebSocket support)
- Typer - CLI framework for command-line tools (`job-rag` command)
- LangGraph 1.1.6 - ReAct agent orchestration and state management
- LangGraph Prebuilt 1.0.9 - Pre-built agent templates (create_react_agent)
- LangChain Core 1.2.28 - LLM abstraction and prompt templates
- LangChain OpenAI 1.1.12 - OpenAI integration for LangChain
- OpenAI 2.30.0 - Direct OpenAI API client
- Instructor - Structured data extraction from LLMs via Pydantic
- sentence-transformers - Cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2`) for semantic reranking
- SQLAlchemy 2.0+ with asyncio - Async ORM for PostgreSQL
- asyncpg 0.31.0 - Async PostgreSQL driver (used in ASYNC_DATABASE_URL)
- psycopg2-binary - Sync PostgreSQL driver (used in DATABASE_URL for CLI)
- pgvector - PostgreSQL vector extension for semantic search via cosine distance
- sse-starlette - Server-sent events for streaming agent responses
- aiohttp - Async HTTP client (indirect dependency)
- pytest 9.0.3+ - Test framework
- pytest-asyncio - Async test support
- httpx - Async HTTP client for testing
- ragas 0.2.0+ - RAG evaluation metrics (optional, marked as eval)
- Langfuse 4.1.0 - LLM observability and tracing (optional, no-op when keys are unconfigured)
- structlog - Structured logging with JSON output
- Pydantic 2.0+ - Data validation and serialization
- Pydantic Settings - Environment variable management
- python-dotenv - .env file loading
- python-multipart - Multipart form data parsing for file uploads
- tenacity - Retry logic with exponential backoff
- mcp - Model Context Protocol server implementation
- ruff - Linter and formatter (target-version py312, line-length 100)
- pyright - Type checker (pythonVersion 3.12, basic mode)
- pip-audit - Dependency vulnerability scanning
## Key Dependencies
- openai 2.30.0 - Core LLM API for extraction, embedding, and RAG generation
- langgraph 1.1.6 - Agent orchestration; provides ReAct loop and tool calling
- SQLAlchemy 2.0+ - Database abstraction; enables async operations via asyncpg
- pgvector - PostgreSQL vector type; enables semantic search with cosine distance
- fastapi 0.135.3 - REST API with automatic OpenAPI docs and dependency injection
- uvicorn - ASGI server; runs the FastAPI app
- asyncpg 0.31.0 - High-performance async PostgreSQL driver
- sse-starlette - Streaming responses for agent output
- sentence-transformers - Loads cross-encoder model at runtime for reranking
- instructor - Enables structured LLM outputs via Pydantic integration
## Configuration
- `.env` file (not committed) — required for API keys and database URLs
- `pyproject.toml` - Core project metadata and dependencies
- `pyproject.toml` [tool.ruff] - Code formatting (100 char line length, py312 target)
- `pyproject.toml` [tool.pyright] - Type checking config
- Docker compose env variables are passed via `docker-compose.yml` or `.env`
- `DATABASE_URL` - Sync PostgreSQL connection string (used by CLI)
- `ASYNC_DATABASE_URL` - Async PostgreSQL with asyncpg (used by FastAPI)
- Both point to the same database on postgres:5432 as configured in `docker-compose.yml`
- `OPENAI_API_KEY` - OpenAI API key for LLM calls
- `JOB_RAG_API_KEY` - Bearer token for API authentication (optional, auth disabled when empty)
- `LANGFUSE_PUBLIC_KEY` - Langfuse observability (optional)
- `LANGFUSE_SECRET_KEY` - Langfuse observability (optional)
- `LANGFUSE_HOST` - Langfuse endpoint (defaults to https://cloud.langfuse.com)
- Location: `src/job_rag/config.py`
- All config loaded via Pydantic Settings from environment + .env file
- Models used:
## Platform Requirements
- Python 3.12+
- uv package manager
- PostgreSQL 17 (or pgvector/pgvector:pg17 Docker image)
- Docker with Docker Compose
- PostgreSQL 17 with pgvector extension enabled (via `CREATE EXTENSION IF NOT EXISTS vector`)
- OPENAI_API_KEY required (secrets managed outside container)
- FastAPI runs on `0.0.0.0:8000` (Uvicorn in docker-entrypoint)
- Database runs on port 5432 (PostgreSQL in Docker, not exposed to host)
- Initialization: Database tables created automatically on startup via `job-rag init-db`
## Build & Deployment
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

## Naming Patterns
- Modules use lowercase with underscores: `extractor.py`, `retrieval.py`, `matching.py`
- Database model files: `models.py` (SQLAlchemy tables) vs `models.py` (Pydantic schemas in different modules)
- Entry points: `cli.py`, `app.py` (FastAPI), `server.py` (MCP)
- Test files: `test_<module>.py` pattern (e.g., `test_extraction.py`)
- Config/setup: `config.py`, `logging.py`, `observability.py`
- Camel case for public functions: `extract_posting()`, `search_postings()`, `match_posting()`
- Snake case consistently throughout: `get_logger()`, `get_openai_client()`, `get_reranker()`
- Async functions prefixed with async keyword, otherwise no naming distinction: `async def run_agent()`, `async def search_postings()`
- Private functions prefixed with single underscore: `_embed_query()`, `_normalize_skill()`, `_sanitize_delimiters()`, `_skill_matches()`
- Factory/builder functions: `build_agent()`, `get_session()`, `get_logger()`
- Camel case for module-level constants used as config: `PROMPT_VERSION`, `AGENT_SYSTEM_PROMPT`, `RAG_SYSTEM_PROMPT`
- Snake case for all local variables: `user_skills`, `must_have`, `nice_to_have`, `posting_id`
- Global module state prefixed with underscore: `_reranker`, `_ALIAS_GROUPS`, `_ALIAS_INDEX`
- Type hints on function parameters and returns always present
- Pydantic models for data structures: `JobPosting`, `JobRequirement`, `UserSkillProfile`, `UserSkill`
- Enums for fixed sets: `SkillCategory`, `RemotePolicy`, `Seniority`, `SalaryPeriod` (use `StrEnum` for string enums)
- Return type annotations required: `dict[str, Any]`, `list[dict[str, Any]]`, `tuple[JobPosting, dict]`
- Union types use `|` operator (Python 3.10+ syntax): `str | None`, `list[str] | None`
## Code Style
- Line length: 100 characters (enforced by ruff, see `pyproject.toml`)
- Indentation: 4 spaces (Python standard)
- No trailing commas except in multiline collections
- Imports organized by ruff's import rules (see Import Organization below)
- Tool: ruff (see `.github/workflows/ci.yml` and `pyproject.toml`)
- Selected rules: `E` (pycodestyle errors), `F` (Pyflakes), `I` (isort/import sorting), `UP` (pyupgrade)
- Target version: Python 3.12
- Run via CI: `uv run ruff check src/ tests/`
- Fix mode available: `uv run ruff check --fix`
- Tool: pyright
- Mode: "basic" (see `pyproject.toml` `[tool.pyright]`)
- Python version: 3.12
- Run via CI: `uv run pyright src/`
- Type hints are expected on public functions; private functions benefit from hints but stricter enforcement is at "basic" level
## Import Organization
- No path aliases configured; all imports use absolute paths from package root
- Example: `from job_rag.services.retrieval import search_postings` (not relative imports like `from ..services`)
- Used in observability module to defer expensive imports when not enabled: see `src/job_rag/observability.py` lines 47, 62
- Pattern: conditional import inside a function to delay import cost until actually needed
## Error Handling
- Tenacity for automatic retries with exponential backoff: `@retry(wait=wait_exponential(min=1, max=10), stop=stop_after_attempt(3))` in `src/job_rag/extraction/extractor.py` line 36
- Try-except with logging for best-effort operations: `src/job_rag/observability.py` lines 78-83 (Langfuse flush)
- HTTPException for API responses: `raise HTTPException(status_code=404, detail="Posting not found")` in `src/job_rag/api/routes.py` line 93
- Validation errors via Pydantic: `ValidationError` raised automatically for schema violations
- Fail-open observability: when Langfuse is disabled, functions return empty lists or None-safe defaults (no errors)
- Error dictionaries returned from tools (MCP server): `{"error": "posting_not_found", "posting_id": posting_id}` in `src/job_rag/mcp_server/tools.py` line 98
- Extraction and LLM calls fail gracefully with retries; if all retries exhausted, exception propagates to API/CLI caller
- Search and retrieval operations return empty results rather than raising (fail-open for UX)
- Security validations (file path, content size) return error objects to MCP tools
- API endpoints use FastAPI's HTTPException for clean error responses
## Logging
- Configured with: contextvars merge, log level processor, ISO timestamp, ConsoleRenderer for dev-friendly output
- Factory: `PrintLoggerFactory` (logs to stdout)
- Context type: dict
- Get logger: `log = get_logger(__name__)` at module top level
- Structured logging with keyword arguments: `log.info("extraction_complete", company=posting.company, title=posting.title, requirements_count=len(posting.requirements), **usage_info)`
- Event name as first positional arg: `log.info("event_name", key1=value1, key2=value2)`
- Examples from codebase:
- Significant operations: LLM calls, database queries, agent tool invocations
- Configuration changes: observability initialization, model selection
- Errors and warnings: via `log.warning()` for recoverable issues (e.g., Langfuse flush failure)
- Do not log: individual loop iterations, internal helper function calls, sensitive user data
## Comments
- Explain the "why" when logic is not obvious: see `src/job_rag/services/matching.py` line 25 (alias groups explanation)
- Document formula/scoring logic: see `src/job_rag/services/matching.py` line 63 (match score formula as docstring)
- Security-sensitive code: see `src/job_rag/extraction/extractor.py` line 32 (prompt injection prevention explanation)
- Workarounds and known limitations: see `.github/workflows/ci.yml` line 36 (CVE note)
- Not used; Python uses docstrings instead
- Docstrings: triple-quoted strings on function/class definitions
- Style: One-liner summary followed by blank line, then description and return type info
- Examples:
## Function Design
- Aim for single responsibility; most functions 10-50 lines
- Extraction function (`extract_posting`) is ~50 lines including docstring and logging
- Retrieval pipeline (`rag_query`) is ~80 lines for full orchestration
- Utility functions (`_skill_matches`, `_normalize_skill`) are 5-10 lines
- Required parameters first, then keyword-only arguments after `*` if appropriate
- Examples: `search_postings(session, query, *, top_k=20, seniority=None, remote=None, min_salary=None)`
- Type hints on all parameters
- Use Annotated for dependency injection in FastAPI: `Session = Annotated[AsyncSession, Depends(get_session)]`
- Explicit return type annotation required
- Dictionary returns favor `dict[str, Any]` for flexibility, with clear documentation of keys
- Tuple returns used for multi-value returns: `tuple[JobPosting, dict]` for extraction results
- Async functions return same types as sync equivalents, wrapped in coroutine
- Empty result safety: functions return empty list/dict rather than None (except when None is semantically meaningful like `salary_min: int | None`)
## Module Design
- Explicit `__all__` only in package-level `__init__.py` files: see `src/job_rag/agent/__init__.py`
- Otherwise, all public functions/classes importable by convention (no leading underscore)
- Minimal use; agent module has one: `src/job_rag/agent/__init__.py` re-exports `build_agent` and `run_agent`
- Most modules imported directly: `from job_rag.services.retrieval import search_postings`
- Services layer has async functions for database operations: `search_postings(session, ...)`, `rag_query(session, ...)`
- Extraction is sync but wrapped with `@retry` decorator for robustness
- API routes all async: `async def search(...)`
- Utility/helper functions (matching logic, normalization) are sync; they don't call I/O
- CLI commands call async code via `asyncio.run()` or similar event loop management
## Code Examples
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

## Pattern Overview
- Ingestion → Retrieval → Intelligence separation of concerns
- Dual SQLAlchemy engines (sync for CLI, async for concurrent services)
- Single tool implementation reused by three entry points (CLI agent, FastAPI, MCP server)
- pgvector vector search with cross-encoder reranking and semantic chunking
- Structured extraction via Instructor + GPT-4o-mini before storage
## Layers
- Purpose: Parse markdown postings, extract structured data, deduplicate, store to database
- Location: `src/job_rag/extraction/`, `src/job_rag/services/ingestion.py`
- Contains: Instructor-based extraction with Pydantic validation, prompt management, content hashing
- Depends on: SQLAlchemy ORM, OpenAI API
- Used by: CLI `ingest` command, FastAPI `/ingest` endpoint
- Purpose: Vector search, reranking, profile scoring, skill gap analysis
- Location: `src/job_rag/services/retrieval.py`, `src/job_rag/services/matching.py`, `src/job_rag/services/embedding.py`
- Contains: pgvector cosine distance search, cross-encoder reranking, fuzzy skill matching, aggregate gap analysis
- Depends on: SQLAlchemy async queries, OpenAI embeddings, local CrossEncoder model
- Used by: MCP tools, agent tools, FastAPI routes
- Purpose: Expose retrieval/matching logic as reusable tools for multiple interfaces
- Location: `src/job_rag/mcp_server/tools.py`, `src/job_rag/agent/tools.py`, `src/job_rag/api/routes.py`
- Contains: Async tool implementations, LangGraph ReAct agent, FastAPI endpoints, MCP server decorators
- Depends on: Retrieval + Matching layer, LangChain, FastMCP
- Used by: End users via CLI, API, agent, or MCP client
- Purpose: Invoke intelligence layer through different interfaces
- Locations: `src/job_rag/cli.py` (CLI), `src/job_rag/api/app.py` (FastAPI), `src/job_rag/mcp_server/server.py` (MCP)
- CLI uses sync engine for simplicity; FastAPI and MCP use async engine for concurrency
- Authentication and rate limiting at API layer (`src/job_rag/api/auth.py`)
## Data Flow
## Key Abstractions
- Purpose: Single implementation used by MCP, Agent, and FastAPI
- Examples: `src/job_rag/mcp_server/tools.py` implements `search_postings()`, `match_skills()`, `skill_gaps()`
- Pattern: Each service function (retrieval, matching, embedding) is pure async; tools wrap these to serialize output for LLM consumption
- Purpose: Sync (`SessionLocal`) for CLI commands (simple, no event loop), Async (`AsyncSessionLocal`) for concurrent requests
- Examples: `src/job_rag/db/engine.py` provides both `engine` and `async_engine`
- Pattern: ORM models shared via `Base` declarative class; session dependency injection in FastAPI
- Purpose: Strict schema for extracted postings and user profile
- Examples: `src/job_rag/models.py` defines `JobPosting`, `JobRequirement`, `UserSkillProfile`
- Pattern: Used for validation on extraction output, API request/response serialization, and type safety
- Purpose: Track extraction prompt evolution; enable full re-extraction on version bump
- Examples: `src/job_rag/extraction/prompt.py` defines `PROMPT_VERSION` (e.g., "1.1"); each `JobPostingDB` stores its prompt version
- Pattern: CLI `reset` command deletes all postings on prompt version change, forcing re-extraction with new prompt
## Entry Points
- Location: `job-rag init-db`, `job-rag ingest`, `job-rag embed`, `job-rag serve`, `job-rag agent`, `job-rag mcp`
- Triggers: User runs command in terminal
- Responsibilities: Database setup, file ingestion loop, batch embedding, FastAPI startup, agent execution
- Location: `src/job_rag/api/app.py` (app factory), `src/job_rag/api/routes.py` (8 endpoints)
- Triggers: HTTP requests to `/health`, `/search`, `/match/{posting_id}`, `/gaps`, `/ingest`, `/agent`, `/agent/stream`
- Responsibilities: Request validation, auth/rate limiting, session dependency injection, SSE streaming for agent events
- Location: `src/job_rag/agent/graph.py` (`build_agent()`, `run_agent()`), `src/job_rag/agent/stream.py` (streaming wrapper)
- Triggers: FastAPI `/agent` and `/agent/stream` endpoints; CLI `agent` command
- Responsibilities: Tool orchestration, LLM reasoning loop, prompt synthesis, result formatting
- Location: `src/job_rag/mcp_server/server.py` (FastMCP app factory), `src/job_rag/mcp_server/tools.py` (4 async tools)
- Triggers: Claude Code or other MCP client connects via stdio
- Responsibilities: Tool exposure, JSON serialization, error handling, session management
## Error Handling
- Extraction: Retry on transient errors (tenacity `retry_exponential`); log and skip on validation failure
- Retrieval: Return empty results if vector search fails; degrade to BM25 if available (not yet)
- Observability: Langfuse integration is fail-open (no `LANGFUSE_*` env vars = silent no-op via `get_langchain_callbacks()`)
- Database: AsyncSession handles connection pooling; CLI explicitly closes sync sessions
## Cross-Cutting Concerns
- Framework: `structlog` with context propagation
- Implementation: `src/job_rag/logging.py` provides `get_logger()`
- Pattern: JSON-structured logs with module name as context; example: `log.info("extraction_complete", company=posting.company, cost_usd=cost)`
- At ingestion: Pydantic validates Instructor output against `JobPosting` schema
- At API layer: FastAPI auto-validates query params and request bodies
- At matching: Skill normalization + alias-based fuzzy matching
- Strategy: Optional Bearer token (env var `JOB_RAG_API_KEY`)
- Implementation: `src/job_rag/api/auth.py` middleware checks `Authorization: Bearer {key}`
- When disabled (empty env var): All endpoints open (local development mode)
- Per-endpoint limits defined in `src/job_rag/api/auth.py`
- Examples: `/search` 30/min, `/ingest` 5/min, `/agent` 10/min
- Storage: In-memory dict per endpoint; per-IP tracking via FastAPI request context
- Provider: Langfuse (optional, requires `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY`)
- Integrated points: Every `ChatOpenAI` LLM call, LangChain callback handlers, Instructor extraction
- Traces include: Token counts, latencies, full prompts, tool inputs/outputs
- Graceful degradation: If keys missing, integration disabled; no performance penalty
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->



<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
