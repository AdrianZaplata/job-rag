# External Integrations

**Analysis Date:** 2026-04-21

## APIs & External Services

**OpenAI:**
- Purpose: LLM for job posting extraction, embeddings, RAG answer generation, and agent reasoning
- Services used:
  - `gpt-4o-mini` - Default model for extraction and RAG generation
  - `gpt-4o` - Alternative model (higher quality, higher cost)
  - `text-embedding-3-small` - Embeddings for semantic search
  - `text-embedding-3-large` - Alternative embeddings model
- SDK: openai 2.30.0 (Python client)
- Integration points:
  - `src/job_rag/observability.py` - `get_openai_client()` wraps client with Langfuse when enabled
  - `src/job_rag/extraction/extractor.py` - Uses Instructor for structured extraction
  - `src/job_rag/services/embedding.py` - Calls `client.embeddings.create()` for text vectors
  - `src/job_rag/services/retrieval.py` - Embedding for query and RAG generation
  - `src/job_rag/agent/graph.py` - ChatOpenAI model for agent reasoning
- Auth: `OPENAI_API_KEY` environment variable (required)
- Pricing tracked in:
  - `src/job_rag/extraction/extractor.py` - Per-request cost calculation for extraction
  - `src/job_rag/services/embedding.py` - Cost tracking for embeddings ($/M tokens)

## Data Storage

**PostgreSQL 17 with pgvector:**
- Purpose: Store job postings, requirements, and semantic embeddings
- Version: 17 (via pgvector/pgvector:pg17 Docker image)
- Connection:
  - Sync: `DATABASE_URL=postgresql://postgres:password@db:5432/job_rag`
  - Async: `ASYNC_DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/job_rag`
- Drivers:
  - Sync: psycopg2-binary (CLI commands)
  - Async: asyncpg 0.31.0 (FastAPI)
- ORM: SQLAlchemy 2.0+ with async support
- Extensions: pgvector (for cosine distance semantic search)
- Tables:
  - `job_posting_db` - Job postings with title, company, location, embedding vector
  - `job_requirement_db` - Skills (must-have and nice-to-have) linked to postings
  - `job_chunk_db` - Semantic chunks of postings (sections) with embeddings
- Models defined in: `src/job_rag/db/models.py`
- Database initialization: `src/job_rag/db/engine.py` (creates extension on first run)

**File Storage (Local):**
- Job postings: `data/postings/` - Markdown files (not committed, user-provided)
- User profile: `data/profile.json` - User skill profile for matching
- Both paths configurable via `data_dir` and `profile_path` in `src/job_rag/config.py`

**Caching:**
- Cross-encoder model: Cached during Docker build in `/home/appuser/.cache/huggingface`
- OpenAI client: Cached via `@lru_cache(maxsize=1)` in `src/job_rag/observability.py`
- LangGraph agents: Cached via `@lru_cache(maxsize=1)` in `src/job_rag/agent/graph.py`

## Authentication & Identity

**API Authentication:**
- Custom Bearer token (optional)
- Implementation: `src/job_rag/api/auth.py`
  - `require_api_key()` validates Bearer token against `JOB_RAG_API_KEY` env var
  - Auth is disabled when `JOB_RAG_API_KEY` is empty (local development)
- Validation: HMAC constant-time comparison to prevent timing attacks
- Applied to endpoints via FastAPI dependency injection (see `src/job_rag/api/routes.py`)
  - `/search` - Requires API key + standard rate limit
  - `/match/{posting_id}` - Requires API key + standard rate limit
  - `/gaps` - Requires API key + standard rate limit
  - `/agent` - Requires API key + agent rate limit
  - `/ingest` - Requires API key + ingest rate limit
  - `/health` - No auth (diagnostic)

**External Auth Providers:**
- None (no OAuth, SAML, or third-party identity providers)

## Monitoring & Observability

**Error Tracking & Tracing:**
- Langfuse 4.1.0 (optional, no-op when disabled)
- Purpose: LLM observability — trace token usage, costs, and agent tool calls
- Configuration:
  - `LANGFUSE_PUBLIC_KEY` - Optional public key
  - `LANGFUSE_SECRET_KEY` - Optional secret key
  - `LANGFUSE_HOST` - Optional endpoint (defaults to https://cloud.langfuse.com)
- When enabled:
  - OpenAI client is wrapped with Langfuse (`langfuse.openai.OpenAI`)
  - LangChain callbacks registered (`langfuse.langchain.CallbackHandler`)
  - All LLM calls and tool invocations are logged to Langfuse
- Implementation: `src/job_rag/observability.py`
  - `is_enabled()` - Checks if both keys are set
  - `get_openai_client()` - Returns wrapped client
  - `get_langchain_callbacks()` - Returns callback handlers for LangChain
  - `flush()` - Flushes pending events before process exit

**Logs:**
- structlog - Structured JSON logging to stdout
- All logs use `get_logger(__name__)` from `src/job_rag/logging.py`
- Log events include tags and key-value pairs for structured querying
- Examples:
  - `embedding_complete` - Logs token count and cost per posting
  - `extraction_complete` - Logs requirements extracted and cost
  - `agent_built` - Logs agent model and tool count
  - Rate limit events logged at 429 status
- Suitable for shipping to log aggregation platforms (stdout capture)

## CI/CD & Deployment

**Hosting:**
- Docker Compose (local/dev)
- Intended for cloud deployment (e.g., AWS ECS, GCP Cloud Run, Azure Container Apps)
- Dockerfile uses multi-stage build for ~1.5GB smaller image (CPU-only PyTorch)

**CI Pipeline:**
- None detected in codebase
- GitHub Actions workflows may exist in `.github/workflows/` (not examined)
- Pre-commit hooks referenced in code (`pip-audit` in dev dependencies)

**Build Artifacts:**
- Image size optimized by using Python 3.12-slim and CPU-only dependencies
- Cross-encoder model pre-cached in image layer (no download on startup)

## Environment Configuration

**Required env vars:**
- `OPENAI_API_KEY` - OpenAI API key (must be set for extraction, embedding, RAG)
- `POSTGRES_PASSWORD` - PostgreSQL password (must be set for docker-compose)
- `DATABASE_URL` - Sync PostgreSQL connection (defaults to localhost, override for production)
- `ASYNC_DATABASE_URL` - Async PostgreSQL connection (defaults to localhost, override for production)

**Optional env vars:**
- `JOB_RAG_API_KEY` - Bearer token for API authentication (auth disabled when empty)
- `LANGFUSE_PUBLIC_KEY` - Langfuse public key (observability disabled when empty)
- `LANGFUSE_SECRET_KEY` - Langfuse secret key (observability disabled when empty)
- `LANGFUSE_HOST` - Langfuse endpoint (defaults to https://cloud.langfuse.com)

**Secrets location:**
- `.env` file (local development, git-ignored)
- Docker Compose reads from `.env` or environment
- Environment variables passed at container runtime (standard practice)

## Webhooks & Callbacks

**Incoming:**
- None (no external webhooks expected)

**Outgoing:**
- None (no external webhook pushes)
- Langfuse receives background telemetry (non-blocking)

## Cross-Service Communication

**Internal APIs:**
- FastAPI to PostgreSQL - Direct SQLAlchemy connections (async via asyncpg)
- LangGraph agent uses tool functions defined in `src/job_rag/agent/tools.py`
  - Tools call service functions (`search_postings`, `match_posting`, `aggregate_gaps`)
  - Agent is stateless; invoked per-request

**Data Flow:**
1. User submits search query → FastAPI `/search` endpoint
2. Query embedded via OpenAI `text-embedding-3-small`
3. pgvector cosine distance search against posting embeddings (top-k=20)
4. Results reranked with cross-encoder (`ms-marco-MiniLM-L-6-v2`)
5. Retrieved chunks passed to OpenAI `gpt-4o-mini` for RAG generation
6. Response streamed via SSE (server-sent events) if streaming enabled
7. Langfuse observability logged (if enabled) in background

## Model Context Protocol (MCP)

**Purpose:** Expose job-rag tools to external clients (e.g., Claude Code)

**Server:** `src/job_rag/mcp_server/server.py`
- Implemented via FastMCP library from mcp package
- Exposed tools:
  - `search_postings(query, remote_only, seniority, limit)` - Semantic search
  - `match_skills(posting_id)` - Score profile match
  - `skill_gaps(seniority, remote)` - Aggregate missing skills
  - `ingest_posting(file_path, content)` - Ingest new posting
- Invocation: `job-rag mcp` CLI command starts stdio-based MCP server
- Integration: Add to Claude Code via `mcpServers` config in JSON with command like:
  ```json
  {
    "mcpServers": {
      "job-rag": {
        "command": "uv",
        "args": ["run", "--directory", "/abs/path/to/job-rag", "job-rag", "mcp"]
      }
    }
  }
  ```

---

*Integration audit: 2026-04-21*
