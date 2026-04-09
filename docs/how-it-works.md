# How Job RAG Works — A Complete Walkthrough

This document explains every piece of the Job RAG system, from the ground up.

---

## What Does This System Do?

You have 23 AI Engineer job postings saved as text files. This system:

1. **Reads** each file and uses AI to pull out structured information (company, skills, salary, etc.)
2. **Stores** everything in a database
3. **Understands meaning** by converting text into numbers (embeddings)
4. **Answers questions** like "which jobs want LangChain experience?" by searching for meaning, not keywords
5. **Scores how well you match** each job and tells you what skills you're missing
6. **Proves it works** by evaluating answer quality with RAGAS metrics
7. **Runs anywhere** via Docker — one command starts the entire system

---

## The Building Blocks

Before diving into the workflow, here's what each technology does and why it's needed.

### PostgreSQL (the database)

A database is just an organized place to store data in tables — like spreadsheets with rows and columns. PostgreSQL is one of the most popular databases. We use it to store job postings, their requirements, and embeddings.

### pgvector (the vector extension)

Normal databases store text and numbers. pgvector is an add-on that lets PostgreSQL also store and search **vectors** — lists of numbers that represent meaning (more on this below). Without pgvector, we'd need a separate database just for semantic search.

### Docker (runs the database)

Instead of installing PostgreSQL on your computer (which involves configuration, version conflicts, etc.), Docker runs it in an isolated container. Think of it as a tiny virtual computer that only runs PostgreSQL. The `docker-compose.yml` file describes what to run:

- Which version of PostgreSQL to use (`pgvector/pgvector:pg17`)
- What port to expose (`5432`)
- What username and password to set (`postgres` / `postgres`)
- Where to keep data so it survives restarts (a `pgdata` volume)

`docker compose up` starts it. `docker compose down` stops it. Your data is safe either way.

### Python (the programming language)

All the logic is written in Python. When you type `job-rag ingest` or `job-rag embed`, you're running Python code.

### SQLAlchemy (talks to the database)

Instead of writing raw SQL queries by hand, SQLAlchemy lets you describe tables as Python classes and interact with the database using Python code. You define a class like `JobPostingDB` with fields like `title`, `company`, `location`, and SQLAlchemy translates that into the actual database table.

### Pydantic (validates data)

Pydantic makes sure data has the right shape. If you say "seniority must be one of: junior, mid, senior, staff, lead, unknown", Pydantic will reject anything else. This prevents garbage data from entering the system.

### OpenAI API (the AI)

The system calls OpenAI's servers to use their AI models:

- **GPT-4o-mini** — reads job postings and extracts structured information
- **text-embedding-3-small** — converts text into vectors (lists of 1536 numbers)

Both cost money per use, but very little — the entire system costs about $0.03 to process 23 postings.

### Instructor (forces the AI to be structured)

Normally when you ask an AI a question, it replies with free-form text. Instructor wraps the OpenAI API so that instead of getting a paragraph back, you get a structured object with exact fields. If the AI returns something invalid (like an unknown seniority level), Instructor automatically asks it to try again.

### Typer (the command line interface)

Typer turns Python functions into terminal commands. Instead of opening Python and calling functions manually, you type `job-rag ingest` or `job-rag stats` in your terminal.

### FastAPI (the web server)

FastAPI creates a web API — a set of URLs you can visit to interact with the system. For example, visiting `http://localhost:8000/search?q=RAG+experience` returns search results as JSON. This is how other applications (or a future frontend) would talk to the system.

### LangChain (generates answers)

After finding relevant job postings, LangChain feeds them to GPT-4o-mini along with your question and gets back a natural language answer. It handles the prompt formatting and the communication with the AI.

### Cross-encoder (reranks results)

A small AI model (~80MB) that runs directly in your Python process (no API calls, no server, no cost per use). It takes search results and re-scores them for relevance. It's slower but more accurate than vector search alone, so we use it as a second pass to pick the best results from a larger pool.

The model (`cross-encoder/ms-marco-MiniLM-L-6-v2`) is downloaded automatically from Hugging Face the first time the code runs. After that, it's cached on your disk at `~/.cache/huggingface/` and loads from there instantly (~1-2 seconds). No need to install it manually via Ollama or any other tool — the `sentence-transformers` Python package handles the download, caching, and loading.

This is different from large language models like GPT-4o or Llama which are billions of parameters and need dedicated servers. The cross-encoder is a small, specialized model — it doesn't generate text, it just scores how well two texts match. Small enough to run on any laptop CPU in milliseconds.

### structlog (logging)

Records what the system does — how many files were processed, how many tokens were used, how much it cost. Useful for debugging and tracking.

### RAGAS (evaluation)

A Python library that scores how well a RAG system answers questions. It uses an LLM (GPT-4o-mini) as a judge — feeding it the question, the answer, the retrieved context, and the expected answer, then asking "is this faithful? is this relevant?" This gives you numbers (0 to 1) instead of gut feelings.

### GitHub Actions (CI/CD)

GitHub's built-in automation. Every time you push code, GitHub spins up a fresh Linux machine, installs your dependencies, and runs your linter, type checker, and tests. If anything fails, you see a red ❌ on the commit. This catches bugs before they reach production.

### Dockerfile (containerization)

A recipe that describes how to build a self-contained image of your application — all code, dependencies, and models baked in. Anyone with Docker can run the image without installing Python, PostgreSQL, or anything else. The multi-stage build pattern keeps the final image small by discarding build tools after they're used.

---

## The Database Tables

The database has three tables. Think of each as a spreadsheet:

### `job_postings` — one row per job (23 rows)

| Column | Example | Purpose |
|---|---|---|
| id | `a1b2c3d4-...` | Unique identifier |
| title | "Senior AI Engineer" | Job title |
| company | "GitLab" | Company name |
| location | "Germany" | Where the job is |
| remote_policy | "remote" | Remote / hybrid / onsite |
| seniority | "senior" | Seniority level |
| salary_min | 70000 | Minimum salary in EUR/year |
| salary_max | 90000 | Maximum salary in EUR/year |
| salary_raw | "€70k-€90k/year" | Original text from posting |
| requirements | *(linked table)* | Skills needed |
| responsibilities | "Build RAG pipelines..." | What you'd do |
| benefits | "30 vacation days..." | Perks |
| raw_text | *(full markdown)* | Original file content |
| content_hash | "a8f3b2..." | SHA-256 hash for dedup |
| embedding | [0.012, -0.034, ...] | 1536 numbers representing meaning |

### `job_requirements` — one row per skill per job (359 rows)

| Column | Example | Purpose |
|---|---|---|
| id | `e5f6g7h8-...` | Unique identifier |
| posting_id | `a1b2c3d4-...` | Links to the parent job posting |
| skill | "Python" | Name of the skill |
| category | "language" | Type: language, framework, tool, concept, etc. |
| required | true | Must-have (true) or nice-to-have (false) |

Why a separate table? Because one job can have 7-15 skills. Keeping them in their own table lets you easily ask "which skill appears most often?" or "which jobs require Docker?"

### `job_chunks` — sections of each posting (73 rows)

| Column | Example | Purpose |
|---|---|---|
| id | `i9j0k1l2-...` | Unique identifier |
| posting_id | `a1b2c3d4-...` | Links to the parent job posting |
| section | "must_have" | Which part: responsibilities, must_have, nice_to_have, benefits |
| content | "Senior AI Eng at GitLab\nMust-have: Python, LangChain..." | The text of that section |
| embedding | [0.008, -0.021, ...] | 1536 numbers representing meaning of this section |

Each posting is split into sections so searches can find the *specific part* of a posting that's relevant, not just "this posting is somewhat related."

---

## Pipeline 1: Ingestion — Getting Data In

**Command:** `job-rag ingest --dir data/postings`

This processes all 23 markdown files and stores them in the database. Here's what happens to each file:

### Step 1: Read the file

The system reads a markdown file like `gitlab-senior-ai-engineer.md`. It's just text — headings, bullet points, paragraphs.

### Step 2: Check for duplicates

Before doing anything expensive (calling the AI), the system checks if this posting is already in the database. It does this two ways:

- **Content hash** — takes the full text and generates a unique fingerprint (SHA-256). If the same text was already processed, skip it.
- **LinkedIn ID** — extracts the job ID from the LinkedIn URL (e.g., `/jobs/view/4372462825/` → `4372462825`). If a posting with the same LinkedIn ID exists, skip it.

This is why running `job-rag ingest` a second time does nothing and costs $0.

### Step 3: Extract structured data with AI

The raw markdown is sent to GPT-4o-mini along with a detailed system prompt that says:

- "Extract the company name, title, location"
- "Classify each skill as language, framework, tool, concept, cloud, database, domain, or soft_skill"
- "Mark skills as must-have or nice-to-have"
- "Convert salary to EUR/year"
- "Map seniority: Mid-Senior → senior, Entry level → junior"

Instructor forces the AI to return data in the exact shape defined by the Pydantic `JobPosting` model. If the AI returns an invalid value (like `"seniority": "experienced"`), Pydantic rejects it and Instructor asks the AI to try again.

**Cost:** ~$0.001 per posting (~0.1 cents).

### Step 4: Store in database

The validated data is inserted into the database:

- 1 row in `job_postings` with all the structured fields
- 7-15 rows in `job_requirements`, one per skill

After all 23 files: 23 posting rows, 359 requirement rows, ~$0.025 total cost.

---

## Pipeline 1.5: Embedding — Making Search Possible

**Command:** `job-rag embed`

This converts text into numbers so the system can search by meaning instead of keywords.

### What is an embedding?

An embedding is a list of 1536 numbers that represents the *meaning* of a text. The AI model (text-embedding-3-small) has been trained on billions of texts and learned that:

- "Python developer" and "Python programmer" → similar numbers (close together)
- "Python developer" and "Python snake handler" → different numbers (far apart)
- "remote work" and "work from home" → similar numbers

This is what makes semantic search possible. You don't need the exact keyword — the system understands that "RAG experience" is related to "retrieval augmented generation" even if those exact words don't appear.

### What gets embedded?

For each of the 23 postings, the system creates:

**1. One posting-level embedding** — a formatted summary:
```
Title: Senior AI Engineer
Company: GitLab
Must-have skills: Python, LangChain, RAG
Responsibilities: Build AI-powered features...
```
This becomes 1536 numbers stored in the `embedding` column of `job_postings`.

**2. Multiple chunk-level embeddings** — one per section:
- Responsibilities chunk → 1536 numbers
- Must-have chunk → 1536 numbers
- Nice-to-have chunk → 1536 numbers
- Benefits chunk → 1536 numbers

Each stored as a row in `job_chunks`. Not every posting has all 4 sections, which is why 23 postings produce 73 chunks, not 92.

**Cost:** ~$0.000168 total for all 23 postings (essentially free).

---

## Pipeline 2: Retrieval — Answering Questions

**Endpoint:** `GET /search?q=which jobs value RAG experience`

When you ask a question, the system goes through four stages:

### Stage 1: Embed the query

Your question "which jobs value RAG experience" is converted into 1536 numbers using the same AI model. Now your question and all the postings live in the same "number space" and can be compared mathematically.

### Stage 2: Vector search (pgvector)

PostgreSQL compares your query's 1536 numbers against each posting's 1536 numbers using **cosine distance** — a mathematical formula that measures how similar two lists of numbers are. It returns the 20 most similar postings, sorted by relevance.

This happens entirely inside the database with a SQL query. pgvector makes it fast.

This is like casting a wide net — get 20 candidates, some may not be perfect.

### Stage 3: Rerank with cross-encoder

The cross-encoder model (running locally on your computer) reads each of the 20 results alongside your question and gives each one a more accurate relevance score. It picks the top 5.

Why two stages? Vector search (Stage 2) is fast but approximate — it compares compressed representations. The cross-encoder (Stage 3) is slower but more accurate — it reads the full text and truly understands if it matches your question. So we use Stage 2 to narrow down quickly, then Stage 3 to pick the best.

### Stage 4: Generate answer (LangChain + GPT-4o-mini)

The top 5 postings are formatted as context and sent to GPT-4o-mini along with your original question:

```
System: "You are a job search assistant..."
Human: "Context: [top 5 postings with details]
        Question: which jobs value RAG experience?"
```

The AI reads the context and writes a natural language answer like:

> "The following jobs value RAG experience:
> 1. **Senior AI Engineer at Thieme** — requires RAG system design...
> 2. **Senior AI Engineer at GovRadar** — requires RAG and LangChain..."

The response includes both the answer and the source postings (with similarity scores) so you can verify.

---

## Pipeline 3: Profile Matching — How Well Do You Fit?

**Endpoint:** `GET /match/{posting_id}`

### Your profile

`data/profile.json` contains your skills with proficiency levels:
```json
{"name": "Python", "proficiency": "intermediate", "years": 3.0}
{"name": "Docker", "proficiency": "intermediate", "years": 2.0}
...30 skills total
```

### The matching process

For a given job posting, the system:

1. **Lists all must-have and nice-to-have skills** from the posting's requirements
2. **Checks each skill against your profile** using fuzzy matching — "PostgreSQL" matches your "SQL", "React.js" matches your "React", etc.
3. **Calculates a score:**

```
score = (matched must-haves / total must-haves) * 0.7
      + (matched nice-to-haves / total nice-to-haves) * 0.3
```

Must-haves are weighted more heavily (70%) because they're dealbreakers.

4. **Returns a report:**
   - Score (0.0 to 1.0)
   - Which skills you match
   - Which skills you're missing (gaps)
   - Bonus signals (remote match, salary meets your minimum)

### Gap analysis

**Endpoint:** `GET /gaps`

Runs the matching across all 23 postings and aggregates: "LangChain is missing in 13% of postings, ML in 17.4%, FastAPI in 13%." This tells you which skills to learn first for maximum impact.

---

## The API — How to Talk to the System

**Command:** `job-rag serve` (starts the server at `http://localhost:8000`)

| Endpoint | What it does |
|---|---|
| `GET /health` | Checks if the database is reachable |
| `GET /search?q=...` | Semantic search with AI-generated answer |
| `GET /search?q=...&generate=false` | Semantic search, raw results only (no AI answer) |
| `GET /search?q=...&seniority=senior` | Search with filters |
| `GET /match/{posting_id}` | Match one posting against your profile |
| `GET /gaps` | Top missing skills across all postings |
| `GET /gaps?seniority=senior` | Gaps for senior roles only |
| `POST /ingest` | Upload a new markdown file |

Visit `http://localhost:8000/docs` for interactive API documentation where you can try each endpoint in your browser.

---

## The CLI — Terminal Commands

| Command | What it does |
|---|---|
| `job-rag init-db` | Creates the database tables (run once) |
| `job-rag ingest --dir data/postings` | Process all markdown files into the database |
| `job-rag ingest --show-cost` | Same, but also shows how much it cost |
| `job-rag embed --show-cost` | Generate embeddings for all postings |
| `job-rag list` | Show all ingested postings in a table |
| `job-rag list --company GitLab` | Filter by company |
| `job-rag stats` | Show skill frequency, seniority distribution, etc. |
| `job-rag serve` | Start the API server |

---

## File Structure

```
job-rag/
├── data/
│   ├── postings/              23 markdown job posting files (input)
│   └── profile.json           Your skills and preferences
│
├── src/job_rag/
│   ├── config.py              Settings loaded from .env file
│   ├── logging.py             Structured logging setup
│   ├── models.py              Pydantic models (data shapes for validation)
│   ├── cli.py                 Terminal commands (ingest, embed, serve, etc.)
│   │
│   ├── db/
│   │   ├── engine.py          Database connection (sync + async)
│   │   └── models.py          Table definitions (ORM)
│   │
│   ├── extraction/
│   │   ├── prompt.py          Rules for the AI extraction
│   │   └── extractor.py       Calls GPT-4o-mini via Instructor
│   │
│   ├── services/
│   │   ├── ingestion.py       Read files → deduplicate → extract → store
│   │   ├── embedding.py       Convert text to vectors, store in DB
│   │   ├── retrieval.py       Search → rerank → generate answers
│   │   └── matching.py        Profile matching and gap analysis
│   │
│   └── api/
│       ├── app.py             FastAPI application setup
│       ├── deps.py            Database session for each request
│       └── routes.py          API endpoint definitions
│
├── tests/                     Automated tests (48 total)
├── docker-compose.yml         Runs PostgreSQL + pgvector in Docker
├── pyproject.toml             Project config and dependencies
└── .env                       API keys and database URL (not in git)
```

---

## End-to-End Example

Here's what happens from start to finish when you set up and use the system:

```
1. docker compose up -d              Start the database
2. job-rag init-db                   Create the tables
3. job-rag ingest --show-cost        Process 23 files → $0.025
4. job-rag embed --show-cost         Generate embeddings → $0.000168
5. job-rag serve                     Start the API server

Then visit:
http://localhost:8000/search?q=which jobs want LangChain experience

Response:
{
  "answer": "The following jobs value LangChain experience:
    1. Senior AI Engineer at Thieme — requires LangChain and RAG...
    2. Senior AI Engineer at GovRadar — requires LangChain...",
  "sources": [
    {"company": "Thieme", "similarity": 0.42, "rerank_score": 0.19},
    {"company": "GovRadar", "similarity": 0.44, "rerank_score": -2.08}
  ]
}
```

Total cost to process everything: **~$0.03** (3 cents).

---

## Pipeline 4: Evaluation — Proving the System Works

When you build a system that uses AI to answer questions, how do you know the answers are actually good? You can't just eyeball it — you need numbers. That's what evaluation does.

### The problem

The RAG pipeline has many moving parts: embedding, vector search, reranking, generation. Each one can silently degrade. Maybe the embeddings don't capture salary information well. Maybe the reranker favors skill-heavy postings over benefit-heavy ones. Maybe the LLM hallucinates a company that doesn't exist. Without measurement, you're flying blind.

### Golden dataset

The foundation of evaluation is a **golden dataset** — a set of questions where you already know the right answer. The file `data/eval/golden_queries.json` contains 18 queries with:

- **question** — what the user asks ("Which jobs require LangChain experience?")
- **ground_truth** — the correct answer, written by hand after reading all 23 postings
- **expected_sources** — which companies should appear in the results

The 18 queries cover five categories:

| Category | Examples | Count |
|---|---|---|
| Skill-based | "Which jobs require LangChain?", "What roles need PyTorch?" | 6 |
| Filter-based | "What remote-friendly senior roles are available?" | 4 |
| Salary/benefits | "Which jobs offer the highest salary?" | 3 |
| Comparative | "Compare requirements between Trimble and GitLab" | 3 |
| Profile-relevant | "Find roles where automotive/HMI background is relevant" | 2 |

Building this dataset is manual work. You run each query, read the answer, compare it against the actual postings, and write down what the correct answer should be. It takes time but it's the only way to have a reliable benchmark.

### RAGAS — the evaluation framework

[RAGAS](https://docs.ragas.io/) (Retrieval Augmented Generation Assessment) is a Python library that scores RAG systems on four dimensions. Each metric uses an LLM (GPT-4o-mini) to judge quality — it reads the question, the answer, the retrieved context, and the ground truth, then assigns a score from 0 to 1.

**Faithfulness (scored: 0.82)** — Does the answer only say things that appear in the retrieved context? A faithfulness score of 0.82 means 82% of the statements in the answers are supported by the context. The remaining 18% are either hallucinated or inferred beyond what was retrieved.

How it works internally: RAGAS breaks the answer into individual statements ("Thieme requires LangChain", "GovRadar is fully remote"), then checks each statement against the retrieved context. Statements that can't be traced back to the context are marked unfaithful.

**Answer Relevancy (scored: 0.74)** — Is the answer actually about what was asked? A score of 0.74 means the answers are mostly relevant, but some queries (especially about salary and benefits) get vague responses because the retrieval doesn't surface the right postings.

How it works: RAGAS generates hypothetical questions that the answer *would* be a good response to, then compares those questions to the original question using embeddings. If the hypothetical questions are similar to the real question, the answer is relevant.

**Context Precision (scored: 0.60)** — Are the retrieved documents actually relevant? A score of 0.60 means about 60% of the time, the top-ranked retrieved postings are the ones that contain the answer. For skill queries this is nearly perfect (1.0). For metadata queries like "which companies offer 30 vacation days?" it drops to 0.0 because the embeddings are optimized for skills and responsibilities, not benefits.

**Context Recall (scored: 0.47)** — Did we retrieve *all* the relevant documents? A score of 0.47 means we're only finding about half of the postings that should appear in the answer. This makes sense — we retrieve 20 postings and rerank to 5, but some questions have 8-10 relevant postings across the corpus.

### What the scores tell us

The scores reveal a clear pattern:

| Query type | Faithfulness | Relevancy | Precision | Recall |
|---|---|---|---|---|
| Skill queries ("LangChain", "PyTorch") | 0.95+ | 0.90+ | 1.00 | 0.50-1.00 |
| Comparative ("Trimble vs GitLab") | 1.00 | 0.73 | 1.00 | 1.00 |
| Metadata ("salary", "vacation days") | 0.50-1.00 | 0.00-0.98 | 0.00 | 0.00-1.00 |

The system excels at what it was designed for — skill-based semantic search. It struggles with metadata queries because the embeddings represent *what a job is about*, not *what benefits it offers*. This is a known limitation of embedding-based retrieval and could be improved with hybrid search (combining vector search with SQL filters on structured fields).

### Running the evaluation

```bash
# Requires: running database with embeddings, OPENAI_API_KEY in .env
uv run python scripts/evaluate.py
```

The script:
1. Loads the 18 golden queries
2. Runs the full RAG pipeline for each (embed query → vector search → rerank → generate)
3. Scores each answer using RAGAS metrics (4 API calls per query = 72 LLM scoring calls)
4. Prints a summary table and saves detailed per-query results to `data/eval/results.json`

Total evaluation cost: ~$0.10-0.15 (72 GPT-4o-mini calls for scoring, plus 18 queries for the RAG pipeline itself).

### Extraction accuracy tests

Separate from RAGAS, there's a second kind of evaluation: **did the AI extract the right data from the postings?**

Five postings were manually verified — reading the original markdown and writing down exactly what the extraction should produce (company name, seniority, remote policy, which skills are must-have, how many requirements there are, etc.). These expectations live in `data/eval/extraction_ground_truth.json`.

The actual extraction results from a verified run are stored in `data/eval/extraction_results.json`. The tests in `tests/test_extraction_accuracy.py` compare the two:

- Does the company name match exactly?
- Is the remote policy correct?
- Is the seniority level correct?
- Is the salary present when expected?
- Is the must-have skill count within the expected range?
- Are key skills (Python, LangChain, RAG, etc.) present in the right category?
- Are benefits present when they should be?

This produces 50 parametrized tests (10 test categories × 5 postings). Run them with:

```bash
uv run pytest -m eval
```

These tests don't call the OpenAI API — they compare stored results against stored expectations. They're fast, free, and deterministic.

---

## Deployment — Running in Docker

### The problem

To run the system locally, you need:
- PostgreSQL with pgvector installed
- Python 3.12 with ~20 packages installed
- The cross-encoder model downloaded (~80MB)
- An `.env` file with your OpenAI API key
- Three commands run in order: `init-db`, `ingest`, `embed`, then `serve`

That's a lot of steps. Docker packages everything so that `docker compose up` does it all.

### How Docker works (the short version)

A **Dockerfile** is a recipe for building an image — a snapshot of a computer with everything installed. A **container** is a running instance of that image. Docker Compose orchestrates multiple containers (database + app) so they can talk to each other.

### The Dockerfile — two-stage build

The Dockerfile uses a **multi-stage build** to keep the final image smaller:

**Stage 1 (builder):** Starts with a Python 3.12 image that has `uv` (the package manager) pre-installed. It copies the project files, installs all dependencies, and pre-downloads the cross-encoder model. This stage is big (~3GB) because it includes compilers and build tools.

One important optimization: it sets `UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu` to install **CPU-only PyTorch**. The default PyTorch includes CUDA support for GPUs, which adds ~1.5GB. The cross-encoder runs fine on CPU, so this is wasted space.

**Stage 2 (runtime):** Starts with a clean, slim Python 3.12 image. It copies only what's needed from Stage 1:
- The virtual environment (installed packages)
- The cached Hugging Face model
- The application source code and data

The build tools, compilers, and intermediate files from Stage 1 are discarded. The final image is smaller and more secure.

```dockerfile
# Stage 1: Install everything
FROM ghcr.io/astral-sh/uv:0.6-python3.12-bookworm-slim AS builder
WORKDIR /app
ENV UV_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu
COPY pyproject.toml uv.lock ./
COPY src/ src/
RUN uv sync --frozen --no-dev
RUN uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')"

# Stage 2: Copy only what's needed
FROM python:3.12-slim-bookworm
WORKDIR /app
COPY --from=builder /app/.venv /app/.venv
COPY --from=builder /root/.cache/huggingface /root/.cache/huggingface
COPY src/ src/
COPY data/ data/
ENV PATH="/app/.venv/bin:$PATH"
EXPOSE 8000
ENTRYPOINT ["/app/docker-entrypoint.sh"]
```

### The entrypoint script

When the container starts, it needs to set up the database before serving requests. The entrypoint script (`scripts/docker-entrypoint.sh`) runs four commands in order:

```bash
job-rag init-db       # Create tables (safe to run multiple times)
job-rag ingest        # Process markdown files (skips duplicates)
job-rag embed         # Generate embeddings (skips already-embedded)
uvicorn ...           # Start the API server
```

On the first run, it does all the work. On subsequent runs, `ingest` and `embed` detect that everything is already processed and skip ahead to serving — zero API cost.

### Docker Compose — orchestrating both services

The `docker-compose.yml` defines two services:

**db** — PostgreSQL with pgvector, the same as before, but now with a **healthcheck**:
```yaml
healthcheck:
  test: ["CMD-SHELL", "pg_isready -U postgres"]
  interval: 5s
  timeout: 5s
  retries: 5
```

This tells Docker to periodically check if PostgreSQL is ready to accept connections.

**app** — the FastAPI application, built from the Dockerfile:
```yaml
app:
  build: .
  ports:
    - "8000:8000"
  environment:
    DATABASE_URL: postgresql://postgres:postgres@db:5432/job_rag
    ASYNC_DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/job_rag
    OPENAI_API_KEY: ${OPENAI_API_KEY}
  depends_on:
    db:
      condition: service_healthy
```

Three important details:

1. **`DATABASE_URL` uses `db` not `localhost`** — inside Docker's network, services find each other by name. The `app` container reaches PostgreSQL at `db:5432`, not `localhost:5432`. The environment variables override the defaults in `config.py`.

2. **`depends_on: condition: service_healthy`** — the app won't start until PostgreSQL's healthcheck passes. Without this, the app would crash trying to connect to a database that isn't ready yet.

3. **`OPENAI_API_KEY: ${OPENAI_API_KEY}`** — reads the key from your host machine's environment (or `.env` file) and passes it into the container.

### Running it

```bash
cp .env.example .env          # Create .env and add your OpenAI key
docker compose up              # Build image + start both services
# Wait for "Starting API server..." message
open http://localhost:8000/docs   # Swagger UI
```

---

## CI/CD — Automated Quality Checks

### The problem

You push code to GitHub. Did you break anything? Are there lint errors? Type errors? Failing tests? You could check manually every time, but that's error-prone. CI (Continuous Integration) automates these checks on every push.

### GitHub Actions

GitHub Actions runs your checks on GitHub's servers every time you push code or open a pull request. The configuration lives in `.github/workflows/ci.yml`.

The workflow does three things:

**1. Lint with ruff** — checks for code style issues, unused imports, and common mistakes:
```bash
uv run ruff check src/ tests/
```

Ruff is extremely fast (written in Rust, checks the entire codebase in <1 second). It enforces rules defined in `pyproject.toml`: PEP 8 style (E), pyflakes errors (F), import sorting (I), and Python upgrade suggestions (UP).

**2. Type check with pyright** — checks that types are consistent:
```bash
uv run pyright src/
```

If a function says it returns `str` but actually returns `int`, pyright catches it. This prevents an entire category of runtime errors.

**3. Test with pytest** — runs all 48 unit tests:
```bash
uv run pytest -m "not eval"
```

The `-m "not eval"` flag skips the extraction accuracy tests (which need the eval data files and aren't part of the core test suite). All 48 tests are fully mocked — they don't need a database or an OpenAI API key to run.

### Caching

The workflow uses `astral-sh/setup-uv@v4` with `enable-cache: true` to cache downloaded packages between runs. This matters because `sentence-transformers` pulls in PyTorch, which is ~200MB. The first CI run downloads everything (~3-4 minutes). Subsequent runs hit the cache (~30 seconds).

### What triggers it

```yaml
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
```

Every push to `main` and every pull request targeting `main` triggers the workflow. If any step fails, the push gets a red ❌ on GitHub.

---

## Updated File Structure

```
job-rag/
├── data/
│   ├── postings/              23 markdown job posting files (input)
│   ├── profile.json           Your skills and preferences
│   └── eval/
│       ├── golden_queries.json          18 queries with ground truth answers
│       ├── extraction_ground_truth.json  Expected extraction for 5 postings
│       ├── extraction_results.json       Stored extraction outputs
│       └── results.json                  RAGAS evaluation scores
│
├── src/job_rag/
│   ├── config.py              Settings loaded from .env file
│   ├── logging.py             Structured logging setup
│   ├── models.py              Pydantic models (data shapes for validation)
│   ├── cli.py                 Terminal commands (ingest, embed, serve, etc.)
│   │
│   ├── db/
│   │   ├── engine.py          Database connection (sync + async)
│   │   └── models.py          Table definitions (ORM)
│   │
│   ├── extraction/
│   │   ├── prompt.py          Rules for the AI extraction
│   │   └── extractor.py       Calls GPT-4o-mini via Instructor
│   │
│   ├── services/
│   │   ├── ingestion.py       Read files → deduplicate → extract → store
│   │   ├── embedding.py       Convert text to vectors, store in DB
│   │   ├── retrieval.py       Search → rerank → generate answers
│   │   └── matching.py        Profile matching and gap analysis
│   │
│   └── api/
│       ├── app.py             FastAPI application setup
│       ├── deps.py            Database session for each request
│       └── routes.py          API endpoint definitions
│
├── tests/                     48 unit tests + 50 extraction accuracy tests
├── scripts/
│   ├── evaluate.py            RAGAS evaluation script
│   └── docker-entrypoint.sh   Docker startup (init → ingest → embed → serve)
│
├── .env.example               Template for environment variables
├── .github/workflows/ci.yml   GitHub Actions: lint, type check, test
├── Dockerfile                 Multi-stage build (builder → slim runtime)
├── docker-compose.yml         PostgreSQL + FastAPI app orchestration
├── pyproject.toml             Project config and dependencies
└── .env                       API keys and database URL (not in git)
```

---

## End-to-End Example (Updated)

### The Docker way (one command)

```
1. cp .env.example .env          Add your OpenAI API key
2. docker compose up              Start everything

   [db]  PostgreSQL ready ✓
   [app] Initializing database...
   [app] Ingesting postings... 23 ingested
   [app] Generating embeddings... 23 embedded
   [app] Starting API server...

3. Visit http://localhost:8000/docs    Interactive API docs
```

### The local development way

```
1. docker compose up db -d           Start just the database
2. uv sync                           Install Python dependencies
3. job-rag init-db                   Create tables
4. job-rag ingest --show-cost        Process 23 files → $0.025
5. job-rag embed --show-cost         Generate embeddings → $0.000168
6. job-rag serve --reload            Start API with hot-reload

Then:
   curl "http://localhost:8000/search?q=which+jobs+want+LangChain"
   curl "http://localhost:8000/gaps?seniority=senior"

7. uv run pytest                     Run all tests (48 pass)
8. uv run pytest -m eval             Run extraction accuracy tests (50 pass)
9. uv run python scripts/evaluate.py  Run RAGAS evaluation (~$0.10)
```

Total cost to process everything: **~$0.03** (3 cents).
Total cost to evaluate everything: **~$0.13** (13 cents).
