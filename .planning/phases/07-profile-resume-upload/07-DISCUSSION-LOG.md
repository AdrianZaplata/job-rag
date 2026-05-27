# Phase 7: Profile & Resume Upload - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in 07-CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-26
**Phase:** 07-profile-resume-upload
**Mode:** Auto-resolved (background session)
**Pattern lock:** Phase 4 (20/20 Recommended) + Phase 5 (23/23 Recommended) + Phase 6 (32/32 Recommended) + Auto-Mode bias "work without stopping for clarifying questions"
**Areas discussed:** Profile DB read-path flip, Upload endpoint contract, Extraction prompt + Instructor, Diff response shape, PATCH save semantics, Review panel UX, Langfuse observability, Error taxonomy, Plan structure preview

---

## A. Profile DB read-path flip (PROF-01)

**Question:** How should `load_profile()` change to read from the `user_profile` DB table instead of `data/profile.json`?

| Option | Description | Selected |
|--------|-------------|----------|
| Async DB query + drop `path` kwarg | Body-flip to `SELECT … WHERE user_id = :uid`; signature becomes `async def load_profile(session, *, user_id=None)`. Phase 1 D-07 explicitly built the kwarg as a forward hook. | ✓ (Recommended) |
| Keep sync, dual sync+async overload | `functools.singledispatch` to keep both call shapes | |
| Keep JSON file as fallback if DB empty | Hybrid read path | |

**Selected:** Async DB query, drop `path` kwarg. Captured in CONTEXT.md D-01, D-02.

**Question:** How should Adrian's existing profile.json content land in the `user_profile` table?

| Option | Description | Selected |
|--------|-------------|----------|
| Alembic data-migration with embedded dict literal | One-time idempotent UPSERT; embed JSON content as Python dict, NOT a runtime file read | ✓ (Recommended) |
| `init_db()` idempotent seed (every boot) | Same pattern as Phase 4 D-10 entra_oid update | |
| Manual `az postgres flexible-server execute` SQL after deploy | Out-of-band insert | |

**Selected:** Alembic data-migration. Captured in CONTEXT.md D-03.

**Question:** What happens to `data/profile.json` after the flip?

| Option | Description | Selected |
|--------|-------------|----------|
| Keep as reference snapshot / test fixture | Update `data/README.md` to record new role; backend tests can still use it | ✓ (Recommended) |
| Delete the file | Removes ambiguity | |
| Move to `tests/fixtures/profile-seed.json` | Relocate to test fixtures | |

**Selected:** Keep as reference snapshot. Captured in CONTEXT.md D-04.

---

## B. Upload endpoint contract (PROF-02)

**Question:** How should the 2 MB cap be enforced?

| Option | Description | Selected |
|--------|-------------|----------|
| Content-Length pre-body check + size-accumulating stream backstop | Reject 413 BEFORE body read per REQ literal wording; backstop catches chunked encoding | ✓ (Recommended) |
| Starlette built-in body cap | Silent; rejects AFTER full body received | |
| Nginx / Envoy / ACA-level cap | Infrastructure-side; doesn't deliver structured 413 | |

**Selected:** Content-Length pre-check + accumulator backstop. Captured in CONTEXT.md D-07.

**Question:** How should file type be validated?

| Option | Description | Selected |
|--------|-------------|----------|
| Extension + Content-Type intersection | Reject if EITHER fails whitelist | ✓ (Recommended) |
| Extension only | Bypassable with renamed file | |
| Magic-byte sniffing via `python-magic` | Adds libmagic native dep | |

**Selected:** Extension + Content-Type intersection. Captured in CONTEXT.md D-08.

**Question:** PDF and DOCX parser choice?

| Option | Description | Selected |
|--------|-------------|----------|
| pypdf 6.x + python-docx 1.x | REQ-PROF-02 literal | ✓ (Recommended — REQ-locked) |
| pdfplumber + python-docx | Better PDF text extraction (tables) | |
| pdfminer.six + mammoth | Pure-Python alternatives | |

**Selected:** pypdf 6.x + python-docx 1.x (REQ literal). Captured in CONTEXT.md D-09.

---

## C. Extraction prompt + Instructor (PROF-03)

**Question:** Resume extraction output schema?

| Option | Description | Selected |
|--------|-------------|----------|
| NEW `ResumeExtraction` model (sibling to UserSkillProfile) | Decouples extraction shape from canonical user state | ✓ (Recommended) |
| Reuse `UserSkillProfile` directly | Tighter coupling, fewer types | |
| Map to legacy CV schema | None exists; would be net-new anyway | |

**Selected:** New `ResumeExtraction` model. Captured in CONTEXT.md D-13.

**Question:** Soft-skill handling in the resume prompt?

| Option | Description | Selected |
|--------|-------------|----------|
| Reject in prompt (Phase 2 D-22 pattern) | Pre-extraction rejection, saves tokens | ✓ (Recommended) |
| Extract everything, filter in diff | More data, more LLM cost, noisy diff | |
| Extract everything, mark soft skills in diff | Lets user re-include if wanted | |

**Selected:** Reject in prompt (Phase 2 D-22 consistency). Captured in CONTEXT.md D-14.

**Question:** Instructor model + call pattern?

| Option | Description | Selected |
|--------|-------------|----------|
| GPT-4o-mini + `@retry(stop=3)` + sync `extract_resume` wrapped in `asyncio.to_thread` | Mirrors `extract_posting` exactly | ✓ (Recommended) |
| GPT-4o (full model) | 10× cost, no quality need for this task | |
| Direct async OpenAI client | Diverges from existing extraction pattern | |

**Selected:** GPT-4o-mini + `@retry` + `to_thread` wrap. Captured in CONTEXT.md D-15.

---

## D. Diff response shape (PROF-04)

**Question:** How should the diff be returned?

| Option | Description | Selected |
|--------|-------------|----------|
| Stateless single round-trip envelope (flat list with status tags) | Client owns review state; PATCH accepts final list | ✓ (Recommended) |
| Persisted `resume_upload_draft` table with two-step protocol | Server-side draft state, race-free | |
| Three separate lists (`added`, `removed`, `unchanged`) | UI re-concats and re-sorts anyway | |

**Selected:** Stateless flat list with status tags. Captured in CONTEXT.md D-17, D-18.

**Question:** Diff item ordering?

| Option | Description | Selected |
|--------|-------------|----------|
| Added → removed → unchanged, each alphabetical | Most-relevant-first | ✓ (Recommended) |
| Pure alphabetical mixed | Predictable but burys additions | |
| Extraction order | Brittle to prompt rephrasing | |

**Selected:** Added → removed → unchanged + alphabetical within section. Captured in CONTEXT.md D-19.

**Question:** What defines "unchanged"?

| Option | Description | Selected |
|--------|-------------|----------|
| `_normalize_skill()` equality (case+dash+underscore-normalized) | Reuses matching.py infra | ✓ (Recommended) |
| Alias-aware via `_ALIAS_INDEX` (populated in this phase) | Phase 5 D-Discretion deferred populating | |
| Exact string match | Misses "React" vs "react" | |

**Selected:** `_normalize_skill()` equality; `_ALIAS_GROUPS` stays empty per Phase 1 D-12. Captured in CONTEXT.md D-20.

---

## E. PATCH save semantics (PROF-06)

**Question:** PATCH save: replace or delta?

| Option | Description | Selected |
|--------|-------------|----------|
| Full replace on `skills` array; other fields optional | UI computes the final list | ✓ (Recommended) |
| Delta operations (add[], remove[]) | More HTTP-idiomatic but UX-clunky | |
| Full PUT replace of entire profile | Overrides every field unconditionally | |

**Selected:** Full replace on `skills`; other fields optional. Captured in CONTEXT.md D-21.

**Question:** Optimistic concurrency / version vector?

| Option | Description | Selected |
|--------|-------------|----------|
| None (single-user, no concurrent writes) | Simplest | ✓ (Recommended) |
| `If-Match` ETag from updated_at | Future-multi-user-ready | |
| Application-level lock | Heavy for v1 | |

**Selected:** None (single-user). Captured in CONTEXT.md D-23.

---

## F. Review panel UX (PROF-05)

**Question:** Layout for the diff review?

| Option | Description | Selected |
|--------|-------------|----------|
| Single-column status-pill chip list | Linear-dense, scan-friendly | ✓ (Recommended) |
| Side-by-side current vs extracted | Forces eye saccades for 80 items | |
| Three-section grouping (Added / Removed / Unchanged headers) | Pushes Added off-screen | |

**Selected:** Single-column status-pill. Captured in CONTEXT.md D-24.

**Question:** Default tick states?

| Option | Description | Selected |
|--------|-------------|----------|
| Added✓, removed☐, unchanged✓ | "Accept extraction" is path of least resistance | ✓ (Recommended) |
| Added☐, removed☐, unchanged✓ | Conservative; user opts in to additions | |
| All✓ | Save = restore-current-plus-additions | |

**Selected:** Added✓, removed☐, unchanged✓. Captured in CONTEXT.md D-25.

**Question:** Inline name editing scope?

| Option | Description | Selected |
|--------|-------------|----------|
| Edit on "added" chips only via Pencil icon | PROF-05 literal | ✓ (Recommended) |
| Edit on all chips | Allows retroactive canonical renames | |
| No edit, accept-as-is only | Loses the "edit before save" UX wording | |

**Selected:** Edit on "added" chips only. Captured in CONTEXT.md D-26.

**Question:** Route structure?

| Option | Description | Selected |
|--------|-------------|----------|
| Single `/profile` route with idle/reviewing state machine | One route, no deep-link issue | ✓ (Recommended) |
| Nested route `/profile/review` | Refresh loses diff data | |
| Modal Dialog on `/profile` | Cramps the review panel | |

**Selected:** Single route with state machine. Captured in CONTEXT.md D-28.

**Question:** Component-tree organization?

| Option | Description | Selected |
|--------|-------------|----------|
| `components/profile/` feature folder (mirror Phase 5/6 pattern) | Consistent | ✓ (Recommended) |
| Inline components in `routes/Profile.tsx` | Single file gets bloated | |
| Split across `components/` and `features/` | Fragmenting | |

**Selected:** `components/profile/` feature folder. Captured in CONTEXT.md D-29.

**Question:** Upload affordance: file input or dropzone library?

| Option | Description | Selected |
|--------|-------------|----------|
| shadcn `Input type="file"` + drag-drop hint | No third-party lib | ✓ (Recommended) |
| `react-dropzone` library | ~6 KB gzipped, more features than needed | |
| Custom drag-drop with no file input | Less native | |

**Selected:** shadcn Input + drag-drop hint. Captured in CONTEXT.md D-30.

---

## G. Langfuse observability (PROF-06 fifth criterion)

**Question:** Trace structure?

| Option | Description | Selected |
|--------|-------------|----------|
| Single trace per upload, 4 spans + extraction_id correlation token | REQ-PROF-06 literal | ✓ (Recommended) |
| Separate traces per HTTP request | Loses upload→save correlation | |
| One span per route, child of a parent trace | Same outcome, more nesting | |

**Selected:** Single trace, 4 spans, extraction_id correlation. Captured in CONTEXT.md D-32.

**Question:** PII policy for raw resume text?

| Option | Description | Selected |
|--------|-------------|----------|
| Never trace raw text; metadata + structured fields only | Safer if traces are shared | ✓ (Recommended) |
| Trace everything (debug-friendly) | Resume contains name + contact + employer | |
| Trace text only in dev environment | Adds env-conditional code | |

**Selected:** Never trace raw text. Captured in CONTEXT.md D-33.

---

## H. Error taxonomy

**Question:** Error response shape?

| Option | Description | Selected |
|--------|-------------|----------|
| `HTTPException(status, detail={reason, message})` structured detail | Frontend maps `reason` → copy | ✓ (Recommended) |
| `HTTPException(status, detail=string)` plain message | Loses programmatic reason | |
| Custom error envelope `{error: {...}}` | Diverges from FastAPI convention | |

**Selected:** Structured detail dict. Captured in CONTEXT.md D-35.

**Question:** Test coverage?

| Option | Description | Selected |
|--------|-------------|----------|
| Happy path + 5 error paths + extraction prompt rejection rules | Mirror existing test coverage discipline | ✓ (Recommended) |
| Happy path only | Insufficient for error UX | |
| Exhaustive parametrized matrix | Diminishing returns | |

**Selected:** Happy + 5 error paths. Captured in CONTEXT.md D-36.

---

## Claude's Discretion (auto-resolved without explicit question; embedded in D-Discretion section of CONTEXT.md)

- pypdf / python-docx version pin
- DOCX text join separator strategy
- Drag-drop visual feedback
- Test fixture filenames
- Toast notifications via sonner
- File input `accept` attribute string
- Extraction summary copy
- Cold-start stepped status timing
- ProfileView idle layout
- TanStack Query keys + invalidation strategy
- Mutation hook ownership
- Route AuthGate wrapping (inherited from Phase 4)
- Manual save with no upload (not surfaced in v1)
- Backend route file placement
- Backend test file naming
- Pydantic response model placement
- Langfuse client factory reuse
- `extraction_id` correlation token semantics
- Migration filename convention
- OpenAPI snapshot + types.ts regen workflow

## Deferred Ideas

Tracked in CONTEXT.md `<deferred>` section. Highlights:

- Multi-resume history → v2
- Server-side resume blob storage → v2
- OCR for scanned PDFs → v2
- Multi-language resume support → v2
- Skill alias-aware diff → revisit if observed
- Editing roles/locations/salary in review panel → Phase 7.1 if needed
- Diff confidence scores → theater, deferred
- RAGAS-on-CI for resume extraction → Phase 8
- Cold-start mitigation via min-replicas=1 → Phase 8 portfolio polish (~€8/mo, out of budget)

## Reviewed Todos (not folded)

None — `gsd-tools todo match-phase 7` returned `todo_count: 0` (verified 2026-05-26).
