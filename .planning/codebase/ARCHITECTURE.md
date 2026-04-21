# Architecture

**Analysis Date:** 2026-04-21

## Pattern Overview

**Overall:** Three-tier layered system with shared async tool layer.

**Key Characteristics:**
- Ingestion → Retrieval → Intelligence separation of concerns
- Dual SQLAlchemy engines (sync for CLI, async for concurrent services)
- Single tool implementation reused by three entry points (CLI agent, FastAPI, MCP server)
- pgvector vector search with cross-encoder reranking and semantic chunking
- Structured extraction via Instructor + GPT-4o-mini before storage

## Layers

**Ingestion Layer:**
- Purpose: Parse markdown postings, extract structured data, deduplicate, store to database
- Location: `src/job_rag/extraction/`, `src/job_rag/services/ingestion.py`
- Contains: Instructor-based extraction with Pydantic validation, prompt management, content hashing
- Depends on: SQLAlchemy ORM, OpenAI API
- Used by: CLI `ingest` command, FastAPI `/ingest` endpoint

**Retrieval + Matching Layer:**
- Purpose: Vector search, reranking, profile scoring, skill gap analysis
- Location: `src/job_rag/services/retrieval.py`, `src/job_rag/services/matching.py`, `src/job_rag/services/embedding.py`
- Contains: pgvector cosine distance search, cross-encoder reranking, fuzzy skill matching, aggregate gap analysis
- Depends on: SQLAlchemy async queries, OpenAI embeddings, local CrossEncoder model
- Used by: MCP tools, agent tools, FastAPI routes

**Intelligence Layer (Tools + Agents):**
- Purpose: Expose retrieval/matching logic as reusable tools for multiple interfaces
- Location: `src/job_rag/mcp_server/tools.py`, `src/job_rag/agent/tools.py`, `src/job_rag/api/routes.py`
- Contains: Async tool implementations, LangGraph ReAct agent, FastAPI endpoints, MCP server decorators
- Depends on: Retrieval + Matching layer, LangChain, FastMCP
- Used by: End users via CLI, API, agent, or MCP client

**Entry Points Layer:**
- Purpose: Invoke intelligence layer through different interfaces
- Locations: `src/job_rag/cli.py` (CLI), `src/job_rag/api/app.py` (FastAPI), `src/job_rag/mcp_server/server.py` (MCP)
- CLI uses sync engine for simplicity; FastAPI and MCP use async engine for concurrency
- Authentication and rate limiting at API layer (`src/job_rag/api/auth.py`)

## Data Flow

**Ingestion Pipeline:**

1. User provides raw markdown job posting (file or upload)
2. Content hash computed for deduplication
3. Optional LinkedIn ID extracted from URL
4. `extract_posting()` calls Instructor wrapper around OpenAI API
5. Pydantic validates response as `JobPosting` model
6. `_store_posting()` writes `JobPostingDB` + `JobRequirementDB` rows (atomic)
7. Embedding scheduled for chunked sections later

**Retrieval Pipeline:**

1. User query enters as string to `search_postings(session, query, filters)`
2. Query embedded via `text-embedding-3-small` to 1536-dim vector
3. `JobPostingDB.embedding.cosine_distance(query_vec)` retrieves top-20 by pgvector
4. Optional filters applied (seniority, remote, salary)
5. `rerank()` runs CrossEncoder scoring on top-20 → returns top-5 results
6. Each result includes `posting` object + `similarity` score + `rerank_score`

**Matching Pipeline:**

1. User calls `match_profile(posting_id)` with specific posting
2. `load_profile()` reads `data/profile.json` as `UserSkillProfile` (skills only)
3. For each requirement in posting:
   - Check if user skill matches via `_skill_matches()` (case-insensitive, fuzzy via alias groups)
   - Track matched/missed must-have vs. nice-to-have separately
4. Score formula: `(matched_must / total_must) * 0.7 + (matched_nice / total_nice) * 0.3`
5. Bonus signals added (e.g., "salary within your range", "location preference met")
6. Return detailed match report with breakdown

**Gap Analysis Pipeline:**

1. User calls `analyze_gaps(seniority, remote)` with optional filters
2. Query postings matching filters
3. Flatten all requirements, group by skill
4. For each skill, count frequency and how many as must-have
5. Filter to skills not in user profile
6. Return top gaps ranked by frequency

**Agent Reasoning Pipeline:**

1. User provides natural-language query to agent
2. Agent system prompt instructs use of three tools: `search_jobs`, `match_profile`, `analyze_gaps`
3. LLM chooses which tool(s) to call and in what order
4. Tool results fed back to LLM as observations
5. LLM can call more tools or synthesize final answer
6. Final answer must cite specific company/role names and sort results by score

## Key Abstractions

**Tool Unification:**
- Purpose: Single implementation used by MCP, Agent, and FastAPI
- Examples: `src/job_rag/mcp_server/tools.py` implements `search_postings()`, `match_skills()`, `skill_gaps()`
- Pattern: Each service function (retrieval, matching, embedding) is pure async; tools wrap these to serialize output for LLM consumption

**Dual SQLAlchemy Engines:**
- Purpose: Sync (`SessionLocal`) for CLI commands (simple, no event loop), Async (`AsyncSessionLocal`) for concurrent requests
- Examples: `src/job_rag/db/engine.py` provides both `engine` and `async_engine`
- Pattern: ORM models shared via `Base` declarative class; session dependency injection in FastAPI

**Pydantic Models:**
- Purpose: Strict schema for extracted postings and user profile
- Examples: `src/job_rag/models.py` defines `JobPosting`, `JobRequirement`, `UserSkillProfile`
- Pattern: Used for validation on extraction output, API request/response serialization, and type safety

**Prompt Versioning:**
- Purpose: Track extraction prompt evolution; enable full re-extraction on version bump
- Examples: `src/job_rag/extraction/prompt.py` defines `PROMPT_VERSION` (e.g., "1.1"); each `JobPostingDB` stores its prompt version
- Pattern: CLI `reset` command deletes all postings on prompt version change, forcing re-extraction with new prompt

## Entry Points

**CLI (`src/job_rag/cli.py`):**
- Location: `job-rag init-db`, `job-rag ingest`, `job-rag embed`, `job-rag serve`, `job-rag agent`, `job-rag mcp`
- Triggers: User runs command in terminal
- Responsibilities: Database setup, file ingestion loop, batch embedding, FastAPI startup, agent execution

**FastAPI Server (`src/job_rag/api/`):**
- Location: `src/job_rag/api/app.py` (app factory), `src/job_rag/api/routes.py` (8 endpoints)
- Triggers: HTTP requests to `/health`, `/search`, `/match/{posting_id}`, `/gaps`, `/ingest`, `/agent`, `/agent/stream`
- Responsibilities: Request validation, auth/rate limiting, session dependency injection, SSE streaming for agent events

**LangGraph Agent (`src/job_rag/agent/`):**
- Location: `src/job_rag/agent/graph.py` (`build_agent()`, `run_agent()`), `src/job_rag/agent/stream.py` (streaming wrapper)
- Triggers: FastAPI `/agent` and `/agent/stream` endpoints; CLI `agent` command
- Responsibilities: Tool orchestration, LLM reasoning loop, prompt synthesis, result formatting

**MCP Server (`src/job_rag/mcp_server/`):**
- Location: `src/job_rag/mcp_server/server.py` (FastMCP app factory), `src/job_rag/mcp_server/tools.py` (4 async tools)
- Triggers: Claude Code or other MCP client connects via stdio
- Responsibilities: Tool exposure, JSON serialization, error handling, session management

## Error Handling

**Strategy:** Fail gracefully with observability, no fatal crashes.

**Patterns:**
- Extraction: Retry on transient errors (tenacity `retry_exponential`); log and skip on validation failure
- Retrieval: Return empty results if vector search fails; degrade to BM25 if available (not yet)
- Observability: Langfuse integration is fail-open (no `LANGFUSE_*` env vars = silent no-op via `get_langchain_callbacks()`)
- Database: AsyncSession handles connection pooling; CLI explicitly closes sync sessions

## Cross-Cutting Concerns

**Logging:** 
- Framework: `structlog` with context propagation
- Implementation: `src/job_rag/logging.py` provides `get_logger()`
- Pattern: JSON-structured logs with module name as context; example: `log.info("extraction_complete", company=posting.company, cost_usd=cost)`

**Validation:**
- At ingestion: Pydantic validates Instructor output against `JobPosting` schema
- At API layer: FastAPI auto-validates query params and request bodies
- At matching: Skill normalization + alias-based fuzzy matching

**Authentication:**
- Strategy: Optional Bearer token (env var `JOB_RAG_API_KEY`)
- Implementation: `src/job_rag/api/auth.py` middleware checks `Authorization: Bearer {key}`
- When disabled (empty env var): All endpoints open (local development mode)

**Rate Limiting:**
- Per-endpoint limits defined in `src/job_rag/api/auth.py`
- Examples: `/search` 30/min, `/ingest` 5/min, `/agent` 10/min
- Storage: In-memory dict per endpoint; per-IP tracking via FastAPI request context

**Observability (Tracing):**
- Provider: Langfuse (optional, requires `LANGFUSE_PUBLIC_KEY` + `LANGFUSE_SECRET_KEY`)
- Integrated points: Every `ChatOpenAI` LLM call, LangChain callback handlers, Instructor extraction
- Traces include: Token counts, latencies, full prompts, tool inputs/outputs
- Graceful degradation: If keys missing, integration disabled; no performance penalty

---

*Architecture analysis: 2026-04-21*
