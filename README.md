# Job RAG

> A RAG system I built during a pivot into AI engineering - to read 23 AI Engineer job postings for me and tell me which ones I should actually be reading.

It ingests raw LinkedIn markdown into structured skill data, scores each posting against my profile, and exposes the whole corpus as a LangGraph agent, a FastAPI service, and an MCP server for Claude Code. Everything is instrumented with Langfuse and evaluated with RAGAS.

---

## What it actually found

The first time I ran the agent against a real corpus with my profile loaded, it ranked this posting as my top match at **0.588**:

**(Senior) AI Engineer at IU Group** - remote, Germany. Matched on `Python`, `FastAPI`, `tool use`, `embeddings`, `vector search`, `monitoring`, `testing`.

Here are the five responsibilities from their posting, side-by-side with what I'd just finished building:

| IU Group | Job RAG |
|---|---|
| Build agentic AI systems for multi-step user journeys | LangGraph ReAct agent orchestrating 3 tools over multi-step queries |
| Develop retrieval and context-engineering pipelines | pgvector search → cross-encoder rerank → LangChain generation |
| Shape AI behavior through prompt engineering | Extraction prompt v1.0 → v1.1 with atomic-skill decomposition rules |
| Optimize production systems for latency, observability, reliability | Langfuse tracing, structured logging, healthcheck-gated Docker |
| Drive improvement through evaluation, testing, monitoring | RAGAS golden dataset, 79 unit tests, GitHub Actions CI |

I had never read this posting before running the tool. The system surfaced it not because it was the most obvious skill match (my first run of the same query, before fixing the profile and extraction pipeline, ranked it 0.183) but because the final version of the pipeline - with atomic-skill decomposition, alias-based fuzzy matching, and an agent sorting results by real match score - could see the fit that the earlier versions could not.

That story is the whole reason this project exists, and also its best validation: **the system works well enough to find its own use case.**

![Agent streaming tool calls and a ranked answer against the live corpus](docs/images/agent-demo.gif)

*The LangGraph agent streaming tool calls (`search_jobs`, `match_profile`) and the ranked answer in real time. Reproduce locally with `job-rag agent --stream "Which 3 remote senior AI Engineer roles fit my profile best, and why?"`.*

---

## Architecture

```mermaid
graph TD
    subgraph "Ingestion"
        MD[23 Markdown postings] --> EXT[Instructor + GPT-4o-mini]
        EXT --> PYD[Pydantic validation]
        PYD --> DB[(PostgreSQL + pgvector)]
    end

    subgraph "Retrieval + Matching"
        Q[User query] --> EMB[text-embedding-3-small]
        EMB --> VS[pgvector cosine]
        VS --> RR[cross-encoder rerank]
        PROF[profile.json] --> MATCH[fuzzy alias matching]
        DB --> VS
        DB --> MATCH
    end

    subgraph "Intelligence layer"
        TOOLS[async tool layer]
        RR --> TOOLS
        MATCH --> TOOLS
        TOOLS --> AGENT[LangGraph ReAct agent]
        TOOLS --> MCP[FastMCP stdio server]
        AGENT --> API[FastAPI + SSE]
        AGENT -.->|traces| LF[Langfuse]
        EXT -.->|traces| LF
    end
```

One tool implementation (`mcp_server/tools.py`) is reused by all three entry points - the FastMCP server, the LangGraph agent, and the FastAPI routes. No duplicated retrieval or matching logic.

---

## Stack and skills demonstrated

| Area | What's here |
|---|---|
| **RAG + vector search** | pgvector cosine distance, section-based chunking, cross-encoder reranking, dense retrieval over 23 postings / 74 chunks |
| **Structured extraction** | Instructor + GPT-4o-mini + Pydantic models; atomic-skill decomposition prompt (v1.1) with few-shot examples |
| **LangChain** | `ChatPromptTemplate`, `ChatOpenAI`, `StrOutputParser`, callback handlers for tracing |
| **LangGraph agents** | `create_react_agent` with 3 tools, `astream_events` for streaming, `lru_cache`'d compiled graph |
| **MCP server development** | FastMCP stdio server exposing 4 tools to Claude Code, reusing the same async service layer |
| **FastAPI** | Async API, dependency-injected sessions, lifespan management, 8 endpoints including SSE |
| **SSE streaming** | `sse-starlette` EventSourceResponse forwarding `astream_events` as `token` / `tool_start` / `tool_end` / `final` frames |
| **LLM observability** | Langfuse drop-in OpenAI wrapper + LangChain `CallbackHandler`, fail-open when keys missing |
| **Evaluation** | RAGAS golden dataset of 18 queries with manually-verified ground truth, 4 metrics, standalone script |
| **PostgreSQL + pgvector** | UUID primary keys, separate normalized `job_requirements` table, `Vector(1536)` columns, indexed on company/seniority/remote |
| **Production Python** | Sync + async SQLAlchemy engines, type hints clean under pyright, structlog, tenacity retry, Typer CLI |
| **Docker + deployment** | Multi-stage Dockerfile with CPU-only PyTorch, Docker Compose with healthcheck-gated app start, `docker-entrypoint.sh` |
| **CI/CD** | GitHub Actions: ruff + pyright + pytest with `uv` caching |
| **Testing** | 79 unit tests + 50 extraction accuracy tests (eval-marked), all mocked, no database or API key required |

---

## Design decisions

**pgvector over a dedicated vector DB.** Leverages existing PostgreSQL skills, keeps the stack to one database, stores structured fields and vectors in the same rows. No vendor lock-in.

**Cross-encoder reranking.** Two-stage retrieval (fast vector search → precise cross-encoder rerank) gives meaningfully better precision than vector search alone. The reranker runs locally on CPU, ~80MB, no API cost per query.

**Section-based chunking over fixed-size.** Postings are split into semantic sections (responsibilities, must-have, nice-to-have, benefits) rather than arbitrary character windows. Preserves structural context in a known schema. This is a deliberate choice over semantic chunking - worth the small loss in flexibility for the gain in interpretability.

**Atomic-skill extraction (v1.1).** The first extraction prompt produced compound requirements like `"Proven production AI solutions in automotive"` as single atomic skills, which the matching engine could never match. Rewriting the prompt with decomposition rules and few-shot examples turned that into `automotive`, `production deployment`, `AI solutions` - three skills the matcher can actually reason about. The top match for the same query went from 0.183 to 0.588.

**Sync + async dual SQLAlchemy engines.** CLI commands use sync (simple, no event loop). FastAPI + MCP + agent use async (concurrent request handling). Both share the same ORM models.

**One tool implementation, three entry points.** The async functions in `mcp_server/tools.py` are wrapped twice: once as `@mcp.tool()` for FastMCP, once as `@tool` for LangChain. No duplicated SQL, matching, or ingestion logic across the MCP server, the LangGraph agent, and the FastAPI routes.

**LangChain only for generation; everything else is direct SQLAlchemy.** Retrieval uses `pgvector.cosine_distance` in raw SQLAlchemy queries rather than LangChain's vector store abstractions. Avoids a duplicate vector store and keeps the retrieval logic legible. LangChain earns its place in the generation chain, where prompt templates and model abstraction actually add value.

**CPU-only PyTorch in the Docker image.** `UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu` drops ~1.5GB from the image. The cross-encoder runs fine on CPU for the reranking workload.

**Observability fails open, not closed.** `get_openai_client()` and `get_langchain_callbacks()` return the Langfuse-wrapped or plain clients depending on env vars. No startup check, no runtime exception, no perf cost when disabled. The codebase doesn't know whether tracing is on.

---

## Evaluation

Quality is measured with [RAGAS](https://docs.ragas.io/) against a golden dataset of 18 queries with manually-verified ground truth answers, across 5 categories: skill-based, filter-based, salary/benefits, comparative, and profile-relevant.

| Metric | v1.1 | v1.0 | Δ |
|---|---|---|---|
| Faithfulness | **0.81** (n=17/18) | 0.82 | ≈ flat |
| Answer Relevancy | **0.68** | 0.74 | −0.06 |
| Context Precision | **0.67** | 0.60 | **+0.07** |
| Context Recall | **0.43** | 0.47 | −0.04 |

The v1.1 extraction prompt rewrite (atomic-skill decomposition) produced a clear improvement in **context precision** - the metric it was expected to affect - from 0.60 to 0.67. Skill queries (LangChain, PyTorch, Docker, agentic AI) score 0.93+ on faithfulness and 1.00 on context precision; domain queries (German, automotive/HMI) score 1.00 on precision and 0.67-0.86 on recall now that compound phrases are decomposed. Metadata queries like "which companies offer 30 vacation days?" still score 0.00 on precision because the embeddings encode *what a job is about*, not *what benefits it offers* - a real known limitation that hybrid retrieval (dense + BM25 keyword) would fix.

One query (Trimble vs GitLab comparative) hits GPT-4o-mini's `max_tokens` ceiling on the faithfulness scorer due to the length of the comparative answer; the script catches this and excludes the failed sample, giving faithfulness n=17/18.

```bash
uv run python scripts/evaluate.py   # ~$0.13, ~1 minute
```

---

## Run it

```bash
# One command, full system
cp .env.example .env   # add OPENAI_API_KEY
docker compose up      # starts PostgreSQL + the app (ingest + embed + serve)
open http://localhost:8000/docs
```

For local development:

```bash
uv sync
docker compose up db -d
job-rag init-db
job-rag ingest --show-cost        # ~$0.025
job-rag embed --show-cost         # ~$0.0002
job-rag serve --reload            # or:
job-rag agent "Which jobs fit my profile best?"       # one-shot agent
job-rag agent --stream "..."                          # with tool call traces
job-rag mcp                                           # stdio MCP server
```

Ingesting and embedding the 23-posting corpus end-to-end costs ~$0.03.

---

## Components

### API endpoints

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/health` | DB connectivity |
| `GET` | `/search?q=...` | Semantic search with RAG answer (`generate=false` for raw results) |
| `GET` | `/match/{posting_id}` | Score user profile against one posting |
| `GET` | `/gaps?seniority=...&remote=...` | Aggregate skill gaps across filtered postings |
| `POST` | `/ingest` | Upload and process a new markdown posting |
| `POST` | `/agent` | Run the LangGraph agent, return final answer + tool call trace |
| `GET` | `/agent/stream?q=...` | Stream agent events (tool calls, tokens) as SSE |

Full interactive docs at `http://localhost:8000/docs`.

### LangGraph agent

A ReAct agent (`src/job_rag/agent/`) that orchestrates three tools:

- `search_jobs(query, remote_only?, seniority?, limit?)` - semantic search
- `match_profile(posting_id)` - score one posting against the user profile
- `analyze_gaps(seniority?, remote?)` - aggregate top missing skills

The agent's system prompt enforces sort-by-score and honest empty-result handling. `build_agent()` is `lru_cache`'d so the compiled graph and `ChatOpenAI` instance are reused across requests.

### MCP server (Claude Code integration)

The same async tools are exposed to [Claude Code](https://docs.claude.com/en/docs/claude-code) as a FastMCP stdio server. Add this to your MCP config:

```json
{
  "mcpServers": {
    "job-rag": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/job-rag", "job-rag", "mcp"],
      "env": {
        "DATABASE_URL": "postgresql://postgres:postgres@localhost:5432/job_rag",
        "ASYNC_DATABASE_URL": "postgresql+asyncpg://postgres:postgres@localhost:5432/job_rag",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

Then ask Claude Code things like *"search job-rag for roles using LangGraph and tell me which ones I match best."*

### Observability

Set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env` (optional). Every OpenAI call, LangChain invocation, and agent run will show up in your Langfuse dashboard as a nested trace: agent root, tool spans, nested LLM calls, with token counts, latencies, full prompts, and tool inputs/outputs. Without credentials, the integration is a no-op.

![Langfuse trace of one agent run showing nested LLM calls, tool invocations, token counts, and the system prompt](docs/images/langfuse-trace.png)

*A single agent query traced end-to-end: the LLM's first reasoning step (536 tokens, $0.000095) chose `search_jobs` with `remote_only: true, seniority: "senior"`. The full tree shows error recovery, five `match_profile` calls, and the final synthesis (3480 tokens). Total cost: $0.001.*

---

## Project structure

```
src/job_rag/
├── cli.py                 Typer CLI (init-db, ingest, embed, serve, mcp, agent, reset)
├── config.py              pydantic-settings (OpenAI, Langfuse, DB, model choices)
├── models.py              Pydantic domain models + enums
├── observability.py       Langfuse integration (optional, fails open)
├── db/                    SQLAlchemy sync + async engines, ORM models
├── extraction/            Instructor + GPT-4o-mini extraction, prompt v1.1
├── services/
│   ├── ingestion.py       Read → dedupe → extract → store
│   ├── embedding.py       Batch embedding, chunking
│   ├── retrieval.py       pgvector search, rerank, LangChain RAG
│   └── matching.py        Profile scoring, alias-based fuzzy matching, gap analysis
├── api/                   FastAPI app, routes, async session dependency
├── mcp_server/            FastMCP stdio server + shared async tool layer
└── agent/                 LangGraph ReAct agent + streaming adapter
tests/                     79 unit tests + 50 extraction accuracy tests (eval-marked)
```

## Cost summary

| Operation | Cost |
|---|---|
| Extract 23 postings (GPT-4o-mini, v1.1 prompt) | $0.025 |
| Embed 23 postings + 74 chunks (text-embedding-3-small) | $0.0002 |
| RAGAS evaluation (72 scoring calls + 18 RAG runs) | ~$0.13 |
| One agent query (~5 tool calls + synthesis) | ~$0.001 |

Total cost to stand up the entire system and run it end-to-end: **~$0.03**.
