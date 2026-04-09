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
