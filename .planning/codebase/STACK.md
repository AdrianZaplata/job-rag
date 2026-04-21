# Technology Stack

**Analysis Date:** 2026-04-21

## Languages

**Primary:**
- Python 3.12 - All application code, CLI, API, agent, and data processing
- Markdown - Job posting corpus format (stored as markdown files in `data/postings/`)

## Runtime

**Environment:**
- Python 3.12 (specified in `pyproject.toml` with `requires-python = ">=3.12"`)
- Docker: Python 3.12-slim-bookworm (multi-stage build for optimized image size)

**Package Manager:**
- uv (ultra-fast Python package manager)
- Lockfile: `uv.lock` (frozen dependency resolution)

## Frameworks

**Core:**
- FastAPI 0.135.3 - REST API server with async/await support
- Uvicorn 0.38+ - ASGI server with standard extras (HTTP/2, WebSocket support)
- Typer - CLI framework for command-line tools (`job-rag` command)

**Agent & Graph:**
- LangGraph 1.1.6 - ReAct agent orchestration and state management
- LangGraph Prebuilt 1.0.9 - Pre-built agent templates (create_react_agent)

**LLM & Embeddings:**
- LangChain Core 1.2.28 - LLM abstraction and prompt templates
- LangChain OpenAI 1.1.12 - OpenAI integration for LangChain
- OpenAI 2.30.0 - Direct OpenAI API client
- Instructor - Structured data extraction from LLMs via Pydantic

**Sentence Transformers:**
- sentence-transformers - Cross-encoder model (`cross-encoder/ms-marco-MiniLM-L-6-v2`) for semantic reranking

**Database:**
- SQLAlchemy 2.0+ with asyncio - Async ORM for PostgreSQL
- asyncpg 0.31.0 - Async PostgreSQL driver (used in ASYNC_DATABASE_URL)
- psycopg2-binary - Sync PostgreSQL driver (used in DATABASE_URL for CLI)
- pgvector - PostgreSQL vector extension for semantic search via cosine distance

**HTTP & Streaming:**
- sse-starlette - Server-sent events for streaming agent responses
- aiohttp - Async HTTP client (indirect dependency)

**Testing:**
- pytest 9.0.3+ - Test framework
- pytest-asyncio - Async test support
- httpx - Async HTTP client for testing
- ragas 0.2.0+ - RAG evaluation metrics (optional, marked as eval)

**Observability:**
- Langfuse 4.1.0 - LLM observability and tracing (optional, no-op when keys are unconfigured)
- structlog - Structured logging with JSON output

**Data & Configuration:**
- Pydantic 2.0+ - Data validation and serialization
- Pydantic Settings - Environment variable management
- python-dotenv - .env file loading
- python-multipart - Multipart form data parsing for file uploads

**Utilities:**
- tenacity - Retry logic with exponential backoff
- mcp - Model Context Protocol server implementation

**Development:**
- ruff - Linter and formatter (target-version py312, line-length 100)
- pyright - Type checker (pythonVersion 3.12, basic mode)
- pip-audit - Dependency vulnerability scanning

## Key Dependencies

**Critical:**
- openai 2.30.0 - Core LLM API for extraction, embedding, and RAG generation
- langgraph 1.1.6 - Agent orchestration; provides ReAct loop and tool calling
- SQLAlchemy 2.0+ - Database abstraction; enables async operations via asyncpg
- pgvector - PostgreSQL vector type; enables semantic search with cosine distance

**Infrastructure:**
- fastapi 0.135.3 - REST API with automatic OpenAPI docs and dependency injection
- uvicorn - ASGI server; runs the FastAPI app
- asyncpg 0.31.0 - High-performance async PostgreSQL driver
- sse-starlette - Streaming responses for agent output

**ML/Indexing:**
- sentence-transformers - Loads cross-encoder model at runtime for reranking
- instructor - Enables structured LLM outputs via Pydantic integration

## Configuration

**Environment:**
- `.env` file (not committed) — required for API keys and database URLs
- `pyproject.toml` - Core project metadata and dependencies
- `pyproject.toml` [tool.ruff] - Code formatting (100 char line length, py312 target)
- `pyproject.toml` [tool.pyright] - Type checking config
- Docker compose env variables are passed via `docker-compose.yml` or `.env`

**Database Configuration:**
- `DATABASE_URL` - Sync PostgreSQL connection string (used by CLI)
- `ASYNC_DATABASE_URL` - Async PostgreSQL with asyncpg (used by FastAPI)
- Both point to the same database on postgres:5432 as configured in `docker-compose.yml`

**Key Configs:**
- `OPENAI_API_KEY` - OpenAI API key for LLM calls
- `JOB_RAG_API_KEY` - Bearer token for API authentication (optional, auth disabled when empty)
- `LANGFUSE_PUBLIC_KEY` - Langfuse observability (optional)
- `LANGFUSE_SECRET_KEY` - Langfuse observability (optional)
- `LANGFUSE_HOST` - Langfuse endpoint (defaults to https://cloud.langfuse.com)

**Settings Class:**
- Location: `src/job_rag/config.py`
- All config loaded via Pydantic Settings from environment + .env file
- Models used:
  - `openai_model` - Default: "gpt-4o-mini" (extraction and RAG)
  - `agent_model` - Default: "gpt-4o-mini" (agent reasoning)
  - `embedding_model` - Default: "text-embedding-3-small"
  - `reranker_model` - Default: "cross-encoder/ms-marco-MiniLM-L-6-v2"
  - `data_dir` - Default: "data/postings"
  - `profile_path` - Default: "data/profile.json"

## Platform Requirements

**Development:**
- Python 3.12+
- uv package manager
- PostgreSQL 17 (or pgvector/pgvector:pg17 Docker image)

**Production:**
- Docker with Docker Compose
- PostgreSQL 17 with pgvector extension enabled (via `CREATE EXTENSION IF NOT EXISTS vector`)
- OPENAI_API_KEY required (secrets managed outside container)

**Deployment:**
- FastAPI runs on `0.0.0.0:8000` (Uvicorn in docker-entrypoint)
- Database runs on port 5432 (PostgreSQL in Docker, not exposed to host)
- Initialization: Database tables created automatically on startup via `job-rag init-db`

## Build & Deployment

**Multi-stage Docker Build:**
1. **Builder stage**: ghcr.io/astral-sh/uv:0.6-python3.12-bookworm-slim
   - Downloads CPU-only PyTorch (`UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu`)
   - Pre-caches cross-encoder model via `CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')`
   - Creates frozen virtual environment
2. **Runtime stage**: python:3.12-slim-bookworm
   - Copies .venv and cached models from builder
   - Runs as non-root user (appuser, UID 1000)
   - Exposes port 8000

**Startup Sequence (docker-entrypoint.sh):**
1. `job-rag init-db` - Create tables and pgvector extension
2. `job-rag ingest --show-cost` - Load job postings from data/postings/*.md
3. `job-rag embed --show-cost` - Generate embeddings for all postings
4. `uvicorn job_rag.api.app:app --host 0.0.0.0 --port 8000` - Start API

---

*Stack analysis: 2026-04-21*
