# How Job RAG Works - A Complete Walkthrough

This is a ground-up walkthrough of every piece of the Job RAG system. It assumes you know how to program but doesn't assume you know anything about RAG, vector databases, LangChain, LangGraph, MCP, or LLM observability. By the end you should understand every moving part and be able to explain why each one exists.

Read it top to bottom the first time. After that, use the table of contents to jump around.

**Contents**

1. [What the system does](#what-does-this-system-do)
2. [The building blocks](#the-building-blocks)
3. [The database tables](#the-database-tables)
4. [Pipeline 1 - Ingestion](#pipeline-1-ingestion--getting-data-in)
5. [Pipeline 2 - Embedding](#pipeline-2-embedding--making-search-possible)
6. [Pipeline 3 - Retrieval](#pipeline-3-retrieval--answering-questions)
7. [Pipeline 4 - Profile matching](#pipeline-4-profile-matching--how-well-do-you-fit)
8. [The intelligence layer (agent, MCP, streaming)](#the-intelligence-layer)
9. [Observability with Langfuse](#observability--tracing-every-llm-call-with-langfuse)
10. [Evaluation with RAGAS](#evaluation--proving-the-system-works)
11. [The API](#the-api--how-to-talk-to-the-system)
12. [The CLI](#the-cli--terminal-commands)
13. [Deployment in Docker](#deployment--running-in-docker)
14. [CI/CD](#cicd--automated-quality-checks)
15. [File structure](#file-structure)
16. [End-to-end example](#end-to-end-example)

---

## What Does This System Do?

You have 23 AI Engineer job postings saved as markdown files. This system:

1. **Reads** each file and uses an LLM to pull out structured information (company, skills, salary, responsibilities, benefits)
2. **Stores** everything in a PostgreSQL database
3. **Understands meaning** by converting each posting into a vector of numbers (an embedding)
4. **Answers questions** like *"which jobs want LangChain experience?"* by searching for meaning, not keywords
5. **Scores how well you match** each job against a profile you define, and tells you what skills you're missing
6. **Runs an agent** - a small LLM-driven program that decides which tools to call, in what order, to answer multi-step questions like *"which 3 remote senior roles fit my profile best, and why?"*
7. **Exposes the same tools to Claude Code** via an MCP server, so you can call them from any Claude Code conversation
8. **Streams results in real time** via Server-Sent Events so the UI feels responsive
9. **Traces every LLM call** with Langfuse so you can debug what the system is doing
10. **Proves it works** with RAGAS evaluation metrics against a golden dataset of queries
11. **Runs anywhere** via Docker - one command starts the entire stack

The project is divided into four conceptual phases, roughly matching how it was built:
- **Phase 1**: structured extraction + PostgreSQL storage
- **Phase 2**: the RAG core (embeddings, retrieval, FastAPI, matching)
- **Phase 3**: evaluation (RAGAS) + Docker deployment + CI/CD
- **Phase 4**: the intelligence layer (MCP server, LangGraph agent, Langfuse observability, SSE streaming)

---

## The Building Blocks

Before diving into the workflow, here's what each technology does and why it's needed. If you already know one of them, skip its section.

### PostgreSQL (the database)

A database is just an organized place to store data in tables - like spreadsheets with rows and columns. PostgreSQL is one of the most popular ones. We use it to store job postings, their individual skill requirements, their embeddings, and the section-level chunks used for retrieval.

### pgvector (the vector extension)

Normal databases store text and numbers. pgvector is an add-on that lets PostgreSQL also store and search **vectors** - lists of numbers that represent meaning (more on this in the embedding section). Without pgvector, we'd need a second database just for semantic search.

### Docker + Docker Compose

Instead of installing PostgreSQL on your computer (which involves version conflicts, configuration, and admin rights), Docker runs it in an isolated container - think "tiny virtual computer that only runs one thing." `docker-compose.yml` is a recipe file that says which containers to start and how they connect.

`docker compose up` starts the stack. `docker compose down` stops it. Your data survives both.

### Python (the programming language)

All the logic is written in Python 3.12. When you type `job-rag ingest` or `job-rag agent "..."`, you're running Python code.

### uv (the package manager)

uv is a fast replacement for pip/poetry. It reads `pyproject.toml` to figure out which packages to install, writes lock files so installs are reproducible, and runs ~10x faster than the alternatives. `uv sync` installs everything. `uv run <command>` runs something in the project's virtual environment.

### SQLAlchemy (the database toolkit)

Instead of writing raw SQL queries, SQLAlchemy lets you describe database tables as Python classes (`JobPostingDB` has `title`, `company`, `location` fields) and interact with them using Python. It also provides two interfaces: a **sync** one (for simple scripts and CLI commands) and an **async** one (for FastAPI, which needs to handle many concurrent requests without blocking). This project uses both - the CLI uses sync, the web API uses async, both share the same ORM models.

### Pydantic (data validation)

Pydantic makes sure data has the right shape. You define a class like `JobPosting` with fields `title: str`, `seniority: Seniority` (an enum), `salary_min: int | None`, and Pydantic will reject any input that doesn't fit. This is how we keep garbage data out of the database.

### OpenAI API (the LLM provider)

The system calls OpenAI's servers to use two models:
- **GPT-4o-mini** - reads job postings and extracts structured data, and later generates RAG answers and drives the agent
- **text-embedding-3-small** - converts text into 1536-number vectors

Both cost a small amount per call. Processing the full 23-posting corpus end-to-end costs about **$0.03**. One agent query costs about **$0.001**.

### Instructor (structured LLM output)

If you ask GPT-4o-mini a question normally, you get free-form text back. Instructor wraps the OpenAI client so that instead you get back a Pydantic object with exact fields. Under the hood it tells the model to use function-calling mode, parses the JSON response, and validates it against the Pydantic schema. If the model returns something invalid, Instructor automatically retries.

This is what makes Phase 1 reliable: we *know* every extraction will produce a valid `JobPosting` or fail loudly.

### Typer (the CLI framework)

Typer turns Python functions into terminal commands. You write `def ingest(directory: Path = ...)` and Typer automatically gives you `job-rag ingest --directory ...` with help text, argument parsing, and type coercion.

### FastAPI (the web server)

FastAPI turns Python functions into HTTP endpoints. You write `async def search(q: str): ...` and FastAPI gives you `GET /search?q=...` plus auto-generated Swagger docs at `/docs`. It's async-first, which matters when the handlers have to call OpenAI and wait for responses.

### LangChain (LLM orchestration)

LangChain is a library for composing LLM calls into chains. In this project we use it in two places:
1. **RAG generation** - a chain that takes `{context, question}`, formats them into a prompt, sends to GPT-4o-mini, parses the string output
2. **Agent tools** - `@tool` decorators that turn Python functions into things the LangGraph agent can call

LangChain is *not* used for retrieval. We do that with raw SQLAlchemy + pgvector queries because it's simpler and avoids a duplicate vector store.

### LangGraph (agent orchestration)

LangGraph is a library for building **agents** - programs where an LLM decides what to do next in a loop. The `create_react_agent` helper builds a "ReAct" agent (Reason + Act): the model reads the user's question, picks a tool, runs it, reads the result, and decides whether to call another tool or write the final answer.

Think of it as GPT-4o-mini being given a steering wheel and three pedals (the three tools), with a text prompt saying "here's the road, go find the best match."

### MCP and FastMCP (tool exposure to Claude Code)

MCP stands for **Model Context Protocol**. It's a standard (introduced by Anthropic) for exposing tools to LLM clients. Claude Code can speak MCP: if you tell it about an MCP server, it adds that server's tools to its available actions during conversations.

FastMCP is a Python library for building MCP servers quickly. You write `@mcp.tool()` on a Python function, FastMCP handles the JSON-RPC-over-stdio protocol, and Claude Code can call your function as if it were native.

### sse-starlette (Server-Sent Events)

Server-Sent Events (SSE) is a simple web protocol where the server keeps an HTTP connection open and pushes a stream of events to the client. It's one-way (server to client only), text-based, and natively supported by browsers via `EventSource`.

`sse-starlette` is a small library that wraps an async generator in an `EventSourceResponse` so FastAPI can stream events easily. We use it for the `/agent/stream` endpoint to send tool calls and token output in real time as the agent runs.

### Langfuse (LLM observability)

Langfuse is a dashboard platform for LLM traces. For every LLM call the system makes, Langfuse records the full input, full output, token counts, latency, cost, and parent-child span relationships. You see the result as a clickable tree: one agent run → child nodes for each tool call → child nodes for each LLM call inside.

It's optional. If you don't set `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` in `.env`, the integration becomes a no-op and the system runs exactly as before.

### Cross-encoder (reranking)

A small AI model (~80MB) that runs locally in the Python process - no API calls, no server, no cost per use. It reads pairs of texts (your query + a candidate posting) and scores how well they match. Slower than vector search but much more accurate. We use it as a second pass: vector search returns 20 candidates, the cross-encoder picks the best 5.

The specific model is `cross-encoder/ms-marco-MiniLM-L-6-v2`, downloaded automatically from Hugging Face the first time you run the code and cached at `~/.cache/huggingface/`. It's very different from large language models like GPT-4o - it has ~22 million parameters (vs ~200 billion for GPT-4o) and doesn't generate text, it only scores match quality. Small enough to run on any laptop CPU in milliseconds.

### structlog (logging)

Records what the system does as structured JSON events - how many files were processed, how many tokens used, which tool the agent called, how much it cost. Structured logs are easier to search and aggregate than plain text.

### RAGAS (evaluation)

A Python library that scores RAG system quality on a set of known questions. It uses an LLM (GPT-4o-mini) as a judge - reading the question, answer, retrieved context, and ground truth, then assigning scores from 0 to 1 on four metrics (faithfulness, relevancy, context precision, context recall).

### pytest

The Python test runner. We have **79 unit tests** (mocked, run in CI, no network required) plus **50 extraction accuracy tests** (marked `@pytest.mark.eval`, excluded from CI, compare stored extraction outputs to human-verified ground truth).

### GitHub Actions (CI/CD)

GitHub's built-in automation. Every push runs lint (ruff), type check (pyright), and tests (pytest) on a fresh Linux machine. A red ❌ on the commit means something broke.

---

## The Database Tables

The database has three tables. Think of each as a spreadsheet.

### `job_postings` - one row per job (23 rows)

| Column | Example | Purpose |
|---|---|---|
| id | `a1b2c3d4-...` | UUID primary key |
| linkedin_job_id | `4396945951` | Extracted from the LinkedIn URL, used for dedup |
| content_hash | `a8f3b2...` | SHA-256 of the raw text, also used for dedup |
| title | `(Senior) AI Engineer` | Job title |
| company | `IU Group` | Company name |
| location | `Germany (Berlin)` | Where the job is |
| remote_policy | `remote` | One of: remote, hybrid, onsite, unknown |
| seniority | `senior` | One of: junior, mid, senior, staff, lead, unknown |
| salary_min | `70000` | Minimum salary in EUR/year (normalized) |
| salary_max | `90000` | Maximum salary in EUR/year |
| salary_raw | `€70k-€90k/year` | Original text from posting |
| salary_period | `year` | One of: year, month, hour, unknown |
| responsibilities | `Build RAG pipelines...` | Newline-joined bullet points |
| benefits | `30 vacation days...` | Newline-joined perks |
| source_url | `https://linkedin.com/...` | Original URL |
| raw_text | *(full markdown)* | Complete original file content |
| prompt_version | `1.1` | Which extraction prompt produced this row |
| embedding | `[0.012, -0.034, ...]` | 1536 numbers, posting-level semantic summary |
| created_at | `2026-04-10 ...` | Timestamp |

### `job_requirements` - one row per skill per job (~509 rows)

| Column | Example | Purpose |
|---|---|---|
| id | `e5f6g7h8-...` | UUID primary key |
| posting_id | `a1b2c3d4-...` | Foreign key to `job_postings` (cascade delete) |
| skill | `Python` | Name of the skill |
| category | `language` | One of 8 enum values (language, framework, tool, etc.) |
| required | `true` | Must-have (true) or nice-to-have (false) |

Why a separate table instead of a JSON column? Because this schema lets you answer questions like *"which skill appears in the most postings?"* or *"which postings require Docker?"* with a single SQL query. It also lets you index on `skill` for fast lookups.

The row count depends on the extraction prompt version. With v1.0 (Phase 1) the corpus had 359 requirements. With v1.1 (Phase 4, atomic-skill decomposition), it has **509** - roughly 42% more skills per posting on average because compound phrases got decomposed into atomic ones. More on that in the Pipeline 1 section.

### `job_chunks` - sections of each posting (76 rows)

| Column | Example | Purpose |
|---|---|---|
| id | `i9j0k1l2-...` | UUID primary key |
| posting_id | `a1b2c3d4-...` | Foreign key to `job_postings` |
| section | `must_have` | One of: responsibilities, must_have, nice_to_have, benefits |
| content | `Senior AI Eng at GitLab\nMust-have: Python, LangChain...` | The text of that section |
| embedding | `[0.008, -0.021, ...]` | 1536 numbers for this section |

Each posting is split into sections so retrieval can find the *specific part* of a posting that's relevant, not just "this posting is somewhat related." Not every posting has all four sections - some don't list benefits, some have no nice-to-haves - which is why 23 postings produce 74 chunks, not 92.

---

## Pipeline 1: Ingestion - Getting Data In

**Command:** `job-rag ingest --dir data/postings`

This processes all 23 markdown files and stores them in the database. Here's what happens to each file.

### Step 1: Read the file

The system reads a markdown file like `iu-senior-ai-engineer.md`. It's just text - headings, bullet points, paragraphs. No parsing yet.

### Step 2: Check for duplicates

Before doing anything expensive (calling the LLM), the system checks if this posting is already in the database. It does this two ways:

- **Content hash** - takes the full text and generates a SHA-256 fingerprint. If the same bytes were already processed, skip it.
- **LinkedIn ID** - extracts the job ID from the URL (e.g., `/jobs/view/4396945951/` → `4396945951`). If a posting with the same LinkedIn ID exists, skip it.

This is why running `job-rag ingest` a second time is free and instant: every posting is flagged as a duplicate before the LLM is ever called.

### Step 3: Extract structured data with the LLM

The raw markdown is sent to GPT-4o-mini along with a detailed system prompt. Instructor forces the model to return data in the exact shape defined by the `JobPosting` Pydantic model. If it returns an invalid value (like `"seniority": "experienced"` - which isn't in the enum), Pydantic rejects it and Instructor asks the model to try again. Up to 3 retries with exponential backoff (handled by tenacity).

**Cost**: ~$0.001 per posting. Full corpus: ~$0.025.

#### The prompt version matters (v1.0 → v1.1)

The original extraction prompt (v1.0, used in Phase 1) told the model to extract all skills and categorize them, but said nothing about decomposition. The model would sometimes produce a single "skill" that was actually a sentence:

- `"Proven production AI solutions in automotive"` (one skill)
- `"Multiple years E/E architecture experience"` (one skill)
- `"bus systems (CAN, LIN, Ethernet)"` (one skill)
- `"Degree in EE, CS, mechatronics or equivalent with AI specialization"` (one skill)

Skills like those can never match a user profile, because profiles list atomic things (`"Python"`, `"Automotive"`). You can't write a profile entry that matches "Proven production AI solutions in automotive" as a literal string.

The v1.1 prompt (introduced in Phase 4) adds explicit decomposition rules and few-shot examples. Now the same posting produces:

- `automotive`, `production AI solutions` (from the first compound phrase)
- `E/E architecture` (the "multiple years" noise dropped)
- `bus systems`, `CAN`, `LIN`, `Ethernet` (split on parens)
- `Electrical Engineering`, `Computer Science`, `Mechatronics`, `AI specialization` (split on the degree list)

Concrete measurable impact: running the agent on the query *"Which 3 remote senior AI Engineer roles fit my profile best?"*, the top match moved from 0.183 (under v1.0) to 0.588 (under v1.1 + profile expansion + alias dictionary updates). That single change - rewriting the extraction prompt - accounts for roughly half of the total improvement.

The `prompt_version` column on `job_postings` stores which version produced that row. If you ever need to re-extract under a newer version, the `job-rag reset` command wipes all postings (cascade-deleting requirements and chunks) so you can re-ingest from scratch.

### Step 4: Store in the database

The validated `JobPosting` object is inserted as:
- 1 row in `job_postings` with all the structured fields
- N rows in `job_requirements`, one per decomposed skill

After all 23 files (under v1.1): 23 posting rows, 509 requirement rows, ~$0.025 total extraction cost.

---

## Pipeline 2: Embedding - Making Search Possible

**Command:** `job-rag embed`

This converts each posting's text into vectors (lists of numbers) so the system can search by meaning instead of keywords.

### What is an embedding?

An embedding is a fixed-length list of floating-point numbers that represents the *meaning* of a piece of text. The model (`text-embedding-3-small`) outputs 1536 numbers per input. It has learned from billions of texts that:

- `"Python developer"` and `"Python programmer"` → vectors very close together
- `"Python developer"` and `"Python snake handler"` → vectors far apart
- `"remote work"` and `"work from home"` → close together
- `"RAG experience"` and `"retrieval augmented generation"` → close together

"Close" here means small cosine distance - a mathematical measure of the angle between two vectors. Small angle = similar meaning.

This is what makes semantic search possible. You don't need the exact keyword - the system understands that *"which jobs want RAG experience?"* is related to *"retrieval-augmented generation"* even if the exact phrase doesn't appear.

### What gets embedded?

For each of the 23 postings, the system creates multiple embeddings:

**1. One posting-level embedding** - a formatted summary of the whole posting:

```
Title: (Senior) AI Engineer
Company: IU Group
Location: Germany (Berlin)
Remote: remote
Seniority: senior
Must-have skills: Python, FastAPI, vector search, embeddings, tool use, ...
Responsibilities: Build agentic AI systems for multi-step user journeys...
```

This becomes 1536 numbers stored in the `embedding` column of `job_postings`. Used for "find the most relevant posting" queries.

**2. Multiple chunk-level embeddings** - one per section of the posting:

- Responsibilities chunk → 1536 numbers
- Must-have chunk → 1536 numbers
- Nice-to-have chunk → 1536 numbers
- Benefits chunk → 1536 numbers

Each stored as a row in `job_chunks`. Not every posting has all four sections, which is why 23 postings produce 74 chunks (not 92). Used when you want to search *within* a posting for a specific topic.

**Cost:** ~$0.00016 total for all 23 postings. Essentially free.

---

## Pipeline 3: Retrieval - Answering Questions

**Endpoint:** `GET /search?q=which+jobs+want+LangChain`

When you ask a question, the system goes through four stages.

### Stage 1: Embed the query

Your question is converted into 1536 numbers using the same `text-embedding-3-small` model that embedded the postings. Now your question and all the postings live in the same "number space" and can be compared mathematically.

### Stage 2: Vector search with pgvector

PostgreSQL compares your query's vector against every posting's vector using **cosine distance**. It sorts by distance and returns the top 20. The whole thing is a single SQL query:

```sql
SELECT *, embedding <=> '[0.1, 0.2, ...]' AS distance
FROM job_postings
WHERE embedding IS NOT NULL
ORDER BY distance
LIMIT 20;
```

pgvector's `<=>` operator computes cosine distance directly in the database. Fast and simple.

Think of this as casting a wide net - get 20 reasonable candidates, knowing that some won't be perfect fits.

### Stage 3: Rerank with the cross-encoder

The cross-encoder model reads each of the 20 candidates alongside your query and assigns a more accurate relevance score. It picks the best 5.

Why two stages? Vector search compares compressed representations of whole documents - fast but approximate. The cross-encoder reads the full text of both the query and the candidate together - slower but much more accurate. The two-stage approach gets the best of both: fast narrowing, precise picking.

### Stage 4: Generate an answer with LangChain + GPT-4o-mini

The top 5 postings are formatted as a context block and sent to GPT-4o-mini along with your original question:

```
System: "You are a job search assistant..."
Human: "Context: [top 5 postings with details]
        Question: which jobs want LangChain experience?"
```

GPT-4o-mini reads the context and writes a natural language answer citing specific companies. LangChain's `ChatPromptTemplate`, `ChatOpenAI`, and `StrOutputParser` handle the prompt formatting, model call, and output parsing.

The response includes the answer text and the source postings (with similarity + rerank scores) so you can verify where the answer came from.

---

## Pipeline 4: Profile Matching - How Well Do You Fit?

**Endpoint:** `GET /match/{posting_id}`

### Your profile

`data/profile.json` contains your skills with proficiency levels:

```json
{
  "skills": [
    {"name": "Python", "proficiency": "advanced", "years": 3.5},
    {"name": "LangChain", "proficiency": "intermediate", "years": 0.5},
    {"name": "FastAPI", "proficiency": "intermediate", "years": 0.5},
    ...
  ],
  "target_roles": ["AI Engineer", "AI Application Engineer", "AI Software Engineer"],
  "preferred_locations": ["Berlin, Germany", "Germany", "Remote"],
  "min_salary": 65000,
  "remote_preference": "remote"
}
```

As of Phase 4, the profile has **61 skills** - expanded from an initial 30 to reflect everything the project itself demonstrates (LangChain, LangGraph, FastAPI, pgvector, MCP, observability, async Python, SQLAlchemy, etc.). If your profile undersells you, match scores will be artificially low.

### The matching process

For a given posting, the system:

1. Lists all must-have and nice-to-have skills from that posting's `job_requirements` rows
2. Checks each one against your profile using **fuzzy matching**
3. Calculates a score
4. Returns a report

Step 2 is the interesting one.

### Fuzzy matching with alias equivalence classes

A naive check would compare skill names literally: does your profile contain `"LangChain"`? But the same skill shows up under different names in different postings. You might have `"PostgreSQL"` in your profile; a posting might ask for `"postgres"` or `"Postgres SQL"` or `"SQL"`. These should all match.

The matching engine solves this with **equivalence classes**: lists of terms that should all match each other. The list lives in `src/job_rag/services/matching.py` as `_ALIAS_GROUPS`:

```python
_ALIAS_GROUPS: list[list[str]] = [
    ["python"],
    ["sql", "postgresql", "postgres", "mysql"],
    ["docker", "docker compose", "containerization", "containers"],
    ["llm", "large language model", "foundation model", ...],
    ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    ["automotive", "automotive ai", "automotive ai solutions", ...],
    ["hmi development", "hmi", "human machine interface", ...],
    ["vector databases", "pgvector", "qdrant", "pinecone", "weaviate", ...],
    ["async python", "asyncio", "async/await", ...],
    ["function calling", "tool use", "tool calling", "tools"],
    ["langgraph", "langchain graph", "agent graphs"],
    ...
]
```

At import time, these groups are flattened into a lookup index that maps each term to its frozenset of synonyms:

```python
"postgres" → frozenset({"sql", "postgresql", "postgres", "mysql"})
"containerization" → frozenset({"docker", "docker compose", "containerization", "containers"})
```

The match check is then: "does the intersection of the user skill's alias group and the job skill's alias group have any common members?" If yes, it's a match.

This structure makes it trivial to extend. Need to link "automotive AI solutions" (how a posting phrases it) to "Automotive" (how the profile lists it)? Add both to the same group. No algorithm changes needed.

### Calculating the score

```
score = (matched_must_haves / total_must_haves) * 0.7
      + (matched_nice_to_haves / total_nice_to_haves) * 0.3
```

Must-haves are weighted at 70% because they're dealbreakers. Nice-to-haves fill in the remaining 30%.

The result is a report that includes:
- The score (0.0 to 1.0)
- Which skills you match (split by must-have and nice-to-have)
- Which skills you're missing (the gap list)
- Bonus signals (remote match, salary meets your minimum)

### Gap analysis

**Endpoint:** `GET /gaps`

Runs the matching across all postings in the corpus and aggregates the misses: *"LangChain is missing in 13% of postings, ML in 17%, FastAPI in 13%."* This tells you which skills would have the biggest impact if you learned them - ranked by frequency across the whole corpus.

---

## The Intelligence Layer

Phases 1-3 give you a set of pipelines: text goes in, a query comes out with a ranked list of postings. It answers one question at a time.

Phase 4 adds a layer on top that lets you do multi-step things like *"find the top 3 remote senior roles, match each of them against my profile, rank by score, and tell me which one to apply to first."* That's three tool calls chained together, and deciding how to chain them requires an LLM that understands the task.

The intelligence layer has four parts:
1. A **shared async tool layer** - four functions that wrap the core services
2. A **LangGraph ReAct agent** that orchestrates those tools for multi-step questions
3. An **MCP server** that exposes the same tools to Claude Code
4. **Server-Sent Events streaming** for real-time tool call and token output

The key architectural principle: **one tool implementation, three entry points.** The same async functions are reused by the MCP server, the LangGraph agent, and (via the agent) the FastAPI routes. No duplicated search, matching, or ingestion logic.

### The shared tool layer

In `src/job_rag/mcp_server/tools.py` are four async functions:

- `search_postings(query, remote_only, seniority, limit)` - semantic search with rerank, returns structured posting summaries
- `match_skills(posting_id)` - fetch one posting, run matching, return a match report
- `skill_gaps(seniority, remote)` - aggregate gaps across filtered postings
- `ingest_posting(file_path, content)` - ingest + embed a new posting

These functions take simple arguments, return plain dicts (JSON-serializable), and manage their own database sessions. They're designed to be callable from anywhere - an MCP server, an agent, an HTTP handler, a test.

Why one implementation? Because if you had separate search logic in three places, they would slowly drift. A bug fix in one wouldn't propagate to the others. A new filter added to the agent wouldn't be visible to Claude Code. Concentrating the logic in one place is a force multiplier for every future change.

### LangGraph and the ReAct agent

**LangGraph** is a library for building agents as graphs of steps. An agent is a program where an LLM decides what to do next in a loop, rather than following a hardcoded sequence of steps.

The specific pattern we use is **ReAct** (Reason + Act):
1. The model reads the user's question
2. It *reasons* about what to do next
3. It *acts* by picking a tool and calling it with specific arguments
4. It reads the tool result
5. It goes back to step 2, until it decides to emit a final answer instead of another tool call

`langgraph.prebuilt.create_react_agent` builds this graph for you in one function call. You give it:
- A chat model (we use `ChatOpenAI(model="gpt-4o-mini", temperature=0.2)`)
- A list of tools (our LangChain-wrapped versions of the four async functions)
- A system prompt that sets the behavior

The system prompt we use is in `src/job_rag/agent/graph.py` and includes rules like:
- *"For 'find jobs that...' questions, call `search_jobs` first"*
- *"To rank results by fit, call `match_profile` on the most promising postings"*
- *"When presenting multiple postings, ALWAYS sort them by score from `match_profile` in descending order - never list them in the order you happened to call the tool"*
- *"Don't dump raw JSON back to the user - synthesize"*

### How one agent query actually runs

Here's a concrete trace. You run:

```bash
job-rag agent "Which 3 remote senior AI Engineer roles fit my profile best?"
```

The agent loop fires roughly like this:

1. **LLM call #1** - reads the question, outputs a tool call: `search_jobs(query="senior AI Engineer", remote_only=true, limit=5)`
2. **Tool execution** - runs the semantic search, gets 5 postings, returns a JSON list
3. **LLM call #2** - reads the search results, outputs a second tool call: `search_jobs(...)` (refining with different terms) OR jumps straight to match_profile. In practice it often does two searches to cover different phrasings.
4. **Tool execution** - second search, more results
5. **LLM call #3** - picks the most promising 3 postings, outputs `match_profile(posting_id="...")` for the first
6. **Tool execution** - matching runs, returns score + matched/missed skills
7. **LLM calls #4 and #5** - same for postings 2 and 3
8. **LLM call #6 (final)** - reads all three match reports, sorts by score descending (per the system prompt), writes a synthesized answer citing each company with the score and the top matched skills

Total: 5 tool calls, 6 LLM calls, ~5-10 seconds, ~$0.001. The important thing is that *we didn't write the pipeline* - the model decided on the order of operations each time.

### Why this matters more than a raw API call

If you only had the FastAPI `/search` endpoint, the user would have to:
1. Call `/search` to find postings
2. Parse the result
3. For each result, call `/match/{id}`
4. Compare scores themselves
5. Write the answer themselves

The agent does all of that automatically. It's the difference between giving someone a database and giving them an analyst who can query it.

### The MCP server

MCP stands for **Model Context Protocol** - a standard introduced by Anthropic for exposing tools to LLM clients. Claude Code speaks MCP. When you add an MCP server to Claude Code's configuration, Claude gets that server's tools available in every conversation.

The job-rag MCP server (`src/job_rag/mcp_server/server.py`) registers the four shared tool functions with FastMCP:

```python
from mcp.server.fastmcp import FastMCP
from job_rag.mcp_server import tools

mcp = FastMCP("job-rag")

@mcp.tool()
async def search_postings(query, remote_only=False, seniority=None, limit=5):
    """Semantic search over the AI Engineer job posting corpus."""
    return await tools.search_postings(query=query, ...)

# same pattern for match_skills, skill_gaps, ingest_posting

def run():
    mcp.run()  # starts the stdio server
```

To wire it into Claude Code, you add an entry to your MCP config:

```json
{
  "mcpServers": {
    "job-rag": {
      "command": "uv",
      "args": ["run", "--directory", "/abs/path/to/job-rag", "job-rag", "mcp"],
      "env": {
        "DATABASE_URL": "postgresql://...",
        "ASYNC_DATABASE_URL": "postgresql+asyncpg://...",
        "OPENAI_API_KEY": "sk-..."
      }
    }
  }
}
```

Now Claude Code can call `search_postings`, `match_skills`, etc. as native tools in any conversation. You can ask something like *"search job-rag for roles using LangGraph and tell me which one I match best"* and Claude orchestrates the tools itself.

How MCP works under the hood: when Claude Code starts, it spawns the `job-rag mcp` subprocess and communicates with it over standard input/output using JSON-RPC messages. FastMCP handles the protocol details - parsing requests, dispatching to the right `@mcp.tool()`-decorated function, serializing the response. You don't write any protocol code.

### Streaming with Server-Sent Events

The agent takes 5-10 seconds to finish. Without streaming, the user sees nothing until the final answer arrives. With streaming, they see tool calls flashing through and partial LLM output appearing in real time - which makes the system feel orders of magnitude more responsive.

The streaming stack has three layers:

**1. LangGraph's `astream_events`** - the LangGraph agent exposes an async iterator that yields low-level events for every step: `on_chat_model_stream` (one LLM token), `on_tool_start` (tool invoked), `on_tool_end` (tool finished), etc.

**2. `src/job_rag/agent/stream.py`** - an adapter that filters and reshapes those raw events into stable dictionaries:

```python
{"type": "token", "content": "Here are"}
{"type": "tool_start", "name": "search_jobs", "args": {"query": "..."}}
{"type": "tool_end", "name": "search_jobs", "output": "..."}
{"type": "final", "content": "Here are the top 3 matches..."}
```

The adapter is in its own file because it's shared: the CLI's `--stream` flag and the FastAPI `/agent/stream` endpoint both consume the same async generator. If LangGraph changes its event schema in a future version, this adapter is the only place we have to update.

**3. `sse-starlette`'s `EventSourceResponse`** - the FastAPI endpoint wraps the adapter's output in SSE frames and sends them over HTTP:

```python
@router.get("/agent/stream")
async def agent_stream(q: str):
    async def event_source():
        async for event in stream_agent(q):
            yield {"event": event["type"], "data": json.dumps(event)}
    return EventSourceResponse(event_source())
```

The wire format is simple text frames:

```
event: tool_start
data: {"type": "tool_start", "name": "search_jobs", "args": {...}}

event: token
data: {"type": "token", "content": "Here are"}

event: token
data: {"type": "token", "content": " the"}
```

Browsers consume this natively with `new EventSource("/agent/stream?q=...")`. From the terminal, `curl -N http://localhost:8000/agent/stream?q=...` works too. No WebSocket libraries required.

---

## Observability - Tracing Every LLM Call with Langfuse

When you build a system that makes many LLM calls in sequence, debugging becomes hard. Say the agent gives a weird answer. Was it:

- The query embedding finding the wrong postings?
- The cross-encoder reranker promoting something irrelevant?
- The `match_profile` tool returning incorrect scores?
- The final synthesis misreading the context?

Without traces, you're guessing. With traces, you click into a dashboard, see a tree of nested operations, and read exactly what went into each step and what came out. That's what Langfuse gives you.

### What Langfuse records

For each LLM call, Langfuse stores:
- The full input (system prompt + user message + prior tool results)
- The full output
- Token counts (input, output, cached)
- Latency
- Cost (computed from tokens × pricing)
- A parent span ID so calls nest correctly into hierarchies

One agent query produces one root span with child spans for every model call and tool invocation inside it.

### How the integration is wired

Two helper functions in `src/job_rag/observability.py`:

**`get_openai_client()`** returns an OpenAI-compatible client. If `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set in `.env`, it returns `langfuse.openai.OpenAI`, a drop-in wrapper that instruments every `.chat.completions.create()` and `.embeddings.create()` call. If not, it returns plain `openai.OpenAI`. The result is `lru_cache`'d so the wrapped client is reused.

**`get_langchain_callbacks()`** returns a list of LangChain callback handlers. If Langfuse is enabled, the list contains one `langfuse.langchain.CallbackHandler` that attaches to every chain invocation. If not, the list is empty.

Every direct OpenAI call in the codebase goes through `get_openai_client()`:
- `extraction/extractor.py` - the Instructor extraction
- `services/embedding.py` - batch posting embeddings
- `services/retrieval.py` - query embedding

Every LangChain call passes `get_langchain_callbacks()` as `config={"callbacks": callbacks}`:
- The RAG generation chain in `services/retrieval.py`
- The LangGraph agent in `agent/graph.py`
- The streaming agent in `agent/stream.py`

That's it. No conditional logic elsewhere in the codebase, no environment-dependent code paths.

### Fail-open design

If `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are missing, the helpers return the plain client and an empty callback list. Nothing fails. The rest of the codebase doesn't know whether observability is on. This matters because:
- You can deploy without credentials and add them later
- Tests don't need mock Langfuse servers
- New contributors can run the project without signing up for Langfuse
- There's no startup check or warning that pollutes logs

### What a trace looks like in the dashboard

A single agent run produces a trace tree roughly like this:

```
agent run [root, 5.2s, $0.001]
├── gpt-4o-mini [0.8s, 250 tokens]  "decide what to do first"
├── search_jobs [tool, 0.12s]
│   └── text-embedding-3-small [0.1s, 15 tokens]  "embed query"
├── gpt-4o-mini [0.6s, 450 tokens]  "read search results"
├── match_profile [tool, 0.02s]
├── match_profile [tool, 0.02s]
├── match_profile [tool, 0.02s]
├── gpt-4o-mini [0.7s, 680 tokens]  "compare match scores"
└── gpt-4o-mini [1.8s, 1200 tokens]  "write final answer"
```

Each node is clickable. You can see the exact prompt that went into each LLM call, the exact output, the cost, and the latency. For debugging, this replaces guessing with reading.

### Flushing matters for short-lived processes

Langfuse batches events and sends them to the dashboard every ~1 second. For long-lived processes (the FastAPI server), the buffer drains continuously and you never have to think about it. For short-lived processes (CLI commands), the Python process can exit before the buffer drains, silently losing traces.

That's why `src/job_rag/cli.py` calls `observability.flush()` in a `finally` block for commands that make LLM calls:

```python
try:
    asyncio.run(_run())
finally:
    flush()
```

`flush()` is also a no-op when Langfuse is disabled.

### Enabling Langfuse

Sign up at langfuse.com (free tier is generous), create a project, grab the public and secret keys, and add them to `.env`:

```bash
LANGFUSE_PUBLIC_KEY=pk-lf-...
LANGFUSE_SECRET_KEY=sk-lf-...
LANGFUSE_HOST=https://cloud.langfuse.com
```

Run any command that makes LLM calls, then open the Langfuse dashboard and watch the traces appear within a second or two.

---

## Evaluation - Proving the System Works

When you build a system that uses LLMs to answer questions, how do you know the answers are actually good? You can't just eyeball it - you need numbers. That's what evaluation does.

### The problem

The RAG pipeline has many moving parts: embedding, vector search, reranking, generation. Each one can silently degrade. Maybe the embeddings don't capture salary information well. Maybe the reranker favors skill-heavy postings over benefit-heavy ones. Maybe the LLM hallucinates a company that doesn't exist. Without measurement, you're flying blind.

### Golden dataset

The foundation of evaluation is a **golden dataset** - a set of questions where you already know the right answer. `data/eval/golden_queries.json` contains **18 queries** with:

- **question** - what the user asks
- **ground_truth** - the correct answer, written by hand after reading all 23 postings
- **expected_sources** - which companies should appear in the results

The 18 queries cover five categories:

| Category | Examples | Count |
|---|---|---|
| Skill-based | "Which jobs require LangChain?", "What roles need PyTorch?" | 6 |
| Filter-based | "What remote-friendly senior roles are available?" | 4 |
| Salary/benefits | "Which jobs offer the highest salary?" | 3 |
| Comparative | "Compare requirements between Trimble and GitLab" | 3 |
| Profile-relevant | "Find roles where automotive/HMI background is relevant" | 2 |

Building this dataset is manual work - run each query, read the answer, compare against the actual postings, write down what the correct answer should be. It takes time but it's the only way to have a reliable benchmark.

### RAGAS - the evaluation framework

[RAGAS](https://docs.ragas.io/) (Retrieval Augmented Generation Assessment) scores RAG systems on four dimensions. Each metric uses GPT-4o-mini as a judge - reading the question, the answer, the retrieved context, and the ground truth, then assigning a score from 0 to 1.

The numbers below are the current **v1.1 baseline**, measured under the atomic-skill decomposition extraction prompt, on all 18 golden queries.

| Metric | v1.1 score | v1.0 score | Δ | What it measures |
|---|---|---|---|---|
| Faithfulness | **0.81** (n=17/18) | 0.82 | ≈ flat | Answer statements are grounded in the retrieved context |
| Answer Relevancy | **0.68** | 0.74 | −0.06 | The answer actually addresses the question |
| Context Precision | **0.67** | 0.60 | **+0.07** | Top-ranked retrieved postings are the right ones |
| Context Recall | **0.43** | 0.47 | −0.04 | All relevant postings are present in the retrieval window |

**Faithfulness** - RAGAS breaks each answer into individual statements (*"Thieme requires LangChain"*, *"GovRadar is fully remote"*), then checks each against the retrieved context. Statements that can't be traced back are marked unfaithful. Under v1.1 the score is **0.81**, essentially unchanged from the v1.0 baseline of 0.82. One query (the Trimble-vs-GitLab comparative) produced an answer long enough that the faithfulness scorer hit GPT-4o-mini's `max_tokens` limit while trying to enumerate statement verdicts. The script catches this gracefully and excludes the failed sample, so faithfulness has n=17/18 while the other metrics have n=18/18. If the comparative query's partial scores had landed, faithfulness would likely be a bit higher.

**Answer Relevancy** - RAGAS generates hypothetical questions that the answer *would* be a good response to, then compares those to the original question using embeddings. Similar → relevant. Under v1.1, **0.68** (down from 0.74). The drop comes from a few metadata queries where the system's answer is honest-but-unhelpful (*"the retrieved context doesn't contain information about vacation days"*), which hurts relevancy even though it's the correct response to give.

**Context Precision** - Are the top-ranked retrieved postings the ones that actually contain the answer? Under v1.1, **0.67** - up from 0.60 in v1.0. **This is the biggest improvement**, and it's exactly the metric that atomic-skill decomposition should improve: when postings store their requirements as atomic skills (`langchain`, `fastapi`, `vector databases`) rather than compound sentences, the embedded chunks become more precisely aligned with skill-based queries, so the retriever finds the right posting more often.

**Context Recall** - Did we retrieve *all* the relevant documents? Under v1.1, **0.43** (slightly down from 0.47). We retrieve 20 candidates and rerank to 5, but some questions (like *"which jobs require Python?"*) have 10+ relevant postings across the corpus, so 5 can't cover them all. The small drop from v1.0 may be partial noise or a mild side-effect of having more chunks per posting (76 vs 74) - the semantic signal is slightly more spread out across chunks.

### What the scores reveal

| Query type | Faithfulness | Relevancy | Precision | Recall |
|---|---|---|---|---|
| Skill queries (LangChain, RAG, PyTorch, Docker, agentic AI) | 0.93-1.00 | 0.86-1.00 | 1.00 | 0.50-0.78 |
| Domain queries (German language, automotive/HMI) | 0.82-1.00 | 0.66-0.98 | 1.00 | 0.67-0.86 |
| Comparative (Trimble vs GitLab) | (skipped) | 0.73 | 1.00 | 1.00 |
| Filter queries (remote senior, Berlin, entry-level) | 0.50-0.92 | 0.69-1.00 | 0.00-0.68 | 0.00-0.44 |
| Metadata (salary, vacation, benefits) | 0.20-1.00 | 0.00 | 0.00-1.00 | 0.00 |

The system excels at skill-based semantic search - exactly what it was designed for. It does well on domain queries now that v1.1 decomposition has atomized phrases like *"Fluent German"* and *"automotive AI solutions"* into matchable units. It struggles with metadata queries (vacation days, salaries, benefits) because the embeddings encode *what a job is about*, not *what perks it offers*. That's a known limitation of pure dense retrieval. Adding hybrid search (dense + BM25 keyword) or routing metadata queries to structured SQL filters would fix it. This is the most obvious next-level improvement for the retrieval layer.

### Running the evaluation

```bash
# Requires: running database with embeddings, OPENAI_API_KEY in .env
uv run python scripts/evaluate.py
```

The script:
1. Loads the 18 golden queries
2. Runs the full RAG pipeline for each (embed → search → rerank → generate)
3. Scores each answer with the 4 RAGAS metrics (4 calls per query × 18 = 72 LLM scoring calls)
4. Prints a summary and saves per-query results to `data/eval/results.json`

Total cost: ~$0.10-0.15.

### Extraction accuracy tests

A separate form of evaluation: *did the extraction pipeline produce correct data?*

Five postings were manually verified - reading the markdown and writing down exactly what the extraction should produce (company, seniority, remote policy, must-have skill count, key required skills, etc.). Expectations live in `data/eval/extraction_ground_truth.json`. A captured extraction run is in `data/eval/extraction_results.json`.

`tests/test_extraction_accuracy.py` compares the two:

- Does the company name match?
- Is the remote policy correct?
- Is the salary present when expected?
- Is the must-have skill count within the expected range?
- Are key skills (Python, LangChain, RAG, etc.) present?

This produces **50 parametrized tests** (10 categories × 5 postings). Run with:

```bash
uv run pytest -m eval
```

These tests don't call the OpenAI API - they compare stored outputs against stored expectations. Fast, free, deterministic. Excluded from CI because they depend on specific eval data files.

---

## The API - How to Talk to the System

**Command:** `job-rag serve` (starts the server at `http://localhost:8000`)

| Method | Endpoint | What it does |
|---|---|---|
| `GET` | `/health` | Checks if the database is reachable (no auth required) |
| `GET` | `/search?q=...&generate=true` | Semantic search with RAG-generated answer (30 req/min) |
| `GET` | `/search?q=...&generate=false` | Semantic search, raw ranked results, no LLM answer (30 req/min) |
| `GET` | `/search?q=...&seniority=senior` | Search with filters (30 req/min) |
| `GET` | `/match/{posting_id}` | Score user profile against one posting (30 req/min) |
| `GET` | `/gaps` | Top missing skills across all postings (30 req/min) |
| `GET` | `/gaps?seniority=senior` | Gaps for senior roles only (30 req/min) |
| `POST` | `/ingest` | Upload a new markdown file, max 1 MB (5 req/min) |
| `POST` | `/agent` | Run the LangGraph agent on a query, return final answer + tool call trace (10 req/min) |
| `GET` | `/agent/stream?q=...` | Stream the agent as SSE events: tool_start, token, tool_end, final (10 req/min) |

All endpoints except `/health` require a Bearer token when `JOB_RAG_API_KEY` is set. When the key is empty (the default), auth is disabled for local development. Rate limits are per-IP, in-memory, and per-process.

Visit `http://localhost:8000/docs` for interactive API documentation where you can try each endpoint in your browser.

Under the hood, every route uses `Depends(get_session)` to get an async SQLAlchemy session, plus `Depends(require_api_key)` and a rate limiter dependency. The lifespan handler in `api/app.py` disposes the async engine on shutdown.

---

## The CLI - Terminal Commands

| Command | What it does |
|---|---|
| `job-rag init-db` | Create database tables + enable pgvector extension (run once) |
| `job-rag ingest --dir data/postings` | Process all markdown files into the database |
| `job-rag ingest --show-cost` | Same, but print total extraction cost |
| `job-rag embed` | Generate embeddings for postings that don't have them yet |
| `job-rag embed --show-cost` | Same, with cost output |
| `job-rag list` | Show all ingested postings in a table |
| `job-rag list --company GitLab` | Filter by company substring |
| `job-rag stats` | Show skill frequency, category breakdown, seniority + remote distribution |
| `job-rag serve` | Start the FastAPI server |
| `job-rag serve --reload` | Same, with auto-reload for development |
| `job-rag reset --yes` | Wipe all postings, requirements, and chunks (forces full re-extraction) |
| `job-rag mcp` | Start the MCP stdio server (for Claude Code) |
| `job-rag agent "<query>"` | Run the LangGraph agent on one query, print the final answer |
| `job-rag agent --stream "<query>"` | Same, with tool calls and token-by-token streaming |

`reset` is useful after bumping `PROMPT_VERSION` - you can wipe the DB and re-ingest under the new prompt in two commands.

---

## Deployment - Running in Docker

### The problem

To run the system locally without Docker, you need:
- PostgreSQL with pgvector installed
- Python 3.12 with ~25 packages installed
- The cross-encoder model downloaded (~80MB)
- An `.env` file with your OpenAI API key
- Four commands in order: `init-db`, `ingest`, `embed`, `serve`

That's a lot. Docker packages everything so `docker compose up` does it all.

### How Docker works (the short version)

A **Dockerfile** is a recipe for building an image - a snapshot of a computer with everything installed. A **container** is a running instance of an image. **Docker Compose** orchestrates multiple containers (database + app) so they can talk to each other.

### The Dockerfile - two-stage build

Uses a **multi-stage build** to keep the final image small:

**Stage 1 (builder)**: starts with a Python 3.12 image that has `uv` preinstalled. Copies the project files, installs all dependencies, pre-downloads the cross-encoder model. This stage is ~3GB because it includes compilers and build tools.

One important optimization: `ENV UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu` installs **CPU-only PyTorch**. The default PyTorch includes CUDA support (~1.5GB), which is wasted space since the cross-encoder runs fine on CPU.

**Stage 2 (runtime)**: starts with a clean slim Python 3.12 image. Creates a non-root `appuser` (UID 1000) and copies only:
- The virtual environment from stage 1
- The cached Hugging Face model (into the user's home directory)
- The source code and data directory

Build tools are discarded. The container runs as `appuser`, not root, for defense in depth.

```dockerfile
# Stage 1: install everything
FROM ghcr.io/astral-sh/uv:0.6-python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --frozen --no-dev
RUN uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Stage 2: copy only what's needed, run as non-root
FROM python:3.12-slim-bookworm
WORKDIR /app
RUN useradd -m -u 1000 appuser
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /root/.cache/huggingface /home/appuser/.cache/huggingface
RUN chown -R appuser:appuser /home/appuser/.cache
COPY src/ src/
COPY data/ data/
RUN chown -R appuser:appuser /app
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
USER appuser
ENTRYPOINT ["/app/docker-entrypoint.sh"]
```

### The entrypoint script

`scripts/docker-entrypoint.sh` runs four commands in order on container start:

```bash
job-rag init-db       # create tables (idempotent)
job-rag ingest        # process markdown files (skips duplicates)
job-rag embed         # generate embeddings (skips already-embedded)
uvicorn ...           # start the API server
```

On the first run, it does all the work. On subsequent runs, ingest and embed detect existing data and skip to serving - zero API cost.

### Docker Compose - orchestrating both services

`docker-compose.yml` defines two services:

**db** - PostgreSQL with pgvector, plus a healthcheck. The database port is not exposed to the host (only reachable by other containers on the Docker network). Credentials come from environment variables:

```yaml
db:
  image: pgvector/pgvector:pg17
  expose:
    - "5432"
  environment:
    POSTGRES_USER: ${POSTGRES_USER:-postgres}
    POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:?Set POSTGRES_PASSWORD in .env}
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-postgres}"]
    interval: 5s
    timeout: 5s
    retries: 5
```

`POSTGRES_PASSWORD` is required. If it is not set in `.env`, Docker Compose will refuse to start.

**app** - the FastAPI application:

```yaml
app:
  build: .
  ports:
    - "8000:8000"
  environment:
    DATABASE_URL: postgresql://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD}@db:5432/job_rag
    ASYNC_DATABASE_URL: postgresql+asyncpg://${POSTGRES_USER:-postgres}:${POSTGRES_PASSWORD}@db:5432/job_rag
    OPENAI_API_KEY: ${OPENAI_API_KEY}
    JOB_RAG_API_KEY: ${JOB_RAG_API_KEY:-}
  depends_on:
    db:
      condition: service_healthy
```

Four important details:

1. **`DATABASE_URL` uses `db` not `localhost`** - inside Docker's network, containers find each other by service name. The `app` container reaches PostgreSQL at `db:5432`. These env vars override the `localhost` defaults in `config.py`.

2. **`depends_on: condition: service_healthy`** - the app won't start until PostgreSQL's healthcheck passes. Without this, the app would crash trying to connect to an unready database.

3. **`OPENAI_API_KEY: ${OPENAI_API_KEY}`** - reads the key from your host machine's environment (or `.env`) and passes it through.

4. **`JOB_RAG_API_KEY`** - when set, all API endpoints except `/health` require a `Bearer <key>` header. When empty (the default), auth is disabled for local development.

### Running it

```bash
cp .env.example .env          # set OPENAI_API_KEY and POSTGRES_PASSWORD (both required)
                              # optionally set JOB_RAG_API_KEY to enable API auth
docker compose up             # build image + start both services
# Wait for "Starting API server..."
open http://localhost:8000/docs
```

---

## CI/CD - Automated Quality Checks

### The problem

You push code to GitHub. Did you break anything? Lint errors? Type errors? Failing tests? Checking manually is error-prone. CI automates it on every push.

### GitHub Actions

The configuration is in `.github/workflows/ci.yml`. Every push to `master` and every pull request targeting `master` triggers the workflow, which runs four steps.

**1. Lint with ruff:**

```bash
uv run ruff check src/ tests/
```

Ruff is a Rust-based linter that checks the entire codebase in <1 second. Rules: PEP 8 style (E), pyflakes errors (F), import sorting (I), Python upgrade suggestions (UP).

**2. Type check with pyright:**

```bash
uv run pyright src/
```

If a function says it returns `str` but actually returns `int`, pyright catches it. Prevents a whole category of runtime errors.

**3. Test with pytest:**

```bash
uv run pytest -m "not eval"
```

Runs all **89 unit tests** (including a security test suite covering auth, rate limiting, delimiter injection, and content size caps). The `-m "not eval"` flag skips the 50 extraction accuracy tests (which need eval data files). All 89 unit tests are fully mocked - no database, no OpenAI key, no network required.

**4. Audit dependencies with pip-audit:**

```bash
uv run pip-audit
```

Scans all installed packages against known vulnerability databases (PyPI, OSV). Fails the build if any dependency has a published CVE with an available fix.

### Caching

The workflow uses `astral-sh/setup-uv@v4` with `enable-cache: true`. First run downloads everything (~3-4 minutes, mostly PyTorch). Subsequent runs hit the cache (~30 seconds).

---

## File Structure

```
job-rag/
├── data/
│   ├── postings/                 23 markdown job posting files (input)
│   ├── profile.json              61-skill user profile
│   └── eval/
│       ├── golden_queries.json           18 queries + ground truth
│       ├── extraction_ground_truth.json  Expected extractions for 5 postings
│       ├── extraction_results.json       Stored extraction outputs (v1.0 baseline)
│       └── results.json                  RAGAS scores
│
├── src/job_rag/
│   ├── __init__.py
│   ├── cli.py                    Typer CLI (init-db, ingest, embed, serve, agent, mcp, reset, ...)
│   ├── config.py                 pydantic-settings (OpenAI, Langfuse, DB, model choices)
│   ├── logging.py                structlog setup
│   ├── models.py                 Pydantic domain models and enums
│   ├── observability.py          Langfuse integration (optional, fails open)
│   │
│   ├── db/
│   │   ├── engine.py             SQLAlchemy sync + async engines
│   │   └── models.py             ORM models (JobPostingDB, JobRequirementDB, JobChunkDB)
│   │
│   ├── extraction/
│   │   ├── prompt.py             System prompt v1.1 with decomposition rules
│   │   └── extractor.py          Instructor + GPT-4o-mini extraction with retries
│   │
│   ├── services/
│   │   ├── ingestion.py          Read → dedupe → extract → store
│   │   ├── embedding.py          Posting + chunk embeddings, cost tracking
│   │   ├── retrieval.py          pgvector search, rerank, RAG generation chain
│   │   └── matching.py           Alias-class fuzzy matching, gap aggregation
│   │
│   ├── api/
│   │   ├── app.py                FastAPI app with lifespan
│   │   ├── auth.py               Bearer token auth + per-endpoint rate limiting
│   │   ├── deps.py               Async session dependency
│   │   └── routes.py             All endpoints incl. /agent and /agent/stream
│   │
│   ├── mcp_server/
│   │   ├── tools.py              Shared async tool layer (single source of truth)
│   │   └── server.py             FastMCP stdio server
│   │
│   └── agent/
│       ├── tools.py              LangChain @tool wrappers
│       ├── graph.py              LangGraph create_react_agent + run_agent
│       └── stream.py             astream_events → structured dict adapter
│
├── tests/
│   ├── conftest.py               Shared fixtures
│   ├── test_models.py            Pydantic model tests
│   ├── test_extraction.py        Mocked Instructor extraction tests
│   ├── test_matching.py          Alias matching, scoring, gap aggregation
│   ├── test_retrieval.py         Reranker tests (mocked cross-encoder)
│   ├── test_api.py               FastAPI endpoint tests (mocked sessions)
│   ├── test_mcp_server.py        MCP tool tests (mocked sessions)
│   ├── test_agent.py             Agent + streaming tests (mocked LangGraph)
│   ├── test_observability.py     Langfuse enabled/disabled path tests
│   ├── test_security.py         Auth, rate limiting, delimiter escape, size cap tests
│   └── test_extraction_accuracy.py  50 eval-marked ground truth comparisons
│
├── scripts/
│   ├── evaluate.py               RAGAS evaluation runner
│   └── docker-entrypoint.sh      Container startup: init → ingest → embed → serve
│
├── docs/
│   ├── how-it-works.md           This document
│   └── project-job-rag.md        Phase-by-phase project plan
│
├── .env                          API keys and DB URLs (not in git)
├── .env.example                  Template for .env
├── .github/workflows/ci.yml      CI pipeline: ruff + pyright + pytest + pip-audit
├── Dockerfile                    Multi-stage build (uv + CPU PyTorch → slim runtime)
├── docker-compose.yml            PostgreSQL + FastAPI orchestration
├── pyproject.toml                Project metadata + dependencies
├── uv.lock                       Pinned dependency versions
└── README.md                     Portfolio-facing overview
```

---

## End-to-End Example

### The Docker way (one command)

```
1. cp .env.example .env           Set OPENAI_API_KEY and POSTGRES_PASSWORD
2. docker compose up              Build image + start database + start app

   [db]  PostgreSQL ready ✓
   [app] Initializing database...
   [app] Ingesting postings... 23 ingested
   [app] Generating embeddings... 23 embedded
   [app] Starting API server...

3. Visit http://localhost:8000/docs   Interactive API docs
```

### The local development way

```
1. docker compose up db -d              Start just the database
2. uv sync                              Install Python dependencies
3. job-rag init-db                      Create tables
4. job-rag ingest --show-cost           Process 23 files → ~$0.025
5. job-rag embed --show-cost            Generate embeddings → ~$0.00016
6. job-rag serve --reload               Start API server with hot reload
```

Then try some queries:

```bash
# Direct semantic search via HTTP
curl "http://localhost:8000/search?q=which+jobs+want+LangChain"

# Gap analysis for senior remote roles
curl "http://localhost:8000/gaps?seniority=senior&remote=remote"

# One-shot agent via CLI
job-rag agent "Which 3 remote senior AI Engineer roles fit my profile best, and why?"

# Agent with real-time tool call streaming
job-rag agent --stream "Find roles using LangGraph"

# Agent via SSE endpoint (in another terminal)
curl -N "http://localhost:8000/agent/stream?q=Find+remote+senior+roles"
```

Run the test suites:

```bash
uv run pytest                       # 89 unit tests (mocked, fast, free)
uv run pytest -m eval                # 50 extraction accuracy tests (stored comparisons)
uv run python scripts/evaluate.py    # RAGAS eval (~$0.13)
```

### What one agent query looks like under the hood

You run:

```bash
job-rag agent "Which 3 remote senior AI Engineer roles fit my profile best?"
```

Behind the scenes:

1. The CLI imports `build_agent()` from `agent/graph.py`, which constructs a LangGraph ReAct agent wired to three tools (`search_jobs`, `match_profile`, `analyze_gaps`).
2. The agent runs. GPT-4o-mini reads your question and outputs a tool call: `search_jobs(query="senior AI Engineer", remote_only=true, limit=5)`.
3. The tool executes. It queries PostgreSQL via pgvector cosine distance, gets 20 candidates, reranks with the cross-encoder, and returns the top 5 as a JSON list.
4. The agent reads the result, decides to refine, calls `search_jobs` again with different terms.
5. The agent picks 3 promising postings and calls `match_profile(posting_id=...)` on each. Each call loads your `profile.json`, runs fuzzy alias-based matching against the posting's requirements, and returns a score plus matched/missed skills.
6. The agent reads the three match reports, sorts by score descending (per its system prompt), and writes a synthesized answer: *"Here are your top 3 fits, ranked by match score. 1. IU Group (0.588) - matched on Python, FastAPI, tool use, embeddings, vector search, monitoring, testing. Gaps: ..."*
7. If Langfuse is configured, all 5+ LLM calls and all 5 tool invocations show up as a nested trace tree in the dashboard.
8. The CLI calls `observability.flush()` on exit so no traces are lost.

Total: ~5 seconds, ~$0.001, 5 tool calls, 6 LLM calls.

---

## Cost summary

| Operation | Cost |
|---|---|
| Extract 23 postings (GPT-4o-mini, v1.1 prompt) | ~$0.025 |
| Embed 23 postings + 74 chunks (text-embedding-3-small) | ~$0.00016 |
| One agent query (~5 tool calls + synthesis) | ~$0.001 |
| RAGAS evaluation (72 scoring calls + 18 RAG runs) | ~$0.13 |

**Total cost to stand up the full system and run it end-to-end: ~$0.03.** Evaluation is an extra ~$0.13 on top if you want the RAGAS scores.

---

## What to read next

- **README.md** - the portfolio-facing overview. Shorter, narrative-first, includes the IU Group "what it actually found" story.
- **docs/project-job-rag.md** - the phase-by-phase project plan with what was built in each phase, design decisions, and results.
- **src/job_rag/services/retrieval.py** - the clearest single file if you want to see the RAG core end-to-end in one place.
- **src/job_rag/agent/graph.py** - the LangGraph agent assembly, system prompt, and `run_agent` helper.
- **src/job_rag/mcp_server/tools.py** - the shared async tool layer. If you change one function here, all three entry points (MCP, agent, FastAPI) get the update automatically.
