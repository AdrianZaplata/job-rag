# Job Posting RAG System - Project Plan

**Purpose:** RAG-powered tool that ingests AI Engineer job postings, extracts structured skill data, matches against my profile, and surfaces insights for job applications.

**Status:** Phase 4 Complete

**Created:** 2026-04-06
**Last updated:** 2026-04-10

---

## Why This Project

- Solves a real problem during my AI Engineer career pivot
- Closes skill gaps 1-4, 6 from my requirements doc in a single project
- Portfolio piece that stands out (real use case, not "chat with PDFs")
- Uses pgvector (leverages existing PostgreSQL experience from RelationshipApp)

---

## Skills Closed Per Phase

| Skill | Gap # | Phase |
|---|---|---|
| Pydantic + Structured Outputs (Instructor) | 2 | 1 ✅ |
| Production Python (type hints, structlog, CLI) | - | 1 ✅ |
| pgvector setup + schema design | 1 | 1 ✅ |
| RAG + Vector DBs + Embeddings | 1 | 2 ✅ |
| LangChain | 3 | 2 ✅ |
| FastAPI | 4 | 2 ✅ |
| Evaluation frameworks (RAGAS) | 6 | 3 ✅ |
| Docker deployment (FastAPI + DB) | - | 3 ✅ |
| CI/CD (GitHub Actions) | 13 | 3 ✅ |
| LangGraph (agent orchestration) | 3 | 4 ✅ |
| MCP server development | 5 | 4 ✅ |
| LLM observability (Langfuse) | 7 | 4 ✅ |
| Streaming responses (SSE) | 9 | 4 ✅ |
| Tool use / function calling | 10 | 4 ✅ |

---

## Tech Stack

| Tool | Purpose | Phase |
|---|---|---|
| Python 3.12+ | Core language | All |
| Pydantic + Instructor | Structured extraction from LLMs | 1 ✅ |
| PostgreSQL + pgvector | Storage + vector search | All |
| SQLAlchemy 2.0 | ORM (sync P1, async P2+) | All |
| OpenAI gpt-4o-mini | Extraction (cheap, fast) | 1 ✅ |
| OpenAI text-embedding-3-small | Semantic embeddings (1536 dims) | 2 ✅ |
| LangChain | RAG retrieval pipeline | 2 ✅ |
| FastAPI | REST API | 2 ✅ |
| Cross-encoder reranker | Retrieval precision | 2 ✅ |
| RAGAS | RAG evaluation metrics | 3 ✅ |
| Docker Compose | Containerized deployment | 3 ✅ |
| GitHub Actions | CI/CD (lint, test, type check) | 3 ✅ |
| LangGraph | Agent orchestration | 4 ✅ |
| Custom MCP Server | Expose system to Claude Code | 4 ✅ |
| Langfuse | LLM observability/tracing | 4 ✅ |
| sse-starlette | Streaming responses | 4 ✅ |
| Typer | CLI framework | 1 ✅ |
| structlog | Structured logging | 1 ✅ |
| pytest | Testing | All |

---

## Architecture

```mermaid
graph TD
    subgraph "Phase 1: Extraction ✅"
        MD[Markdown Files] --> EXT[Instructor + GPT-4o-mini]
        EXT --> PYD[Pydantic Validation]
        PYD --> DB[(PostgreSQL + pgvector)]
        EXT -.->|structlog| LOG[Cost & Token Logging]
    end

    subgraph "Phase 2: RAG + API ✅"
        Q[User Query] --> EMB[text-embedding-3-small]
        EMB --> VS[pgvector Similarity]
        VS --> RR[Cross-Encoder Rerank]
        RR --> LC[LangChain Generation]
        LC --> API[FastAPI Response]
        PROF[User Profile JSON] --> MATCH[Match Scoring]
        DB --> VS
        DB --> MATCH
    end

    subgraph "Phase 3: Quality"
        GOLD[Golden Dataset] --> RAGAS[RAGAS Evaluation]
        API --> DOCKER[Docker Compose]
        RAGAS --> CI[GitHub Actions CI/CD]
    end

    subgraph "Phase 4: Intelligence ✅"
        AGENT[LangGraph ReAct Agent] --> |search_jobs| TOOLS[Async Tool Layer]
        AGENT --> |match_profile| TOOLS
        AGENT --> |analyze_gaps| TOOLS
        MCP[FastMCP Server stdio] --> TOOLS
        TOOLS --> DB
        AGENT -.->|traces| LF[Langfuse]
        EXT -.->|traces| LF
        LC -.->|traces| LF
        AGENT --> SSE[SSE Streaming /agent/stream]
    end
```

---

## Phase 1 - Structured Extraction & Storage ✅

**Goal:** Run `job-rag ingest` and have all postings extracted into structured data in PostgreSQL.

**Skills closed:** Production Python, Pydantic + structured outputs, pgvector, structured logging.

### What Was Built

| File | Purpose |
|---|---|
| `src/job_rag/models.py` | Pydantic models: JobPosting, JobRequirement, UserSkillProfile, enums (SkillCategory, RemotePolicy, Seniority, SalaryPeriod) |
| `src/job_rag/config.py` | pydantic-settings BaseSettings loading from .env |
| `src/job_rag/logging.py` | structlog configuration with ISO timestamps |
| `src/job_rag/db/engine.py` | Sync SQLAlchemy engine, SessionLocal, Base, init_db() |
| `src/job_rag/db/models.py` | ORM models: JobPostingDB (UUID PK, linkedin_job_id unique, content_hash, embedding Vector(1536) nullable, prompt_version) + JobRequirementDB (skill, category, required, FK cascade) |
| `src/job_rag/extraction/prompt.py` | System prompt v1.0 with mapping rules for remote policy, seniority, salary, skill categorization |
| `src/job_rag/extraction/extractor.py` | Instructor extraction with tenacity retry (3 attempts, exponential backoff), cost tracking per call |
| `src/job_rag/services/ingestion.py` | Batch ingestion: read markdown → check dedup (linkedin_job_id + content_hash) → extract → store |
| `src/job_rag/cli.py` | Typer CLI: init-db, ingest (--show-cost), list (--company filter), stats |
| `tests/test_models.py` | 13 tests - Pydantic validation, enum values, helper functions |
| `tests/test_extraction.py` | 7 tests - mocked Instructor extraction, post-processing |

### Key Design Decisions

- **Deduplication:** linkedin_job_id from URL (primary) + SHA-256 content_hash (secondary)
- **Salary normalization:** LLM classifies period (hour/month/year), Python converts to EUR/year. Raw string preserved in `salary_raw`
- **Separate requirements table:** Not JSONB - enables SQL queries like "which jobs need LangChain?"
- **Embedding column added now (nullable):** Populated in Phase 2, zero cost when NULL
- **Prompt versioning:** `prompt_version` stored per extraction for future A/B comparison
- **Cost tracking:** Each extraction logs tokens + USD cost; `--show-cost` flag on CLI

### Results

- **23/23 postings ingested** - $0.025 total cost
- **359 requirements extracted** across 8 categories
- **Dedup verified** - re-run: 0 ingested, 23 skipped
- **20/20 tests passing**, ruff clean, pyright clean
- **Top skills found:** Python (19x), LangChain (6x), ML (5x), PyTorch (5x), RAG (4x), Docker (3x), FastAPI (3x)

---

## Phase 2 - RAG Core + FastAPI ✅

**Goal:** Semantic search over job postings via API. Skill matching against user profile.

**Skills closed:** RAG architecture, embeddings, LangChain, FastAPI.

### What Was Built

| File | Purpose |
|---|---|
| `src/job_rag/db/engine.py` | Added async engine (asyncpg) + AsyncSessionLocal alongside existing sync engine |
| `src/job_rag/db/models.py` | Added JobChunkDB (section-based chunks with Vector(1536) embeddings) |
| `src/job_rag/services/embedding.py` | OpenAI batch embedding, section-based chunking, format_posting_for_embedding() |
| `src/job_rag/services/retrieval.py` | pgvector cosine search, cross-encoder reranking, LangChain RAG generation chain |
| `src/job_rag/services/matching.py` | Profile loading, fuzzy skill matching with aliases, scoring formula, gap aggregation |
| `src/job_rag/api/app.py` | FastAPI app with async lifespan |
| `src/job_rag/api/deps.py` | Async session dependency injection |
| `src/job_rag/api/routes.py` | 5 endpoints: /health, /search, /match/{id}, /gaps, /ingest |
| `src/job_rag/cli.py` | Added `embed` (populate embeddings) and `serve` (start uvicorn) commands |
| `data/profile.json` | User skill profile (30 skills from requirements doc) |
| `tests/test_matching.py` | 15 tests - skill normalization, matching, scoring formula, gap aggregation |
| `tests/test_retrieval.py` | 4 tests - reranking with mocked cross-encoder |
| `tests/test_api.py` | 5 tests - all endpoints with mocked dependencies |

### Key Design Decisions

- **Dual engine:** Sync SQLAlchemy for CLI, async for FastAPI - no breaking changes to Phase 1
- **SQLAlchemy + pgvector for retrieval, LangChain only for generation:** Avoids duplicate vector store, uses existing schema
- **Section-based chunking:** Splits postings into responsibilities, must_have, nice_to_have, benefits sections
- **Cross-encoder reranker:** `cross-encoder/ms-marco-MiniLM-L-6-v2` runs locally (~80MB, no API cost)
- **Fuzzy skill matching:** Alias dictionary maps variations (e.g., "PostgreSQL" → "sql", "React.js" → "react")
- **Match formula:** `score = (matched_must / total_must) * 0.7 + (matched_nice / total_nice) * 0.3`

### Results

- **23/23 postings embedded** - 74 chunks total, $0.000168 embedding cost
- **Full RAG pipeline verified** - search → rerank → LangChain generation working end-to-end
- **48/48 tests passing**, ruff clean, pyright clean
- **Top skill gaps identified:** ML (17.4%), LangChain (13%), RAG (13%), FastAPI (13%)
- **API live at** `localhost:8000` with Swagger docs at `/docs`

---

## Phase 3 - Evaluation + Docker Deployment ✅

**Goal:** Prove it works with metrics. Make it portable. CI/CD.

**Skills closed:** Evaluation frameworks (RAGAS), containerized deployment (Docker multi-stage), CI/CD (GitHub Actions).

### What Was Built

| File | Purpose |
|---|---|
| `data/eval/golden_queries.json` | 18 golden queries with ground truth answers across 5 categories (skill, filter, salary, comparative, profile-relevant) |
| `data/eval/extraction_ground_truth.json` | Manually verified expected extraction for 5 diverse postings |
| `data/eval/extraction_results.json` | Pre-stored extraction outputs compared against ground truth |
| `data/eval/results.json` | RAGAS evaluation scores (per-query + aggregate) |
| `scripts/evaluate.py` | Standalone RAGAS script: runs full RAG pipeline for each query, scores with 4 metrics, saves results |
| `tests/test_extraction_accuracy.py` | 50 parametrized tests (10 categories × 5 postings), marked `@pytest.mark.eval` |
| `Dockerfile` | Multi-stage build: uv + CPU-only PyTorch + pre-downloaded cross-encoder → slim runtime |
| `scripts/docker-entrypoint.sh` | Container startup: init-db → ingest → embed → uvicorn |
| `docker-compose.yml` | Added `app` service with healthcheck-gated `depends_on` and env overrides |
| `.env.example` | Template with DATABASE_URL, ASYNC_DATABASE_URL, OPENAI_API_KEY |
| `.github/workflows/ci.yml` | GitHub Actions: ruff → pyright → pytest with uv caching |
| `README.md` | Portfolio showcase: Mermaid architecture, API docs, skills table, design decisions, RAGAS results |
| `docs/how-it-works.md` | Extended walkthrough covering evaluation, Docker, and CI/CD |
| `pyproject.toml` | Added `ragas` dev dependency and `eval` pytest marker |

### Key Design Decisions

- **Standalone eval script, not CLI command:** `scripts/evaluate.py` is imported-on-demand to avoid pulling RAGAS into every CLI invocation; it requires a running DB and real API calls which belong outside the test suite
- **Async OpenAI client for RAGAS:** `llm_factory` with `AsyncOpenAI` so `ascore()` can run inside the existing async pipeline
- **CPU-only PyTorch in Docker:** `UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu` saves ~1.5GB; cross-encoder runs fine on CPU
- **Multi-stage Dockerfile:** Builder stage installs + pre-downloads models, runtime stage copies only `.venv` and `~/.cache/huggingface` - discards build tools
- **Healthcheck-gated app service:** `depends_on: db: condition: service_healthy` prevents the app from crashing on an unready database
- **Env var override for Docker networking:** `DATABASE_URL` in compose uses `db` hostname instead of `localhost`; pydantic-settings picks it up automatically
- **`eval` pytest marker:** Keeps extraction accuracy tests separate from CI unit tests (`pytest -m "not eval"`) - CI stays fast and hermetic, eval tests run on-demand
- **Extraction tests compare stored outputs:** No OpenAI calls during tests - fast, deterministic, free; the verified extraction results are committed alongside ground truth
- **Single CI job, not parallel:** Project is small enough that spinning up three runners for lint/typecheck/test would add more overhead than it saves

### Results

- **18 golden queries evaluated** across 5 categories with manually verified ground truth
- **RAGAS scores:** Faithfulness **0.82** · Answer Relevancy **0.74** · Context Precision **0.60** · Context Recall **0.47**
- **System excels at skill queries:** PyTorch query scored 1.00 across all metrics; comparative queries (Trimble vs GitLab) scored 1.00 on faithfulness and recall
- **Known limitation surfaced:** metadata queries (salary, vacation days) score 0.00 on context precision - embeddings are skill-focused, not benefit-focused
- **98/98 tests passing** - 48 unit tests (mocked) + 50 extraction accuracy tests (eval-marked), ruff clean, pyright clean
- **Docker image builds successfully** - `docker compose up` starts db + app, runs init → ingest → embed → serve end-to-end
- **CI green on master** - lint + typecheck + tests complete in ~57 seconds with uv cache enabled
- **Total evaluation cost:** ~$0.13 for 72 RAGAS scoring calls + 18 RAG pipeline runs

---

## Phase 4 - Agent Layer + MCP + Observability ✅

**Goal:** Make it smart, autonomous, and observable.

**Skills closed:** LangGraph, MCP development, Langfuse observability, SSE streaming, tool use.

### What Was Built

| File | Purpose |
|---|---|
| `src/job_rag/mcp_server/tools.py` | Async tool implementations reused by MCP and the agent |
| `src/job_rag/mcp_server/server.py` | FastMCP stdio server registering 4 tools |
| `src/job_rag/agent/tools.py` | LangChain `@tool` wrappers around the same async services |
| `src/job_rag/agent/graph.py` | `create_react_agent` assembly with system prompt + cached build |
| `src/job_rag/agent/stream.py` | `astream_events` adapter yielding token/tool_start/tool_end/final dicts |
| `src/job_rag/observability.py` | Langfuse integration: cached OpenAI wrapper + LangChain callback handler |
| `src/job_rag/api/routes.py` | New `POST /agent` and `GET /agent/stream` endpoints |
| `src/job_rag/cli.py` | New `job-rag mcp` and `job-rag agent [--stream]` commands |
| `tests/test_mcp_server.py` | 11 tests covering all 4 MCP tools with mocked DB |
| `tests/test_agent.py` | 6 tests for tool wrappers, run_agent, and stream_agent |
| `tests/test_observability.py` | 6 tests verifying enabled/disabled paths and no-op fallbacks |

### LangGraph Agent (3 tools)

- [x] `search_jobs(query, remote_only?, seniority?, limit?)` → semantic search + rerank
- [x] `match_profile(posting_id)` → skill match against user profile
- [x] `analyze_gaps(seniority?, remote?)` → aggregate gap analysis

Built with `langgraph.prebuilt.create_react_agent`. Sync entry point (`run_agent`) returns the final answer plus a list of tool calls; streaming entry point (`stream_agent`) yields structured events consumed by both the CLI (`--stream` flag) and the SSE endpoint.

Stretch goals (deferred): auto-process folder, CV bullet point generation, high-match alerts.

### MCP Server

- [x] `search_postings(query, remote_only, seniority, limit)` → reranked posting list
- [x] `match_skills(posting_id)` → match report
- [x] `skill_gaps(seniority, remote)` → aggregated gaps
- [x] `ingest_posting(file_path | content)` → ingest + auto-embed

Implemented as a FastMCP stdio server reusing the existing retrieval, matching, and ingestion services. The same async tool implementations are also wrapped as LangChain tools for the LangGraph agent - single source of truth for tool behavior. Launch with `job-rag mcp`. Wired into Claude Code via `mcpServers` config - see README.

### Observability

- [x] Langfuse integration via drop-in `langfuse.openai.OpenAI` wrapper (extraction, embedding, retrieval query embedding)
- [x] LangChain `CallbackHandler` attached to RAG generation and agent runs
- [x] Optional via env vars (`LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST`); no-op when unset
- [x] `flush()` helper called from CLI exit paths

### Streaming

- [x] `GET /agent/stream?q=...` SSE endpoint via `sse-starlette` `EventSourceResponse`
- [x] Forwards LangGraph `astream_events` as `tool_start`, `tool_end`, `token`, `final` SSE events
- [x] CLI `job-rag agent --stream` consumes the same async generator for terminal use

### Dependencies Added

`mcp`, `langgraph`, `langfuse`, `sse-starlette` (the latter pulled in transitively by `mcp` already, declared explicitly).

### Key Design Decisions

- **One tool implementation, three entry points:** `mcp_server/tools.py` holds the async functions; the FastMCP server registers them directly, the LangGraph agent wraps them in `@tool` decorators, the FastAPI routes call them via the agent. No duplicated SQL or matching logic.
- **`build_agent()` is `lru_cache`'d:** the compiled graph and the `ChatOpenAI` instance are reused across requests - avoids re-instantiating the model on every call.
- **Langfuse helpers fail open, not closed:** if keys aren't configured, `get_openai_client()` returns plain `openai.OpenAI` and `get_langchain_callbacks()` returns `[]`. The codebase doesn't have to know whether observability is on.
- **Streaming events are structured dicts, not raw LangGraph events:** the `stream.py` adapter normalizes `astream_events` output to a stable schema (`token`/`tool_start`/`tool_end`/`final`) so the CLI and SSE endpoint share the same consumer code. Insulates callers from LangGraph internal changes.
- **Agent returns tool_calls list:** `run_agent` extracts tool call metadata from intermediate messages so callers can audit which tools fired without parsing the full message history.

### Results

- **123 tests collected** - 73 unit tests pass (was 48), +25 covering MCP, agent, observability, SSE; 50 eval tests still gated behind `-m eval`
- **ruff clean, pyright clean** - 0 errors, 0 warnings across `src/`
- **MCP server smoke-tested** - `mcp.list_tools()` returns all 4 tools with descriptions
- **SSE endpoint smoke-tested** - `/agent/stream` emits well-formed `event: <type>\ndata: <json>` frames
- **Skills closed:** LangGraph orchestration, MCP server development, Langfuse observability, SSE streaming, tool use / function calling - all five Phase 4 skill targets met

**Done when (achieved):** Can drop a new posting file, have it auto-processed, query it from Claude Code via MCP, see full traces in Langfuse (when configured), and get streaming responses via `/agent/stream`.

---

## Queries the System Should Handle

- "Which postings value MCP experience?"
- "Find roles where my automotive HMI background is a differentiator"
- "What are the top 5 skills I'm missing across all senior AI Engineer postings?"
- "Generate tailored bullet points for this Anthropic posting"
- "Show me remote-friendly roles with >80% skill match"
- "What salary range do postings matching my profile offer?"

---

## Success Metrics

- Retrieval precision: relevant postings returned for skill-based queries
- Extraction accuracy: structured data correctly parsed from raw postings
- Match score correlation: system scores align with manual assessment
- Time saved: faster than manually reading and comparing postings
- Portfolio signal: deployed, documented, measurable
- RAGAS scores: faithfulness > 0.8, answer relevancy > 0.8
