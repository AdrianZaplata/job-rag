---
phase: 07-profile-resume-upload
plan: 01
type: execute
wave: 0
depends_on: []
files_modified:
  - pyproject.toml
  - uv.lock
  - src/job_rag/config.py
  - tests/conftest.py
  - tests/test_profile.py
  - tests/test_resume_extractor.py
  - tests/test_observability.py
  - tests/test_alembic.py
  - tests/test_matching.py
  - tests/fixtures/sample-resume.pdf
  - tests/fixtures/sample-resume.docx
  - tests/fixtures/encrypted-sample.pdf
  - tests/fixtures/empty-text-sample.pdf
  - frontend/src/components/profile/.gitkeep
  - data/README.md
autonomous: true
requirements: [PROF-01, PROF-02, PROF-03, PROF-04, PROF-05, PROF-06]
requirements_addressed: [PROF-01, PROF-02, PROF-03, PROF-04, PROF-05, PROF-06]

must_haves:
  truths:
    - "pypdf>=6,<7 and python-docx>=1,<2 are present in pyproject.toml and uv.lock"
    - "settings.max_resume_size_bytes defaults to 2_000_000 and is overridable via env"
    - "Four synthetic resume fixture files exist under tests/fixtures/"
    - "Backend test scaffolds (test_profile.py, test_resume_extractor.py, test_alembic.py) exist and are importable"
    - "data/README.md documents data/profile.json as a reference snapshot, NOT a runtime read path"
    - "frontend/src/components/profile/ directory exists"
  artifacts:
    - path: "pyproject.toml"
      provides: "pypdf and python-docx dependency pins"
      contains: "pypdf>=6,<7"
    - path: "src/job_rag/config.py"
      provides: "max_resume_size_bytes Setting"
      contains: "max_resume_size_bytes"
    - path: "tests/conftest.py"
      provides: "Four resume byte fixtures"
      contains: "sample_resume_pdf"
    - path: "tests/fixtures/sample-resume.pdf"
      provides: "Synthetic valid PDF resume fixture"
    - path: "tests/fixtures/sample-resume.docx"
      provides: "Synthetic valid DOCX resume fixture"
    - path: "tests/fixtures/encrypted-sample.pdf"
      provides: "Synthetic encrypted PDF fixture"
    - path: "tests/fixtures/empty-text-sample.pdf"
      provides: "Synthetic image-only PDF fixture (text extract <100 chars)"
    - path: "data/README.md"
      provides: "Repurposes data/profile.json as reference snapshot"
      contains: "reference snapshot"
  key_links:
    - from: "pyproject.toml"
      to: "uv.lock"
      via: "uv lock"
      pattern: "pypdf.*6"
    - from: "tests/conftest.py"
      to: "tests/fixtures/sample-resume.{pdf,docx}"
      via: "open() bytes fixture"
      pattern: "sample_resume_pdf"
---

<objective>
Land the Wave-0 foundation for Phase 7 — every artifact that Plans 02-05 depend on but which sits outside their commit boundary: PDF/DOCX parser deps, the `max_resume_size_bytes` Setting, four synthetic test fixtures, byte fixtures in `conftest.py`, empty test-file scaffolds, the `data/README.md` repurposing doc, and the `frontend/src/components/profile/` directory. No production logic is written here; this plan establishes the scaffolding so downstream plans can run their tests against red→green cycles without yak-shaving infrastructure.

Purpose: per CONTEXT D-37, Wave-0 foundation amortises shared setup across the phase. Per VALIDATION wave-0 list (lines 95-107), 12 specific artifacts must exist before any other plan's tests can pass.
Output: 14 files committed (pyproject.toml, uv.lock, config.py, conftest.py, 4 test scaffolds, 4 fixture binaries, data/README.md, .gitkeep).
</objective>

<execution_context>
@$HOME/.claude/get-shit-done/workflows/execute-plan.md
@$HOME/.claude/get-shit-done/templates/summary.md
</execution_context>

<context>
@.planning/PROJECT.md
@.planning/ROADMAP.md
@.planning/STATE.md
@.planning/phases/07-profile-resume-upload/07-CONTEXT.md
@.planning/phases/07-profile-resume-upload/07-RESEARCH.md
@.planning/phases/07-profile-resume-upload/07-PATTERNS.md
@.planning/phases/07-profile-resume-upload/07-VALIDATION.md
@pyproject.toml
@src/job_rag/config.py
@tests/conftest.py

<interfaces>
<!-- Pattern: existing config.py Field declaration shape (config.py:51-53) -->
```python
# ge=1 guards against env-misconfig (0 or negative) that would silently break
# asyncio.wait_for and sse-starlette's ping kwarg downstream (D-15, D-25).
agent_timeout_seconds: int = Field(default=60, ge=1)
heartbeat_interval_seconds: int = Field(default=15, ge=1)
```

<!-- Pattern: existing fixture in conftest.py:20-24 -->
```python
@pytest.fixture
def sample_raw_text() -> str:
    path = "tests/fixtures/sample_posting.md"
    with open(path, encoding="utf-8") as f:
        return f.read()
```
</interfaces>
</context>

<threat_model>
## Trust Boundaries

| Boundary | Description |
|----------|-------------|
| developer machine → committed binaries | Synthetic test fixtures must NOT contain Adrian's real PII; they are committed to a public-ready repo |

## STRIDE Threat Register

| Threat ID | Category | Component | Disposition | Mitigation Plan |
|-----------|----------|-----------|-------------|-----------------|
| T-07-02 | Denial of Service | upload endpoint (preparation) | mitigate | `max_resume_size_bytes = 2_000_000` Setting added; Plan 04 wires the middleware that enforces it (validated by 07-04-01, 07-04-02) |
| T-07-foundation-PII | Information disclosure | tests/fixtures/sample-resume.* | mitigate | Fixtures MUST be synthetic — generated with mock skills and a "TEST FIXTURE" watermark (D-Discretion); NO use of Adrian's real resume content |
</threat_model>

<tasks>

<task type="auto" id="07-01-01">
  <name>Task 1: Add pypdf + python-docx deps + max_resume_size_bytes Setting + data/README.md</name>
  <files>pyproject.toml, uv.lock, src/job_rag/config.py, data/README.md</files>
  <read_first>
    - pyproject.toml (the existing [project] dependencies block — preserve pin style)
    - src/job_rag/config.py (canonical analog: `agent_timeout_seconds: int = Field(default=60, ge=1)` at lines 51-53 — match the Field(default=..., ge=N) pattern with explanatory comment)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §9 (config.py pattern lines 454-473)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §27 (data/README.md content lines 1073-1086)
    - .planning/phases/07-profile-resume-upload/07-RESEARCH.md §"Why embed the dict literal" lines 268-270
  </read_first>
  <action>
1. Edit `pyproject.toml`: in the `[project] dependencies` array, add two entries preserving the existing comma+newline+indent style:
   - `"pypdf>=6,<7",`  (per D-09 + REQ-PROF-02 literal "pypdf 6.x")
   - `"python-docx>=1,<2",`  (per D-09 + REQ-PROF-02 literal "python-docx 1.x")

   Insert alphabetically among the existing deps (between `pgvector` and existing `p*` entries, or at the natural alphabetical slot).

2. Run `uv lock` from the repo root to update `uv.lock`. Do NOT hand-edit `uv.lock`.

3. Edit `src/job_rag/config.py`: in the `Settings` class, near the `agent_timeout_seconds` / `heartbeat_interval_seconds` block (around lines 51-53), add per D-07:

   ```python
   # Phase 7 D-07: 2 MB cap on resume uploads. Enforced by the ASGI middleware
   # in api/middleware.py BEFORE the body is materialized into memory (REQ-PROF-02
   # literal "rejected with 413 before the body is fully read").
   max_resume_size_bytes: int = Field(default=2_000_000, ge=1)
   ```

   Use `Field` (already imported in config.py for the existing pattern). The `ge=1` guard mirrors `agent_timeout_seconds` (config.py:51-53).

4. Create `data/README.md` (NEW, ~10 lines) per D-04 + PATTERNS §27:

   ```markdown
   # data/

   Local-only reference data. NOT a runtime read path.

   - `profile.json` — reference snapshot of Adrian's seed `user_profile` row. The canonical runtime
     source is the `user_profile` DB row, seeded by `alembic/versions/0006_seed_user_profile.py` from
     an embedded dict literal (PROF-01 / Phase 7 D-03, D-04). Update flow when seed contents change:
     edit `profile.json` + regenerate the dict literal in the migration in lockstep.
   - `postings/` — markdown ingestion corpus; consumed by `job-rag ingest` (development only).
   ```

5. Verify environment with `uv run python -c "from job_rag.config import settings; assert settings.max_resume_size_bytes == 2_000_000, settings.max_resume_size_bytes; print('OK')"`.
  </action>
  <verify>
    <automated>grep -E 'pypdf>=6,<7' pyproject.toml && grep -E 'python-docx>=1,<2' pyproject.toml && grep 'max_resume_size_bytes' src/job_rag/config.py && grep -q 'reference snapshot' data/README.md && uv run python -c "from job_rag.config import settings; assert settings.max_resume_size_bytes == 2_000_000"</automated>
  </verify>
  <acceptance_criteria>
    - `grep -E "pypdf|python-docx" pyproject.toml` returns both lines (VALIDATION 07-01-01)
    - `uv run python -c "from job_rag.config import settings; assert settings.max_resume_size_bytes == 2_000_000"` exits 0 (VALIDATION 07-01-02)
    - `grep -q "reference snapshot" data/README.md` returns 0
    - `uv.lock` updated (modification timestamp newer than pyproject.toml's previous mtime; verified by `git status` showing both as modified together)
  </acceptance_criteria>
  <done>
    - pyproject.toml + uv.lock + config.py + data/README.md committed in one logical unit
    - `uv run pyright src/` passes (no type errors from new Setting)
  </done>
</task>

<task type="auto" id="07-01-02">
  <name>Task 2: Generate synthetic resume fixtures + commit to tests/fixtures/</name>
  <files>tests/fixtures/sample-resume.pdf, tests/fixtures/sample-resume.docx, tests/fixtures/encrypted-sample.pdf, tests/fixtures/empty-text-sample.pdf, scripts/generate_resume_fixtures.py (optional helper)</files>
  <read_first>
    - .planning/phases/07-profile-resume-upload/07-CONTEXT.md §Claude's Discretion (line 288 — fixtures committed, synthetic only)
    - .planning/phases/07-profile-resume-upload/07-VALIDATION.md (Wave-0 Requirements lines 97-100)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §14 (fixture byte-return pattern lines 631-650)
    - tests/fixtures/sample_posting.md (the existing sample fixture — confirms the directory exists and style of synthetic content)
  </read_first>
  <action>
Generate FOUR synthetic resume fixtures. NO use of Adrian's real resume content (T-07-foundation-PII threat). All fixtures must contain a "TEST FIXTURE — synthetic data" watermark in their text content.

**Recommended approach:** Use the just-added `pypdf` + `python-docx` deps to author them via a one-shot script `scripts/generate_resume_fixtures.py` (commit this script so the fixtures are regeneratable). The script is NOT production code; it lives outside `src/`.

Fixture 1 — `tests/fixtures/sample-resume.pdf` (~10-50 KB synthetic PDF):
- Use `pypdf` or `reportlab` (if available) OR generate via `python-docx` and convert — simplest path is to use `pypdf.PdfWriter` to assemble a valid PDF with a text page containing:
  ```
  TEST FIXTURE — synthetic data
  Jane Doe — AI Engineer
  Skills: Python, FastAPI, PostgreSQL, pgvector, Docker, Azure Container Apps
  Languages: English, German
  Target roles: AI Engineer, ML Engineer
  Min salary EUR: 70000
  Years experience: 5
  ```
- Must produce ≥100 non-whitespace chars (passes D-10 minimum) and extract cleanly via `pypdf.PdfReader.pages[i].extract_text()`.

Fixture 2 — `tests/fixtures/sample-resume.docx`:
- Use `python-docx`:
  ```python
  from docx import Document
  doc = Document()
  doc.add_heading("TEST FIXTURE — synthetic data", level=1)
  doc.add_paragraph("Jane Doe — AI Engineer")
  doc.add_paragraph("Skills: Python, FastAPI, PostgreSQL, pgvector, Docker, Azure Container Apps")
  doc.add_paragraph("Languages: English, German")
  doc.add_paragraph("Target roles: AI Engineer, ML Engineer")
  table = doc.add_table(rows=2, cols=2)
  table.rows[0].cells[0].text = "Years"
  table.rows[0].cells[1].text = "5"
  table.rows[1].cells[0].text = "Min salary (EUR)"
  table.rows[1].cells[1].text = "70000"
  doc.save("tests/fixtures/sample-resume.docx")
  ```

Fixture 3 — `tests/fixtures/encrypted-sample.pdf` (encrypted PDF):
- Use `pypdf.PdfWriter.encrypt(user_password="test")`:
  ```python
  from pypdf import PdfWriter
  writer = PdfWriter()
  writer.add_blank_page(width=72, height=72)
  writer.encrypt(user_password="test", owner_password="test")
  with open("tests/fixtures/encrypted-sample.pdf", "wb") as f:
      writer.write(f)
  ```
- When read with `pypdf.PdfReader(path)`, `reader.is_encrypted` MUST be True (per RESEARCH §1 lines 28).

Fixture 4 — `tests/fixtures/empty-text-sample.pdf` (image-only / extracts <100 chars):
- Easiest synthetic: a PDF with a single blank page (no text content) OR with only an image. `pypdf.PdfWriter().add_blank_page()` writes a page that `.extract_text()` returns `""` for.
  ```python
  from pypdf import PdfWriter
  writer = PdfWriter()
  writer.add_blank_page(width=595, height=842)
  with open("tests/fixtures/empty-text-sample.pdf", "wb") as f:
      writer.write(f)
  ```
- Reading + concatenating all `page.extract_text()` results MUST yield `len(text.strip()) < 100` (D-10 threshold).

Commit `scripts/generate_resume_fixtures.py` AND the four generated `.pdf`/`.docx` binaries. The fixtures are version-controlled binaries — `.gitignore` rules in this repo allow `tests/fixtures/*` (verify with `git check-ignore tests/fixtures/sample-resume.pdf`; should NOT be ignored).
  </action>
  <verify>
    <automated>test -f tests/fixtures/sample-resume.pdf -a -f tests/fixtures/sample-resume.docx -a -f tests/fixtures/encrypted-sample.pdf -a -f tests/fixtures/empty-text-sample.pdf && uv run python -c "
import pypdf, docx
r1 = pypdf.PdfReader('tests/fixtures/sample-resume.pdf')
assert not r1.is_encrypted
text = '\n'.join(p.extract_text() or '' for p in r1.pages)
assert len(text.strip()) >= 100, f'sample PDF text too short: {len(text.strip())}'
d = docx.Document('tests/fixtures/sample-resume.docx')
assert any('TEST FIXTURE' in p.text for p in d.paragraphs)
r3 = pypdf.PdfReader('tests/fixtures/encrypted-sample.pdf')
assert r3.is_encrypted, 'encrypted fixture is NOT encrypted'
r4 = pypdf.PdfReader('tests/fixtures/empty-text-sample.pdf')
empty_text = '\n'.join(p.extract_text() or '' for p in r4.pages)
assert len(empty_text.strip()) < 100, f'empty-text fixture extracts too much: {len(empty_text.strip())}'
print('OK')
"</automated>
  </verify>
  <acceptance_criteria>
    - `test -f tests/fixtures/sample-resume.pdf -a -f tests/fixtures/sample-resume.docx -a -f tests/fixtures/encrypted-sample.pdf -a -f tests/fixtures/empty-text-sample.pdf` exits 0 (VALIDATION 07-01-03)
    - `pypdf.PdfReader("tests/fixtures/sample-resume.pdf")` is NOT encrypted, extracts ≥100 chars
    - `pypdf.PdfReader("tests/fixtures/encrypted-sample.pdf").is_encrypted is True`
    - `pypdf.PdfReader("tests/fixtures/empty-text-sample.pdf")` extracts <100 chars total
    - `python-docx` opens `sample-resume.docx` and yields a paragraph containing "TEST FIXTURE"
    - All four fixtures contain "TEST FIXTURE" or "synthetic data" watermark visible to a reader (PII threat mitigation T-07-foundation-PII)
  </acceptance_criteria>
  <done>
    - 4 fixture binaries + scripts/generate_resume_fixtures.py committed
    - Verification command above exits 0
  </done>
</task>

<task type="auto" id="07-01-03">
  <name>Task 3: Add conftest fixtures + test-file scaffolds + frontend profile/ dir</name>
  <files>tests/conftest.py, tests/test_profile.py, tests/test_resume_extractor.py, tests/test_observability.py, tests/test_alembic.py, tests/test_matching.py, frontend/src/components/profile/.gitkeep</files>
  <read_first>
    - tests/conftest.py (analog: `sample_raw_text` fixture at lines 20-24 — file-bytes/string fixture shape)
    - tests/test_matching.py (existing — Phase 7 will APPEND `test_load_profile_*` tests; do not overwrite)
    - tests/test_observability.py (verify if file exists; if it does, APPEND mode; if not, create with module docstring)
    - .planning/phases/07-profile-resume-upload/07-PATTERNS.md §14 (conftest fixture pattern lines 616-651)
    - .planning/phases/07-profile-resume-upload/07-VALIDATION.md Wave-0 Requirements (lines 95-107)
  </read_first>
  <action>
1. Append to `tests/conftest.py` (do NOT replace existing fixtures). Place these AFTER the existing `sample_raw_text` fixture per PATTERNS §14:

   ```python
   @pytest.fixture
   def sample_resume_pdf() -> bytes:
       with open("tests/fixtures/sample-resume.pdf", "rb") as f:
           return f.read()

   @pytest.fixture
   def sample_resume_docx() -> bytes:
       with open("tests/fixtures/sample-resume.docx", "rb") as f:
           return f.read()

   @pytest.fixture
   def encrypted_resume_pdf() -> bytes:
       with open("tests/fixtures/encrypted-sample.pdf", "rb") as f:
           return f.read()

   @pytest.fixture
   def empty_text_resume_pdf() -> bytes:
       with open("tests/fixtures/empty-text-sample.pdf", "rb") as f:
           return f.read()
   ```

2. Create `tests/test_profile.py` (NEW, empty scaffold). Module docstring only; tests filled by Plans 02 + 04:

   ```python
   """Tests for the Phase 7 profile feature (PROF-01..06).

   Coverage filled by:
   - Plan 02 (07-02-*): load_profile DB read path + seed migration round-trip
   - Plan 04 (07-04-*): upload route 413/415/422 + diff helper + PATCH semantics
   """
   ```

3. Create `tests/test_resume_extractor.py` (NEW, empty scaffold). Module docstring only:

   ```python
   """Tests for src/job_rag/extraction/resume_extractor.py (PROF-03).

   Coverage filled by Plan 03 (07-03-*): structured-output return type,
   tenacity retry behavior, prompt rejection rules.
   """
   ```

4. Handle `tests/test_observability.py`:
   - Check if file exists: `test -f tests/test_observability.py`.
   - If exists: APPEND a section header comment `# Phase 7: resume_upload trace tests (Plan 04)`. Do NOT modify existing tests.
   - If not: create with module docstring `"""Tests for src/job_rag/observability.py. Phase 7 adds resume_upload trace coverage in Plan 04."""`.

5. Create `tests/test_alembic.py` (or append if it exists):
   - If exists: skip — Plan 02 appends.
   - If not: create with module docstring `"""Tests for alembic migrations. Phase 7 adds 0006_seed_user_profile round-trip coverage in Plan 02."""`.

6. Confirm `tests/test_matching.py` exists (it does — per VALIDATION 07-02-01 it's the target file for `test_load_profile_*` tests). Do NOT modify content; just verify file presence so Plan 02 knows where to add tests.

7. Create directory `frontend/src/components/profile/` and place a `.gitkeep` (empty file) so the directory is committed. Plan 05 fills it.

8. Run `uv run pytest --collect-only tests/test_profile.py tests/test_resume_extractor.py tests/test_alembic.py tests/test_observability.py 2>&1 | head -30` to confirm pytest can import the new scaffolds without error.

9. Run `uv run pytest tests/conftest.py 2>&1 | head -20` — pytest will report "0 tests collected" but MUST NOT error on the new fixtures.

10. Smoke-test the byte fixtures with a one-off:
    ```bash
    uv run python -c "
    import io, pypdf
    with open('tests/fixtures/sample-resume.pdf','rb') as f:
        data = f.read()
    assert len(data) > 100, 'fixture too small'
    r = pypdf.PdfReader(io.BytesIO(data))
    print('pdf pages:', len(r.pages), 'OK')
    "
    ```
  </action>
  <verify>
    <automated>test -f tests/test_profile.py -a -f tests/test_resume_extractor.py -a -f tests/test_observability.py -a -d frontend/src/components/profile && grep -q 'sample_resume_pdf' tests/conftest.py && grep -q 'sample_resume_docx' tests/conftest.py && grep -q 'encrypted_resume_pdf' tests/conftest.py && grep -q 'empty_text_resume_pdf' tests/conftest.py && uv run pytest --collect-only tests/test_profile.py tests/test_resume_extractor.py 2>&1 | grep -E '(no tests ran|collected 0)' && echo OK</automated>
  </verify>
  <acceptance_criteria>
    - All four new fixtures (`sample_resume_pdf`, `sample_resume_docx`, `encrypted_resume_pdf`, `empty_text_resume_pdf`) are grep-able in `tests/conftest.py`
    - `tests/test_profile.py`, `tests/test_resume_extractor.py` exist with module docstrings (pytest can `--collect-only` without ImportError)
    - `tests/test_observability.py` exists (either pre-existing or newly created)
    - `tests/test_alembic.py` exists OR is queued for Plan 02 creation (record decision in plan summary)
    - `frontend/src/components/profile/` directory exists (`test -d frontend/src/components/profile`)
    - `uv run pytest --collect-only tests/conftest.py tests/test_profile.py tests/test_resume_extractor.py` exits 0 with no errors (warnings OK)
  </acceptance_criteria>
  <done>
    - 4 new conftest fixtures + 4 test scaffolds + 1 frontend dir committed
    - pytest --collect-only against the new files exits 0
  </done>
</task>

</tasks>

<verification>
After all three tasks land, run from repo root:

```bash
# Static checks
grep -E 'pypdf>=6,<7' pyproject.toml
grep -E 'python-docx>=1,<2' pyproject.toml
grep 'max_resume_size_bytes' src/job_rag/config.py
grep -q 'reference snapshot' data/README.md
test -d frontend/src/components/profile

# Fixture sanity
test -f tests/fixtures/sample-resume.pdf
test -f tests/fixtures/sample-resume.docx
test -f tests/fixtures/encrypted-sample.pdf
test -f tests/fixtures/empty-text-sample.pdf

# Test import + collection
uv run pytest --collect-only tests/test_profile.py tests/test_resume_extractor.py tests/test_alembic.py
uv run pyright src/ | tail -5

# Setting resolution
uv run python -c "from job_rag.config import settings; assert settings.max_resume_size_bytes == 2_000_000"
```

All commands must exit 0.
</verification>

<success_criteria>
- Wave-0 Requirements checklist (VALIDATION lines 95-107) is fully ticked
- No downstream plan can blame "missing fixture" or "missing dep" for a red test
- `uv lock` clean (no resolution conflict)
- `pyright src/` exits 0
</success_criteria>

<output>
After completion, create `.planning/phases/07-profile-resume-upload/07-01-SUMMARY.md` capturing:
- Pinned `uv.lock` versions for pypdf + python-docx
- File sizes of the 4 generated fixtures
- Whether `tests/test_alembic.py` was newly created or appended
- Any deviations from the Wave-0 list with reason
</output>
