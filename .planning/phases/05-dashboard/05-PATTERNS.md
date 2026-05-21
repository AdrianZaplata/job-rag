# Phase 5: Dashboard — Pattern Map

**Mapped:** 2026-05-22
**Files analyzed:** 24 (10 backend incl. tests + 14 frontend incl. tests + codegen + package.json)
**Analogs found:** 21 / 24 (3 net-new — recharts BarChart, shadcn primitives, codegen artifacts have RESEARCH.md references rather than codebase analogs)

---

## File Classification

| Target File | Role | Data Flow | Closest Analog | Match Quality |
|---|---|---|---|---|
| `src/job_rag/services/analytics.py` | backend service module | request-response (CRUD aggregate) | `src/job_rag/services/retrieval.py` lines 54-99 + `src/job_rag/services/matching.py` lines 124-157 | exact (role-match; same async SQLAlchemy + same filter mutation pattern) |
| `src/job_rag/api/dashboard.py` | backend Pydantic response-model module | request-response (schema) | `src/job_rag/api/sse.py` lines 1-122 | exact (API-layer Pydantic-only module sibling to routes/auth/deps) |
| `src/job_rag/api/routes.py` (MODIFIED) | FastAPI route handlers — append 3 endpoints | request-response | self (lines 153-199 — `/match` and `/gaps`) | exact (same file; same handler shape) |
| `tests/test_analytics.py` | pytest-asyncio unit tests | n/a | `tests/test_matching.py` lines 1-167 | exact (sibling test module; same class layout) |
| `tests/test_api.py` (MODIFIED) | pytest-asyncio endpoint integration tests | n/a | self (`TestMatchEndpoint` lines 116-143 + `TestGapsEndpoint` lines 195-222) | exact |
| `tests/conftest.py` (MODIFIED) | shared pytest fixtures | n/a | self (lines 26-97 `sample_posting` fixture) | exact |
| `frontend/src/routes/Dashboard.tsx` | top-level route page (replaces stub) | composition | `frontend/src/routes/AccessDenied.tsx` lines 38-112 + `frontend/src/components/AppShell.tsx` lines 46-92 | partial (no existing 3-up-grid page; AccessDenied gives Card composition shape) |
| `frontend/src/components/dashboard/DashboardFilters.tsx` | filter bar component | UI-state-to-URL bridge | `frontend/src/components/AppShell.tsx` lines 60-83 (DropdownMenu invocation) | partial (DropdownMenu only — `ToggleGroup` is net-new shadcn install) |
| `frontend/src/components/dashboard/TopSkillsCard.tsx` | React widget component | request-response via useQuery | `frontend/src/routes/AccessDenied.tsx` lines 79-111 (Card scaffold) + `frontend/src/test/queryClient.test.tsx` lines 9-16 (useQuery shape) | partial (no existing Card+useQuery composition — UI-SPEC §5 is the canonical reference) |
| `frontend/src/components/dashboard/SalaryBandsCard.tsx` | React widget component | request-response via useQuery | `frontend/src/routes/AccessDenied.tsx` lines 79-111 (Card scaffold) | **WEAK** (Recharts BarChart is net-new — UI-SPEC §7 + RESEARCH.md §Pattern 1 are canonical) |
| `frontend/src/components/dashboard/CvVsMarketCard.tsx` | React widget component | request-response via useQuery | `frontend/src/routes/AccessDenied.tsx` lines 79-111 (Card scaffold) | partial (Badge chip pattern net-new for this codebase — UI-SPEC §8 canonical) |
| `frontend/src/components/dashboard/useDashboardFilters.ts` | typed hook | URL-state | (none — net-new) | **WEAK** (no existing useSearchParams wrapper; RESEARCH.md §Pattern 5 + UI-SPEC §10 are canonical) |
| `frontend/src/components/dashboard/__tests__/TopSkillsCard.test.tsx` | Vitest + RTL component test | n/a | `frontend/src/test/shellPrimitives.test.tsx` lines 1-51 | exact (RTL pattern; render → assert byRole/byText) |
| `frontend/src/components/dashboard/__tests__/SalaryBandsCard.test.tsx` | Vitest + RTL component test | n/a | `frontend/src/test/shellPrimitives.test.tsx` lines 1-51 | exact |
| `frontend/src/components/dashboard/__tests__/CvVsMarketCard.test.tsx` | Vitest + RTL component test | n/a | `frontend/src/test/shellPrimitives.test.tsx` lines 1-51 | exact |
| `frontend/src/components/dashboard/__tests__/DashboardFilters.test.tsx` | Vitest + RTL component test | n/a | `frontend/src/test/AppShell.test.tsx` lines 1-26 | exact |
| `frontend/src/components/dashboard/useDashboardFilters.test.ts` | Vitest hook test with MemoryRouter | n/a | `frontend/src/test/AuthGate.test.tsx` lines 1-37 (MemoryRouter wiring) | partial (no existing `renderHook` test — MemoryRouter rendering pattern is the closest) |
| `frontend/src/components/ui/alert.tsx` | shadcn primitive (installed) | n/a | `frontend/src/components/ui/badge.tsx` lines 1-49 | exact (pure CVA + Tailwind, no Radix dep — like Badge) |
| `frontend/src/components/ui/chart.tsx` | shadcn primitive wrapping Recharts | n/a | (none — net-new) | **WEAK** (no chart wrapper in codebase; RESEARCH.md §Standard Stack + shadcn `chart` docs are canonical) |
| `frontend/src/components/ui/toggle-group.tsx` | shadcn primitive on radix-ui | n/a | `frontend/src/components/ui/dropdown-menu.tsx` lines 1-50 (radix-ui import shape) | partial (radix-ui import shape only; ToggleGroup itself is net-new) |
| `frontend/src/api/jobs.ts` (MODIFIED) | typed API service module | request-response | `frontend/src/api/authedFetch.ts` lines 54-82 (authedFetch caller) + `frontend/src/api/health.ts` lines 6-11 (typed fetch fn shape) | exact (jobs.ts is a stub; health.ts provides the shape) |
| `frontend/src/api/types.ts` (REGENERATED) | codegen output | n/a | (regenerated via `npm run codegen`) | n/a — not hand-written |
| `frontend/openapi.snapshot.json` (REGENERATED) | OpenAPI snapshot | n/a | (regenerated via openapi-typescript workflow) | n/a — not hand-written |
| `frontend/package.json` (MODIFIED) | NPM manifest | n/a | self (existing 16-line deps block, lines 17-39) | exact (transitive only — shadcn `add chart toggle-group` mutates) |

---

## A. Backend (new + modified)

### A.1 `src/job_rag/services/analytics.py` — NEW (service module)

**Role:** Backend service module hosting 3 async analytical functions + shared private filter helper + module-level `EU_COUNTRY_CODES` literal.
**Data flow:** Request-response (CRUD aggregate via SQLAlchemy 2.x async).
**Analog:** `src/job_rag/services/retrieval.py` (for the async session + filter-mutation idiom) + `src/job_rag/services/matching.py` (for the `Counter`-based aggregation idiom). Both share the same module shape and target the same `JobPostingDB` / `JobRequirementDB` schema.

**Why closest:** Sibling file in the same `services/` package; `retrieval.py::search_postings` mutates `stmt` with optional filter clauses the same way Phase 5's `_apply_filters` will; `matching.py::aggregate_gaps` uses `Counter` exactly as Phase 5's `cv_match` top-3 missing aggregation will.

**Imports pattern** (from `retrieval.py` lines 1-15 + `matching.py` lines 1-12):

```python
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from job_rag.db.models import JobPostingDB, JobRequirementDB
from job_rag.logging import get_logger
from job_rag.services.matching import load_profile, match_posting

log = get_logger(__name__)
```

**Filter-mutation pattern** (from `retrieval.py` lines 80-87):

```python
if seniority:
    stmt = stmt.filter(JobPostingDB.seniority == seniority)
if remote:
    stmt = stmt.filter(JobPostingDB.remote_policy == remote)
if min_salary is not None:
    stmt = stmt.filter(
        (JobPostingDB.salary_max >= min_salary) | (JobPostingDB.salary_max.is_(None))
    )
```

**Counter aggregation pattern** (from `matching.py` lines 132-157):

```python
from collections import Counter

must_have_gaps: Counter[str] = Counter()
for posting in postings:
    for req in posting.requirements:
        if not _skill_matches(user_skills, req.skill):
            if req.required:
                must_have_gaps[req.skill] += 1

return {
    "must_have_gaps": [
        {"skill": skill, "count": count, "percentage": round(count / len(postings) * 100, 1)}
        for skill, count in must_have_gaps.most_common(20)
    ],
}
```

**Copy-edit anchors:**
- Function names: `top_skills`, `salary_bands`, `cv_match`, `_apply_filters`
- Module-level literal name: `EU_COUNTRY_CODES: frozenset[str]` (snapshot date in inline comment per RESEARCH §EU-27 ISO Snapshot)
- Return-type contracts: per D-01 / D-12; use Pydantic response models from `api/dashboard.py` (not `dict[str, Any]`) — see RESEARCH §"Pydantic Response Models"

**Pitfalls / do NOT copy:**
- Do NOT carry over `_embed_query` or `rerank` from retrieval.py — analytics doesn't touch vectors
- Do NOT copy `min_salary` filter clause — Phase 5 doesn't expose salary filter (deferred idea)
- Do NOT copy `dict[str, Any]` return type from matching.py — Phase 5 uses Pydantic response models per RESEARCH §"Pydantic Response Models"
- Do NOT inline `match_posting()` formula — import and reuse verbatim (D-10)
- `Counter.most_common(3)` cap (Phase 5) vs `most_common(20)` (matching.py aggregate_gaps) — different cap
- Use `case((cond, 1), else_=0)` positional-tuple SQLAlchemy 2.x form, NOT keyword `whens=` (RESEARCH §Pitfall 5)
- `func.percentile_cont(0.5)` ALWAYS chained with `.within_group(<sort_expr>.asc())` (RESEARCH §Pitfall 1)
- `selectinload(JobPostingDB.requirements)` mandatory in cv_match SQL pre-filter (RESEARCH §Pitfall 14; mirrors `/gaps` at routes.py:186)

---

### A.2 `src/job_rag/api/dashboard.py` — NEW (Pydantic response models)

**Role:** API-layer Pydantic-only module exposing response schemas + filter enums for OpenAPI → openapi-typescript codegen.
**Data flow:** Schema declaration (no I/O).
**Analog:** `src/job_rag/api/sse.py` lines 1-122 — the existing "API-specific Pydantic models live under api/" precedent (Phase 1 D-14).

**Why closest:** `api/sse.py` is THE existing API-Pydantic-only module — declares `TokenEvent`, `ToolStartEvent`, `ErrorEvent`, etc. as `BaseModel` subclasses with field descriptors, and exports a `TypeAdapter`-friendly union. Phase 5's `api/dashboard.py` plays the exact same role for analytical responses.

**Module-docstring + import pattern** (from `api/sse.py` lines 1-33):

```python
"""SSE event contract for /agent/stream.

Pydantic v2 discriminated union on the ``type`` field per D-14. Six event types:
...
"""
from typing import Literal

from pydantic import BaseModel, Field


class TokenEvent(BaseModel):
    """Incremental assistant text chunk."""

    type: Literal["token"]
    content: str = Field(description="Assistant text chunk")
```

**Copy-edit anchors:**
- Class names: `TopSkillItem`, `DashboardTopSkillsResponse`, `DashboardSalaryBandsResponse`, `MissingSkillItem`, `DashboardCvMatchResponse`, `CountryFilter`, `RemoteFilter`
- Default-value pattern: `currency: str = "EUR"` (Pydantic v2)
- Nullable percentile fields: `p25: int | None`, `p50: int | None`, `p75: int | None` (RESEARCH §Pitfall 2)
- Use `StrEnum` from `enum` (not `Enum`) per existing convention in `src/job_rag/models.py` line 1

**Pitfalls / do NOT copy:**
- Do NOT use a discriminated `Annotated[X | Y | Z, Field(discriminator="type")]` union — dashboard responses are independent schemas, NOT one polymorphic envelope like SSE events
- Do NOT add a `to_sse()`-style helper — these models flow back through plain FastAPI JSON serialization
- Do NOT colocate inside `src/job_rag/models.py` (domain models) — keep transport concerns in `api/` (RESEARCH §Open Question Q2)
- Reuse the EXISTING `Seniority` enum from `src/job_rag/models.py` line 76 for seniority filter — do NOT redeclare

---

### A.3 `src/job_rag/api/routes.py` — MODIFIED (append 3 handlers)

**Role:** FastAPI router; append 3 `@router.get` handlers below the `/agent` block (after line 209).
**Data flow:** Request-response.
**Analog:** Self — the existing `/match` (lines 153-175) and `/gaps` (lines 178-199) handlers. Same decorator stack, same `Session` alias, same `Annotated[uuid.UUID, Depends(get_current_user_id)]` shape.

**Why closest:** Identical handler shape; copy-paste-edit is the literal pattern.

**Decorator + handler signature pattern** (from `routes.py` lines 178-199):

```python
@router.get("/gaps", dependencies=[Depends(require_api_key), Depends(standard_limit)])
async def gaps(
    session: Session,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    seniority: str | None = None,
    remote: str | None = None,
) -> dict[str, Any]:
    """Aggregate skill gaps across all (or filtered) postings."""
    stmt = select(JobPostingDB).options(selectinload(JobPostingDB.requirements))
    if seniority:
        stmt = stmt.filter(JobPostingDB.seniority == seniority)
    if remote:
        stmt = stmt.filter(JobPostingDB.remote_policy == remote)

    result = await session.execute(stmt)
    postings = list(result.scalars().all())

    if not postings:
        raise HTTPException(status_code=404, detail="No postings found with given filters")

    profile = load_profile(user_id=user_id)
    return aggregate_gaps(profile, postings)
```

**Module-level alias to reuse** (from `routes.py` line 60):

```python
Session = Annotated[AsyncSession, Depends(get_session)]
```

**Copy-edit anchors:**
- Handler names: `top_skills_route`, `salary_bands_route`, `cv_vs_market_route`
- URL paths: `/dashboard/top-skills`, `/dashboard/salary-bands`, `/dashboard/cv-vs-market` (NOT `/match/{posting_id}` / `/gaps`)
- Add `tags=["dashboard"]` to each `@router.get(...)` (RESEARCH §Pitfall 16; Claude's Discretion in CONTEXT)
- Return-type annotation MUST be the Pydantic response model (`-> DashboardTopSkillsResponse:` etc.), NOT `dict[str, Any]` — drives openapi-typescript named schemas
- Use enum-typed `Query` defaults: `country: CountryFilter = CountryFilter.WW`, `remote: RemoteFilter = RemoteFilter.ANY`, `seniority: Seniority | None = None`
- Add `limit: int = Query(default=50, ge=1, le=200)` on top-skills only

**Pitfalls / do NOT copy:**
- Do NOT raise `HTTPException(404, ...)` on empty filter result — Phase 5 D-12 returns HTTP 200 with zero-state body (do this for top-skills, salary-bands, cv-vs-market). `/gaps` 404 is INCOMPATIBLE behaviour, deliberately
- Do NOT inline the SQL aggregation here — delegate to `analytics.top_skills/salary_bands/cv_match` per D-02
- Do NOT use `agent_limit` (10/min reserved for Phase 6 chat) — use `standard_limit` (30/min) like `/search`, `/match`, `/gaps`
- Do NOT add a new `Session` alias — reuse the existing one at line 60 (RESEARCH §Open Question Q7)
- Imports — add `from job_rag.api.dashboard import (CountryFilter, RemoteFilter, DashboardTopSkillsResponse, DashboardSalaryBandsResponse, DashboardCvMatchResponse)` + `from job_rag.services.analytics import top_skills, salary_bands, cv_match` to the existing import block (do NOT reorder existing imports)
- `Query` import: add `Query` to the existing `from fastapi import ...` line (line 25), NOT a new import line

---

## B. Tests — Backend

### B.1 `tests/test_analytics.py` — NEW

**Role:** pytest-asyncio unit tests for the 3 analytics functions + `_apply_filters` + `EU_COUNTRY_CODES`.
**Data flow:** Tests (in-memory fixtures).
**Analog:** `tests/test_matching.py` lines 1-167 — same async-service-module-with-classes layout, same MagicMock-based posting fixture pattern.

**Why closest:** Phase 5's `analytics.py` is the sibling service to `matching.py`; the test file mirrors the test pattern verbatim.

**Test class layout pattern** (from `test_matching.py` lines 1-89):

```python
import uuid
from unittest.mock import MagicMock

import pytest

from job_rag.models import RemotePolicy, UserSkill, UserSkillProfile
from job_rag.services.matching import (
    _normalize_skill,
    _skill_matches,
    aggregate_gaps,
    match_posting,
)


@pytest.fixture
def profile() -> UserSkillProfile:
    return UserSkillProfile(
        skills=[UserSkill(name="Python"), UserSkill(name="Docker")],
        ...
    )


def _make_posting(must_have: list[str], nice_to_have: list[str], ...) -> MagicMock:
    """Create a mock posting with requirements."""
    posting = MagicMock()
    posting.id = uuid.uuid4()
    ...
    return posting


class TestMatchPosting:
    def test_perfect_must_have_match(self, profile):
        ...
        assert result["score"] == 1.0
```

**Copy-edit anchors:**
- Test classes (UI-SPEC §"Wave 0 Gaps" verbatim): `TestTopSkills`, `TestSalaryBands`, `TestCvMatch`, `TestApplyFilters`, `TestEuCountrySetMembership`, `TestFilterEffects`
- Import path: `from job_rag.services.analytics import top_skills, salary_bands, cv_match, _apply_filters, EU_COUNTRY_CODES`
- Fixture pattern: extend `_make_posting` to accept country, seniority, salary_period, skill_category kwargs (Phase 5 needs more variety than the matching-test factory)
- Async tests: use `@pytest.mark.asyncio` decorator (see `test_api.py` line 15) since analytics functions are `async`

**Pitfalls / do NOT copy:**
- Do NOT reuse the global `profile` fixture from `test_matching.py` — Phase 5 needs control over the profile per cv-match test
- Do NOT rely on the dev DB's 98 postings — RESEARCH §"Test Data Strategy" mandates in-memory fixtures only (reproducibility)
- Async session fixtures: use `AsyncMock` for `session.execute` mocks (see `test_api.py` line 19); MagicMock + plain `_make_posting` is fine for in-memory analytics functions if they accept a session-typed argument but never actually hit DB internals — alternatively use the `dashboard_postings_factory` (see B.3) for end-to-end SQL verification
- The `TestFilterEffects::test_country_filter_changes_results` test (per UI-SPEC §Validation Architecture) MUST exercise all 4 country values (PL/DE/EU/WW) and assert distinct numeric outputs — this is the DASH-04 success-criterion canary

---

### B.2 `tests/test_api.py` — MODIFIED (append `TestDashboardEndpoints`)

**Role:** Integration tests for the 3 new endpoints.
**Data flow:** Tests (FastAPI TestClient + dependency overrides).
**Analog:** Self — `TestMatchEndpoint` (lines 116-143) + `TestGapsEndpoint` (lines 195-222).

**Why closest:** Same file; the existing 4-step pattern (mock session → override `get_session` → override `get_current_user_id` → assert status code + JSON shape) is the literal template.

**Dependency-override + assertion pattern** (from `test_api.py` lines 116-143):

```python
@pytest.mark.asyncio
class TestMatchEndpoint:
    async def test_match_not_found(self):
        from job_rag.api.auth import get_current_user_id
        from job_rag.api.deps import get_session
        from job_rag.config import settings

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_session():
            yield mock_session

        async def override_user():
            return settings.seeded_user_id

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user_id] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(f"/match/{uuid.uuid4()}")

        app.dependency_overrides.clear()

        assert response.status_code == 404
```

**Copy-edit anchors:**
- Test class name: `TestDashboardEndpoints` (one class for all 3 endpoints; cleaner than 3 separate classes)
- Endpoint paths: `/dashboard/top-skills`, `/dashboard/salary-bands`, `/dashboard/cv-vs-market`
- Tests to write (per UI-SPEC Validation Architecture): one happy-path-with-shape test per endpoint + one `test_country_filter_exercises_4_values` + one `test_top_skills_openapi_shape` (asserts named schema present)
- Mock pattern for analytics functions: `with patch("job_rag.api.routes.top_skills", new_callable=AsyncMock) as mock_top:` mirroring `test_search_no_generate` lines 73-75

**Pitfalls / do NOT copy:**
- Do NOT assert status 404 on empty filter — Phase 5 D-12 returns 200 with zero-state body
- Do NOT bypass `get_current_user_id` — every dashboard test MUST override `app.dependency_overrides[get_current_user_id] = override_user` (the auth gate test)
- Do NOT skip the `app.dependency_overrides.clear()` at end of each test — leaking overrides poisons later tests
- The OpenAPI shape assertion (`test_top_skills_openapi_shape`) should hit `/openapi.json` and assert `components.schemas.DashboardTopSkillsResponse` exists (proves the Pydantic response model became a named schema)

---

### B.3 `tests/conftest.py` — MODIFIED (add `dashboard_postings_factory`)

**Role:** Shared pytest fixture for cross-test posting variety (DE/PL/EU/WW × salary/no-salary × seniority × skill_category).
**Data flow:** Tests (in-memory fixture data).
**Analog:** Self — the existing `sample_posting` fixture (lines 26-97).

**Why closest:** Same file; the existing fixture demonstrates the `JobPosting` + `JobRequirement` Pydantic builder pattern Phase 5 needs to scale.

**Pydantic posting + requirement fixture pattern** (from `conftest.py` lines 26-97):

```python
@pytest.fixture
def sample_posting() -> JobPosting:
    return JobPosting(
        title="Senior AI Engineer",
        company="TestCorp",
        location=Location(country="DE", city="Berlin", region=None),
        remote_policy=RemotePolicy.HYBRID,
        salary_min=70000,
        salary_max=90000,
        salary_period=SalaryPeriod.YEAR,
        seniority=Seniority.SENIOR,
        requirements=[
            JobRequirement(
                skill="Python",
                skill_type=SkillType.LANGUAGE,
                skill_category=derive_skill_category(SkillType.LANGUAGE),
                required=True,
            ),
            ...
        ],
        ...
    )
```

**Copy-edit anchors:**
- Fixture name: `dashboard_postings_factory` (returns a `list[JobPostingDB]` ORM-shaped builder per UI-SPEC §"Wave 0 Gaps") — note `JobPostingDB` (ORM), not `JobPosting` (Pydantic) like the existing fixture
- Variety to seed (per RESEARCH §"Test Data Strategy"): 5 DE postings (3 with salary, 2 NULL), 3 PL, 2 region="EU"/country=NULL, 1 region="Worldwide", varied seniority + salary_period (year/month/hour) + skill_category (hard/soft)
- Import path additions: `from job_rag.db.models import JobPostingDB, JobRequirementDB` (the ORM models, not just Pydantic)

**Pitfalls / do NOT copy:**
- Do NOT reuse `sample_posting` (Pydantic shape) — `dashboard_postings_factory` must return `JobPostingDB` ORM rows (analytics queries operate on ORM)
- Including `salary_period='hour'` + `skill_category='soft'` rows IS required (RESEARCH §"Edge Cases to Cover Explicitly") — these test the exclusion filters
- Do NOT include UNKNOWN seniority in the default variety — leave that for explicit defensive tests (D-08)

---

## C. Frontend (new + modified)

### C.1 `frontend/src/routes/Dashboard.tsx` — REPLACES current `PhasePlaceholder` stub

**Role:** Top-level route page composing filter bar + 3-up grid of widget cards.
**Data flow:** Composition (no data fetching at this level — widgets self-fetch).
**Analog:** `frontend/src/routes/AccessDenied.tsx` lines 38-112 (Card composition shape) — closest in this codebase.

**Why closest:** AccessDenied is the only existing page with multi-section Card composition. The 3-up grid is net-new — UI-SPEC §3 is the canonical reference for the locked JSX skeleton.

**Page-container + composition pattern** (from `AccessDenied.tsx` lines 79-112):

```tsx
return (
  <Card className="max-w-2xl mx-auto mt-12 p-8">
    <CardHeader>
      <CardTitle className="text-2xl font-semibold">Access denied</CardTitle>
    </CardHeader>
    <CardContent>
      <p className="text-sm text-muted-foreground mb-8">...</p>
      <div role="region" aria-label="Your account ID" className="mb-8 p-4 bg-muted rounded">
        ...
      </div>
    </CardContent>
  </Card>
)
```

**Canonical Phase 5 page-container** (from UI-SPEC §3):

```tsx
export default function Dashboard() {
  return (
    <div className="mx-auto max-w-6xl p-6 space-y-6">
      <DashboardFilters />
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <TopSkillsCard />
        <SalaryBandsCard />
        <CvVsMarketCard />
      </div>
    </div>
  )
}
```

**Copy-edit anchors:**
- Export shape: the existing stub has `export function DashboardPage()` — Phase 5 keeps that NAME (App.tsx routes-table lazy-imports `DashboardPage`); MUST keep the named export `DashboardPage` to avoid a routing churn
- Container classes: `mx-auto max-w-6xl p-6 space-y-6` (locked in UI-SPEC §3)
- Grid classes: `grid grid-cols-1 md:grid-cols-3 gap-4` (locked in UI-SPEC §3 + CONTEXT D-18)
- Imports use `@/components/dashboard/...` alias (Phase 4 baseline)

**Pitfalls / do NOT copy:**
- Do NOT import `PhasePlaceholder` — Phase 5 replaces, doesn't wrap
- Do NOT add a hero / banner section above the filter bar (CONTEXT specifics: "No top-of-page summary banner")
- Do NOT lift TanStack Query usage into Dashboard.tsx — per-widget useQuery is the contract (D-01 + D-22)
- The widget components must NOT be imported via `index.ts` barrel — direct imports (`@/components/dashboard/TopSkillsCard`) keep tree-shaking sharp

---

### C.2 `frontend/src/components/dashboard/DashboardFilters.tsx` — NEW

**Role:** Filter bar component with 3 controls (country dropdown, seniority dropdown, remote ToggleGroup).
**Data flow:** UI-state bridge (URL ↔ `useDashboardFilters` hook).
**Analog:** `frontend/src/components/AppShell.tsx` lines 60-83 — the only existing `DropdownMenu` usage in this codebase.

**Why closest:** AppShell shows the canonical `DropdownMenu + Trigger + Content + Item` shape; Phase 5 extends with `DropdownMenuRadioGroup` + `DropdownMenuRadioItem` (already exported from `dropdown-menu.tsx` lines 116-157). The `ToggleGroup` is net-new (installed via `npx shadcn@latest add toggle-group`).

**DropdownMenu invocation pattern** (from `AppShell.tsx` lines 66-83):

```tsx
<DropdownMenu>
  <DropdownMenuTrigger asChild>
    <Button variant="ghost" size="icon" aria-label="Open account menu">
      <UserIcon className="h-4 w-4" />
    </Button>
  </DropdownMenuTrigger>
  <DropdownMenuContent align="end">
    <DropdownMenuItem
      variant="destructive"
      onSelect={(e) => { e.preventDefault(); signOut() }}
    >
      Sign out
    </DropdownMenuItem>
  </DropdownMenuContent>
</DropdownMenu>
```

**Canonical Phase 5 filter bar JSX skeleton:** UI-SPEC §4 lines 192-300 (full JSX) — the executor must follow that exactly, including the `aria-label` strings ("Dashboard filters", "Remote policy", "Any remote policy", etc.) per UI-SPEC §16 verbatim contract.

**Copy-edit anchors:**
- File location: `frontend/src/components/dashboard/DashboardFilters.tsx`
- Component name: `export function DashboardFilters()` (not default)
- Label maps (UI-SPEC §4 lines 208-221): `COUNTRY_LABEL`, `SENIORITY_LABEL`
- Filter values per CONTEXT D-07/D-08/D-09: country PL/DE/EU/WW, seniority junior/mid/senior/staff/lead (no `unknown`), remote any/remote/non_remote

**Pitfalls / do NOT copy:**
- Do NOT use `DropdownMenuItem` for country/seniority — use `DropdownMenuRadioGroup` + `DropdownMenuRadioItem` (radio semantics, single-select) per UI-SPEC §4
- Do NOT add a 5th country option ("All countries", Switzerland, etc.) — REQUIREMENTS DASH-04 is literal "Poland / Germany / EU / Worldwide" (CONTEXT specifics: "Filter values are LITERAL from REQUIREMENTS DASH-04")
- Do NOT add a "show soft skills" toggle to the filter bar — CONTEXT D-13 says backend accepts `?include_soft=true` but UI does NOT surface
- Do NOT use `useState` for filter state — read/write through `useDashboardFilters()` hook only (URL is the source of truth)
- Do NOT add a "remote=unknown" toggle item — D-09 collapses to any/remote/non_remote (the 3-state tri-toggle)

---

### C.3 `frontend/src/components/dashboard/TopSkillsCard.tsx` — NEW

**Role:** Card-shaped widget rendering top 8-10 hard skills as Tailwind-native horizontal bars + "Show more" Dialog trigger.
**Data flow:** Request-response via `useQuery(['dashboard', 'top-skills', filters])`.
**Analog (weak):** `frontend/src/routes/AccessDenied.tsx` lines 79-111 (Card scaffold) + `frontend/src/test/queryClient.test.tsx` lines 9-16 (useQuery shape).

**Why this is a WEAK analog:** No existing component composes `Card + useQuery + Skeleton + EmptyState + Alert`. The TopSkillsCard pattern is net-new for this codebase — the executor MUST follow UI-SPEC §5 (lines 340-530) precisely.

**Card scaffold pattern** (from `AccessDenied.tsx` lines 79-95):

```tsx
<Card className="max-w-2xl mx-auto mt-12 p-8">
  <CardHeader>
    <CardTitle className="text-2xl font-semibold">Access denied</CardTitle>
  </CardHeader>
  <CardContent>
    <p className="text-sm text-muted-foreground mb-8">
      Your account is not on the allowlist...
    </p>
  </CardContent>
</Card>
```

**useQuery shape pattern** (from `queryClient.test.tsx` lines 10-15):

```tsx
const { data } = useQuery({
  queryKey: ['probe'],
  queryFn: async () => 'ok',
  staleTime: Infinity,
})
```

**Canonical TopSkillsCard JSX:** UI-SPEC §5 lines 371-451 — the executor follows that as the source of truth.

**Copy-edit anchors:**
- Title: `<CardTitle className="text-sm font-medium">Top skills</CardTitle>` (UI-SPEC §16 verbatim)
- Container: `<Card className="flex flex-col">` + `<CardContent className="flex-1">` + `<CardFooter className="text-xs text-muted-foreground">` (UI-SPEC §12)
- useQuery: `queryKey: ['dashboard', 'top-skills', filters]`, `queryFn: ({ signal }) => topSkills(filters, signal)`, `staleTime: 5 * 60_000` (CONTEXT D-22)
- Constants: `const VISIBLE_ROWS = 10` (UI-SPEC §5 line 393)
- Empty state body: literal `No skills match these filters. Try widening the filter set.` (UI-SPEC §16)
- Error AlertTitle: `Couldn't load top skills` (UI-SPEC §16)
- Footer template: `{n} postings · {m} unique hard skills` with `n === 1` singular branch
- Bar formula: `widthPct = Math.round((total / leader.total) * 100)` (UI-SPEC §5 lines 499-505)

**Pitfalls / do NOT copy:**
- Do NOT import Recharts here — top-skills uses Tailwind-native bars only (CONTEXT D-14)
- Do NOT use `staleTime: Infinity` (test fixture) or `30_000` (Phase 4 default) — Phase 5 dashboard queries override to `5 * 60_000` (CONTEXT D-22)
- Do NOT wrap `filters` in `useMemo` — TanStack Query v5 deep-hashes the queryKey (RESEARCH §Pitfall 6)
- Do NOT render the CardFooter on error/pending state (UI-SPEC §11 "Footer rendering when no data" — only renders when `data` is truthy)
- "Show more" button MUST gate on `data.skills.length > VISIBLE_ROWS` — never render the Dialog trigger if ≤10 skills
- The bar must be a TWO-segment visual: outer `bg-foreground` (total width) with inner `bg-primary` (must-have proportion) — NOT a single bar (UI-SPEC §5 lines 477-491)

---

### C.4 `frontend/src/components/dashboard/SalaryBandsCard.tsx` — NEW

**Role:** Card-shaped widget rendering p25/p50/p75 as a Recharts `BarChart` (the ONE chart in v1).
**Data flow:** Request-response via `useQuery`.
**Analog (WEAK):** `frontend/src/routes/AccessDenied.tsx` lines 79-95 (Card scaffold only).

**Why this is a WEAK analog:** Net-new pattern — there is NO existing Recharts usage in the codebase, NO existing `ChartContainer` wrapping, and NO existing `BarChart` invocation. The canonical reference is **RESEARCH.md §"Standard Stack" + UI-SPEC §7 (lines 656-822)**.

**Canonical SalaryBandsCard JSX:** UI-SPEC §7 lines 687-787 — the executor follows that as the source of truth (Recharts `BarChart` + `<XAxis>` + `<Bar>` + `<LabelList>`).

**Recharts imports pattern (FROM UI-SPEC §7, lines 690-691):**

```tsx
import { Bar, BarChart, LabelList, XAxis } from 'recharts'

import {
  ChartContainer,
  type ChartConfig,
} from '@/components/ui/chart'
```

**ChartConfig + color-token pattern (FROM UI-SPEC §7, lines 711-713):**

```tsx
const chartConfig: ChartConfig = {
  value: { label: 'Salary', color: 'var(--chart-1)' },
}
```

**Copy-edit anchors:**
- Title: `<CardTitle className="text-sm font-medium">Salary bands</CardTitle>` (UI-SPEC §16)
- Format helper: `formatEur(value) → \`€${value.toLocaleString('en-US')}\`` (UI-SPEC §7 lines 715-717)
- Container height: `<ChartContainer ... className="h-48 w-full" ...>` (UI-SPEC §7 line 761)
- X-axis: `<XAxis dataKey="band" tickLine={false} axisLine={false} />` (UI-SPEC §7 line 765)
- Bar: `<Bar dataKey="value" fill="var(--chart-1)" radius={4}>` (UI-SPEC §7 line 766)
- LabelList: `<LabelList ... formatter={(v: number) => \`${formatEur(v)}/yr\`} className="fill-foreground text-xs" />` (UI-SPEC §7 lines 767-772)
- Footer: `{postings_with_salary} of {total_postings} postings had salary data` (UI-SPEC §16)

**Pitfalls / do NOT copy:**
- Do NOT render `<YAxis>` — UI-SPEC §7 explicitly: "Y-axis NOT rendered" (D-23 number-forward)
- Do NOT render `<Legend>` — UI-SPEC §7: "Legend NOT rendered"
- Do NOT render `<Tooltip>` — UI-SPEC §7: "Tooltip NOT rendered in v1"
- Do NOT animate bar grow — Recharts 3 `accessibilityLayer` prop does NOT animate; do NOT pass `isAnimationActive={true}` (UI-SPEC §14 anti-motion rules)
- Do NOT hardcode bar color (`#ffaa00` etc.) — MUST use CSS var `var(--chart-1)` so the theme toggle Just Works (CONTEXT Claude's Discretion)
- Recharts 3 + React 19 peer-dep WARNING: if `npm install` post-shadcn-add emits `react-is` warnings, add `"overrides": { "react-is": "$react" }` to package.json (RESEARCH §Pitfall 7)
- `accessibilityLayer` MUST be passed on `<BarChart>` (Recharts 3 a11y; UI-SPEC §15)

---

### C.5 `frontend/src/components/dashboard/CvVsMarketCard.tsx` — NEW

**Role:** Card-shaped widget rendering big-text match score + top-3 missing-skill chip list.
**Data flow:** Request-response via `useQuery`.
**Analog:** `frontend/src/routes/AccessDenied.tsx` lines 79-111 (Card scaffold + nested `<div role="region">` with mono content).

**Why closest:** AccessDenied is the closest example of "Card + hero-styled content + supporting text" in the codebase. The Badge chip list pattern is a fresh composition; UI-SPEC §8 is the canonical reference.

**Hero-styled pattern (analogy from AccessDenied):**

```tsx
<div role="region" aria-label="Your account ID" className="mb-8 p-4 bg-muted rounded">
  <p className="text-xs text-muted-foreground mb-2">Your account ID</p>
  <pre className="font-mono text-sm overflow-x-auto">
    <code>{oid}</code>
  </pre>
</div>
```

**Canonical CvVsMarketCard JSX:** UI-SPEC §8 lines 855-946 — the executor follows that as the source of truth.

**Copy-edit anchors:**
- Title: `<CardTitle className="text-sm font-medium">CV vs market</CardTitle>` (UI-SPEC §16)
- Hero: `<div className="text-5xl font-medium tabular-nums" aria-label={`Match score ${data.mean_score!.toFixed(2)}`}>{data.mean_score!.toFixed(2)}</div>` (UI-SPEC §8 lines 909-915 + UI-SPEC §12 typography)
- Hero label: `<div className="text-xs text-muted-foreground">Match score</div>`
- Thin baseline: `border-b border-border pb-4` (UI-SPEC §12 + CONTEXT D-23)
- Missing-skills label: `<div className="text-xs text-muted-foreground">Missing must-haves</div>`
- Chip JSX: `<Badge variant="secondary"><span className="font-mono">{m.skill}</span><span className="ml-1 text-muted-foreground tabular-nums">{Math.round(m.percentage)}%</span></Badge>` (UI-SPEC §8 lines 924-931)
- Empty heading: `No postings to compare` / body: `No postings to compare against — try adjusting filters.` (UI-SPEC §16)
- Footer: `Score across {n} postings`

**Pitfalls / do NOT copy:**
- Do NOT format score with `% suffix` — match scores are 0.00–1.00 decimals, not percentages (UI-SPEC §13)
- Do NOT use `text-2xl` for the hero (CONTEXT D-23 says "text-2xl") — UI-SPEC §12 overrides to `text-5xl` (48px) for THIS hero specifically
- Do NOT show ` % ` in the chip if `m.percentage` is null/undefined — backend always returns int/float per Pydantic contract
- Hide the entire "Missing must-haves" section when `top_missing_must_have.length === 0` (UI-SPEC §8 "Hidden chip-list behaviour")
- Use `Badge variant="secondary"` not `variant="default"` (UI-SPEC §8 chip contract)
- Optional `RadialBarChart` mentioned in CONTEXT D-14 ("if it adds visual interest at zero cost") — UI-SPEC §18 explicitly DECLINES it; do NOT add

---

### C.6 `frontend/src/components/dashboard/useDashboardFilters.ts` — NEW

**Role:** Typed wrapper around `useSearchParams` providing default elision write + type-guarded read.
**Data flow:** URL ↔ filters state bridge.
**Analog (WEAK):** None in codebase — no existing `useSearchParams` usage.

**Why this is a WEAK analog:** The codebase has no existing URL-state hook. RESEARCH §Pattern 5 (lines 554-620) + UI-SPEC §10 (lines 1160-1232) are the canonical references.

**Canonical hook implementation:** UI-SPEC §10 lines 1160-1232 — the executor follows that as the source of truth.

**Type-guard read pattern (FROM UI-SPEC §10):**

```ts
import { useSearchParams } from 'react-router'
import type { Seniority } from '@/api/types'

export type Country = 'PL' | 'DE' | 'EU' | 'WW'
export type Remote = 'any' | 'remote' | 'non_remote'

const DEFAULT_COUNTRY: Country = 'WW'
const DEFAULT_REMOTE: Remote = 'any'
const COUNTRIES: readonly Country[] = ['PL', 'DE', 'EU', 'WW'] as const
const REMOTES: readonly Remote[] = ['any', 'remote', 'non_remote'] as const

function isCountry(v: string | null): v is Country {
  return v !== null && (COUNTRIES as readonly string[]).includes(v)
}
```

**Default-elision write pattern (FROM UI-SPEC §10 lines 1200-1228):**

```ts
function setFilters(patch: Partial<DashboardFilters>) {
  setParams((prev) => {
    const next = new URLSearchParams(prev)
    if ('country' in patch) {
      if (patch.country && patch.country !== DEFAULT_COUNTRY) {
        next.set('country', patch.country)
      } else {
        next.delete('country')
      }
    }
    // ... seniority, remote
    return next
  }, { replace: false })
}
```

**Copy-edit anchors:**
- Export shape: `{ filters, setFilters }` (not `[filters, setFilters]` tuple)
- `Country` type union: `'PL' | 'DE' | 'EU' | 'WW'` (UI-SPEC §10 line 1164)
- `Remote` type union: `'any' | 'remote' | 'non_remote'` (UI-SPEC §10 line 1165)
- `Seniority` type imported from `@/api/types` (codegen output)
- `replace: false` on setParams (UI-SPEC §10 line 1234 — pushes new history entry for back-button stepping)

**Pitfalls / do NOT copy:**
- Do NOT mutate URL on mount — UI-SPEC §10 "Mount semantics": `/dashboard?country=WW` stays as-is until user touches a filter
- Do NOT use `Object.entries(patch).forEach` — explicit `if ('country' in patch) {...}` is the contract (handles `undefined` writes correctly per Partial-key semantics)
- Do NOT add `useMemo` around the returned `filters` object — TanStack Query v5 deep-hashes the queryKey; memo is unnecessary (RESEARCH §Pitfall 6)
- Use `react-router` package import (already on `package.json` line 33), NOT `react-router-dom` (that's the v6 package)
- Do NOT export `DEFAULT_COUNTRY`/`DEFAULT_REMOTE` constants — they're hook-internal; if the test needs them, redeclare inside the test file

---

### C.7 `frontend/src/api/jobs.ts` — MODIFIED (fill stub)

**Role:** Typed API service module — 3 typed async functions calling `authedFetch` + casting against `openapi-typescript`-generated types.
**Data flow:** Request-response (HTTP fetch).
**Analog:** `frontend/src/api/health.ts` lines 6-11 (typed fetch fn shape — but `health.ts` uses plain `fetch`, NOT `authedFetch`) + `frontend/src/api/authedFetch.ts` lines 54-82 (the wrapper itself).

**Why closest:** `health.ts` is the only existing typed `api/*.ts` file with a fully-implemented function (others — `agent.ts`, `profile.ts` — are stubs). For the `authedFetch` invocation pattern, the closest demonstration is inside `routes/DebugAgentStream.tsx` (lines 34-39) — but that uses POST + SSE. Phase 5 dashboard uses GET + JSON.

**Typed fetch fn shape pattern** (from `health.ts` lines 6-11):

```ts
export async function getHealth(signal?: AbortSignal): Promise<{ status: string }> {
  const baseUrl = import.meta.env.VITE_API_BASE_URL || ''
  const res = await fetch(`${baseUrl}/health`, { signal })
  if (!res.ok) throw new Error(`health: ${res.status}`)
  return res.json()
}
```

**authedFetch invocation pattern** (from `DebugAgentStream.tsx` lines 33-40):

```ts
const res = await authedFetch('/agent/stream', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ message: query }),
  signal: abortRef.current.signal,
})
if (!res.ok) throw new Error(`HTTP ${res.status}`)
```

**Phase 5 canonical shape** (synthesis):

```ts
import { authedFetch } from '@/api/authedFetch'
import type { components } from '@/api/types'  // openapi-typescript output
import type { DashboardFilters } from '@/components/dashboard/useDashboardFilters'

type TopSkillsResponse = components['schemas']['DashboardTopSkillsResponse']

function buildQuery(filters: DashboardFilters): string {
  const params = new URLSearchParams()
  if (filters.country !== 'WW') params.set('country', filters.country)
  if (filters.seniority) params.set('seniority', filters.seniority)
  if (filters.remote !== 'any') params.set('remote', filters.remote)
  return params.toString()
}

export async function topSkills(
  filters: DashboardFilters,
  signal?: AbortSignal,
): Promise<TopSkillsResponse> {
  const qs = buildQuery(filters)
  const res = await authedFetch(`/dashboard/top-skills${qs ? `?${qs}` : ''}`, { signal })
  if (!res.ok) throw new Error(`top-skills: HTTP ${res.status}`)
  return res.json()
}
```

**Copy-edit anchors:**
- Function names: `topSkills`, `salaryBands`, `cvVsMarket` (camelCase matching CONTEXT D-15)
- URL paths: `/dashboard/top-skills`, `/dashboard/salary-bands`, `/dashboard/cv-vs-market`
- Type imports: `import type { components } from '@/api/types'` then `components['schemas']['DashboardTopSkillsResponse']` etc.
- DELETE the `export {}` stub line 3 (currently the entire file body)
- Re-run `npm run codegen` AFTER backend lands the 3 routes — this regenerates `types.ts` with the named schemas

**Pitfalls / do NOT copy:**
- Do NOT use plain `fetch` like `health.ts` — authenticated routes MUST go through `authedFetch` (Phase 4 D-13)
- Do NOT inline `headers: { 'Content-Type': 'application/json' }` — GET requests don't have bodies; the header is irrelevant
- Do NOT throw the response body as the error — `throw new Error(\`top-skills: HTTP ${res.status}\`)` is the right shape (matches DebugAgentStream's `HTTP ${res.status}` convention so `describeError` in widgets renders correctly)
- The `searchJobs` function mentioned in CONTEXT D-16 ("typed `searchJobs` (existing)") does NOT actually exist yet — the stub is the WHOLE file. Phase 5 adds 3 fns + leaves `searchJobs` for a later phase (or omits it entirely)
- Default-elision in the URL query string: `country=WW` and `remote=any` are OMITTED (keeps URLs + cache-keys clean) — see `buildQuery` above

---

### C.8 `frontend/src/api/types.ts` — REGENERATED

**Role:** openapi-typescript codegen output.
**Data flow:** n/a (not hand-written).
**Analog:** Self — regenerated via `npm run codegen` (per `package.json` line 13).

**Why no analog:** The file is machine-generated. The codegen workflow is already wired in Phase 4 (Plan 04-01). Phase 5's only action: re-run after backend endpoints land.

**Action sequence:**
1. Backend Wave 1 lands `analytics.py` + `api/dashboard.py` + 3 routes
2. Bring up backend locally (`uv run job-rag serve`)
3. Run `cd frontend && npm run codegen` (hits `http://localhost:8000/openapi.json` per package.json line 13)
4. Verify `frontend/src/api/types.ts` now contains `components.schemas.DashboardTopSkillsResponse`, `DashboardSalaryBandsResponse`, `DashboardCvMatchResponse`, `TopSkillItem`, `MissingSkillItem`, `CountryFilter`, `RemoteFilter`
5. Re-run `npm run codegen:snapshot` to update `openapi.snapshot.json` for CI drift detection (per `package.json` line 14)

**Pitfalls:**
- Do NOT hand-edit `types.ts` — it's regenerated. Any manual edits get clobbered.
- The `codegen` script needs the backend RUNNING — if backend isn't up, the command fails. Document this in the executor task.
- `npm run codegen:snapshot` reads `./openapi.snapshot.json` — do NOT delete the snapshot file before re-running (Plan 04-01 wired the snapshot)

---

### C.9 `frontend/openapi.snapshot.json` — REGENERATED

**Role:** Captured OpenAPI snapshot for CI drift detection (Plan 04-01).
**Data flow:** n/a (machine-generated; checked into git).
**Analog:** Self — the existing file (21126 bytes; lines: machine-generated JSON).

**Action sequence:** Same as C.8. After backend lands, regenerate via the same workflow Plan 04-01 wired (typically `uv run job-rag serve` + `curl http://localhost:8000/openapi.json > frontend/openapi.snapshot.json` — but inspect Plan 04-01's actual command).

**Pitfalls:**
- The snapshot is the "diff against this" reference for CI's openapi-drift check — if Phase 5's backend endpoints change shape without regenerating the snapshot, CI fails. Do NOT skip the regeneration step.
- Snapshot is git-tracked — commit alongside the backend changes so the diff is visible in PR

---

### C.10 `frontend/package.json` — MODIFIED (transitively only)

**Role:** NPM manifest; gets 3 new transitive deps when shadcn `add` runs.
**Data flow:** n/a.
**Analog:** Self — the existing 16-dep block (lines 17-39).

**Why "transitively only":** Phase 5 does NOT directly add deps via `npm install <pkg>`. The `npx shadcn@latest add alert chart toggle-group` invocation mutates `package.json` to add:
- `recharts` ^3.8.1 (via shadcn `chart`)
- `@radix-ui/react-toggle-group` ^1.1.11 (via shadcn `toggle-group`)
- possibly `@radix-ui/react-toggle` (transitive of toggle-group; verify on install)

**Existing deps pattern** (from `package.json` lines 17-39):

```json
"dependencies": {
  "@azure/msal-browser": "^5.11.0",
  "@tanstack/react-query": "^5.100.11",
  "lucide-react": "^1.16.0",
  "radix-ui": "^1.4.3",
  "react": "^19.2.6",
  "react-router": "^7.15.1",
  "shadcn": "^4.7.0",
  ...
}
```

**Copy-edit anchors:**
- Install command: `cd frontend && npx shadcn@latest add alert chart toggle-group` (UI-SPEC §2 + Pitfall 8 — BARE invocation)
- Expected new deps to verify after install: `recharts`, `@radix-ui/react-toggle-group`
- Possible `overrides` addition (only if peer-dep warnings appear — RESEARCH §Pitfall 7):
  ```json
  "overrides": {
    "react-is": "$react"
  }
  ```

**Pitfalls / do NOT copy:**
- Do NOT pass `--style new-york` / `--base-color zinc` flags to shadcn add (UI-SPEC §17 Pitfall 8 — would clobber existing `components.json` `radix-nova` / `neutral` preset)
- Do NOT manually `npm install recharts` — shadcn does it as part of `add chart` (CONTEXT D-14)
- Do NOT pre-emptively add `overrides.react-is` — only add if `npm install` post-shadcn-add produces actual warnings (verify with `npm ls react-is`)
- Do NOT bump versions of any existing deps — Phase 5 is purely additive

---

### Net-new shadcn primitives (installed via `npx shadcn@latest add`)

The following three files materialise from `npx shadcn@latest add alert chart toggle-group`. They are NOT hand-written — the executor's only intervention is running the install command and verifying the resulting files match shadcn's official emissions.

### C.11 `frontend/src/components/ui/alert.tsx` — NEW (shadcn install)

**Role:** shadcn `Alert` + `AlertTitle` + `AlertDescription` (pure CVA + Tailwind).
**Analog:** `frontend/src/components/ui/badge.tsx` lines 1-49 — same pure-CVA + Tailwind shape, no Radix dependency.

**Why closest:** Like `Badge`, `Alert` is a pure CVA + Tailwind primitive (no Radix import). The existing `badge.tsx` shows the canonical `cva()` + `variants: { variant: { default, destructive, ... } }` shape — same pattern the shadcn-emitted `alert.tsx` will follow.

**CVA pattern reference** (from `badge.tsx` lines 7-28):

```tsx
const badgeVariants = cva(
  "group/badge inline-flex h-5 w-fit ... text-xs font-medium ...",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground",
        destructive: "bg-destructive/10 text-destructive ...",
        ...
      },
    },
    defaultVariants: { variant: "default" },
  }
)
```

**Copy-edit anchors:** N/A — shadcn writes the file. Verify post-install:
- Exports: `Alert`, `AlertTitle`, `AlertDescription`
- Variants exposed: `default`, `destructive`
- No Radix import (pure CVA + Tailwind)

**Pitfalls:**
- shadcn `alert` is the static a11y primitive (`role="alert"` on destructive variant) — NOT `alert-dialog` (which is the modal version). RESEARCH §"Standard Stack" verified this.
- If shadcn emits something with a Radix import, the install was wrong — re-check `components.json` wasn't tampered with

---

### C.12 `frontend/src/components/ui/chart.tsx` — NEW (shadcn install)

**Role:** shadcn `ChartContainer` + `ChartTooltip` + `ChartTooltipContent` + `ChartLegend` + `ChartLegendContent` + `ChartConfig` type (wrapper around Recharts).
**Analog:** None — net-new. Nearest reference: `frontend/src/components/ui/dialog.tsx` lines 1-167 (composable shadcn wrapper exporting multiple primitives via `radix-ui` import).

**Why no good analog:** No existing chart-wrapping primitive in the codebase. The dialog.tsx file shows the shape of a "shadcn primitive that exports multiple named components" (composable wrapper around a third-party lib), which is what chart.tsx becomes.

**Composable-export pattern reference** (from `dialog.tsx` lines 155-166):

```tsx
export {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogOverlay,
  DialogPortal,
  DialogTitle,
  DialogTrigger,
}
```

**Copy-edit anchors:** N/A — shadcn writes the file. Verify post-install:
- Exports: `ChartContainer`, `ChartTooltip`, `ChartTooltipContent`, `ChartLegend`, `ChartLegendContent`, type `ChartConfig`
- CSS vars wired: `--chart-1` through `--chart-5` in `app.css` (verify via `grep '\-\-chart-' frontend/src/app.css`)
- `recharts` added to `package.json` deps (^3.x)

**Pitfalls:**
- The shadcn `chart` block adds `--chart-1..5` CSS vars to `app.css` — UI-SPEC §17 lists `app.css` as "MUST NOT modify" in Phase 5. EXCEPTION: shadcn install is what mutates it; the executor must verify the diff is ONLY the CSS-var additions (no other changes to `app.css`). If shadcn touches anything beyond the chart vars, revert and investigate.
- Net-new pattern reference: see RESEARCH §"Standard Stack" + UI-SPEC §7 for canonical usage inside `SalaryBandsCard`

---

### C.13 `frontend/src/components/ui/toggle-group.tsx` — NEW (shadcn install)

**Role:** shadcn `ToggleGroup` + `ToggleGroupItem` (Radix wrapper).
**Analog:** `frontend/src/components/ui/dropdown-menu.tsx` lines 1-50 — same radix-ui wrapping shape.

**Why closest:** `dropdown-menu.tsx` shows the canonical shadcn-Radix-wrapper pattern: `import { DropdownMenu as DropdownMenuPrimitive } from "radix-ui"` → re-wrap with `data-slot="..."` + Tailwind className. `toggle-group.tsx` follows the same shape, swapping `DropdownMenu` → `ToggleGroup`.

**Radix-wrapper pattern reference** (from `dropdown-menu.tsx` lines 1-30):

```tsx
import * as React from "react"
import { DropdownMenu as DropdownMenuPrimitive } from "radix-ui"

import { cn } from "@/lib/utils"

function DropdownMenu({
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Root>) {
  return <DropdownMenuPrimitive.Root data-slot="dropdown-menu" {...props} />
}

function DropdownMenuTrigger({
  ...props
}: React.ComponentProps<typeof DropdownMenuPrimitive.Trigger>) {
  return (
    <DropdownMenuPrimitive.Trigger
      data-slot="dropdown-menu-trigger"
      {...props}
    />
  )
}
```

**Copy-edit anchors:** N/A — shadcn writes the file. Verify post-install:
- Exports: `ToggleGroup`, `ToggleGroupItem`
- Imports from `radix-ui` (NOT `@radix-ui/react-toggle-group` directly — codebase uses the umbrella `radix-ui` v1.4.3 per package.json line 29)
- A peer file `frontend/src/components/ui/toggle.tsx` is auto-installed (UI-SPEC §2 — "installs together as a pair")

**Pitfalls:**
- The `radix-ui` umbrella package is on line 29 of `package.json` (^1.4.3) — newer shadcn versions might emit `@radix-ui/react-toggle-group` direct imports. If the emit looks different, sanity-check that runtime resolution still works (the umbrella package re-exports the discrete ones)

---

### C.14–C.18 Frontend tests

All 5 frontend tests follow the same Vitest + RTL pattern. Analog is the existing `frontend/src/test/shellPrimitives.test.tsx` (lines 1-51) — describes/it/render/screen/expect structure.

**Tests location convention:** The existing tests live in `frontend/src/test/` (flat directory). UI-SPEC §"Test Data Strategy" recommends `*.test.tsx` colocated with components (`frontend/src/components/dashboard/__tests__/...`). Phase 5 introduces the colocated convention — both work with Vitest's default config; executor's choice. The current PATTERNS.md table uses the colocated path per CONTEXT D-15 + UI-SPEC §17 "Components Phase 5 CREATES".

### C.14 `frontend/src/components/dashboard/__tests__/TopSkillsCard.test.tsx` — NEW

**Analog:** `frontend/src/test/shellPrimitives.test.tsx` lines 1-51.

**RTL render pattern** (from `shellPrimitives.test.tsx`):

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'

describe('EmptyState (SHEL-06)', () => {
  it('renders heading and body', () => {
    render(<EmptyState icon={Inbox} heading="Empty" body="No data" />)
    expect(screen.getByRole('heading', { name: /empty/i })).toBeInTheDocument()
    expect(screen.getByText(/no data/i)).toBeInTheDocument()
  })
})
```

**Copy-edit anchors:**
- Tests to cover (per UI-SPEC §"Validation Architecture"):
  - `renders skeleton on isPending`
  - `renders alert on isError`
  - `renders empty state on data.skills.length === 0`
  - `renders bars on data`
  - `renders "Show more" button when skills.length > VISIBLE_ROWS`
  - `opens dialog when Show more clicked` (uses `userEvent`)
- Mock `useQuery` return shapes via `vi.mock('@tanstack/react-query', () => ({ useQuery: () => ({...}) }))`
- Mock `useDashboardFilters` to return a deterministic filters object

**Pitfalls / do NOT copy:**
- Do NOT render inside an actual `QueryClientProvider` — mock `useQuery` directly so tests don't hit a real query lifecycle (the only existing `QueryClientProvider`-wrapped test is `queryClient.test.tsx` lines 19-26 — that's a different concern: testing the client itself)
- Do NOT mock `topSkills` from `@/api/jobs` — mocking `useQuery` directly is simpler and more contract-focused (testing branch logic, not network shape)

---

### C.15 `frontend/src/components/dashboard/__tests__/SalaryBandsCard.test.tsx` — NEW

Same as C.14. Tests must additionally:
- Verify Recharts BarChart renders (look for the `[aria-label*="Salary band chart"]` from UI-SPEC §15)
- Verify the footer "{n} of {m} postings had salary data" text (UI-SPEC §11 verbatim)

**Pitfalls:**
- Recharts SVG rendering in jsdom may need `ResizeObserver` polyfill — Vitest's `jsdom` env via `@vitejs/plugin-react` should handle this, but verify; if tests fail with "ResizeObserver is not defined", add a global polyfill in `vitest.config.ts`

---

### C.16 `frontend/src/components/dashboard/__tests__/CvVsMarketCard.test.tsx` — NEW

Same as C.14. Tests must additionally:
- Verify `data.mean_score.toFixed(2)` renders (e.g. `0.42`)
- Verify chip list renders with `Badge` count matching `top_missing_must_have.length`
- Verify "Missing must-haves" section is HIDDEN when `top_missing_must_have.length === 0` (UI-SPEC §8 hidden-chip behaviour)

---

### C.17 `frontend/src/components/dashboard/__tests__/DashboardFilters.test.tsx` — NEW

**Analog:** `frontend/src/test/AppShell.test.tsx` lines 1-26 — uses MemoryRouter wrapping (DashboardFilters needs the same since it consumes `useSearchParams`).

**MemoryRouter pattern** (from `AppShell.test.tsx`):

```tsx
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router'

describe('AppShell', () => {
  it('renders nav with Dashboard / Chat / Profile + account menu', async () => {
    const { AppShell } = await import('@/components/AppShell')
    render(
      <MemoryRouter>
        <AppShell />
      </MemoryRouter>,
    )
    expect(screen.getByRole('navigation', { name: /primary/i })).toBeInTheDocument()
  })
})
```

**Copy-edit anchors:**
- Wrap rendering in `<MemoryRouter initialEntries={['/dashboard']}>`
- Tests to cover (UI-SPEC §"Validation Architecture"):
  - 4 country options visible (Worldwide / EU / Germany / Poland)
  - 6 seniority options visible (Any seniority / Junior / Mid / Senior / Staff / Lead)
  - 3 remote toggle items (Any / Remote / On-site)
  - `aria-label="Dashboard filters"` present on the group
  - Default country trigger label = `Worldwide` when URL has no `country` param
- Use `userEvent.click` to verify dropdown opens (interaction tests)

---

### C.18 `frontend/src/components/dashboard/useDashboardFilters.test.ts` — NEW

**Analog:** `frontend/src/test/AuthGate.test.tsx` lines 1-37 (MemoryRouter setup pattern — closest existing) + `frontend/src/test/queryClient.test.tsx` lines 9-25 (probe-component testing pattern).

**Why this is a partial analog:** No existing `renderHook` usage in this codebase. The cleanest pattern is a small probe component that calls the hook and exposes results via DOM.

**Probe-component test pattern** (synthesized from existing patterns):

```ts
import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Route, Routes } from 'react-router'

import { useDashboardFilters } from './useDashboardFilters'

function Probe() {
  const { filters, setFilters } = useDashboardFilters()
  return (
    <div>
      <span data-testid="country">{filters.country}</span>
      <span data-testid="remote">{filters.remote}</span>
      <button onClick={() => setFilters({ country: 'WW' })}>set-WW</button>
    </div>
  )
}

describe('useDashboardFilters', () => {
  it('reads country from URL', () => {
    render(
      <MemoryRouter initialEntries={['/dashboard?country=DE']}>
        <Routes>
          <Route path="/dashboard" element={<Probe />} />
        </Routes>
      </MemoryRouter>,
    )
    expect(screen.getByTestId('country').textContent).toBe('DE')
  })
})
```

**Copy-edit anchors:**
- Tests to cover (UI-SPEC §"Validation Architecture"):
  - `reads country=DE from URL ?country=DE`
  - `defaults to country=WW when URL has no country param`
  - `reads remote=remote from URL ?remote=remote`
  - `writes country=PL to URL on setFilters({ country: 'PL' })`
  - `default elision: setFilters({ country: 'WW' }) DELETES the param`
  - `default elision: setFilters({ remote: 'any' }) DELETES the param`
  - `setFilters preserves other params (e.g. setting country preserves seniority)`
- Use `MemoryRouter` with `initialEntries` for reading; use a button + `userEvent.click` to trigger writes

**Pitfalls / do NOT copy:**
- Do NOT use `@testing-library/react-hooks` (deprecated since RTL v16) — use the probe-component pattern
- The default-elision test must inspect the URL state — easiest via `useLocation()` inside the Probe and rendering `location.search` to a data-testid

---

## Shared Patterns (cross-cutting)

### Authentication (backend routes)
**Source:** `src/job_rag/api/routes.py` line 178 (decorator block) + line 181 (Annotated dep).
**Apply to:** All 3 new dashboard endpoints.

```python
@router.get(
    "/dashboard/X",
    tags=["dashboard"],
    dependencies=[Depends(require_api_key), Depends(standard_limit)],
)
async def X_route(
    session: Session,
    user_id: Annotated[uuid.UUID, Depends(get_current_user_id)],
    ...
) -> DashboardXResponse:
    ...
```

### Authentication (frontend service)
**Source:** `frontend/src/api/authedFetch.ts` lines 54-82.
**Apply to:** All 3 new typed fns in `jobs.ts`.

```ts
const res = await authedFetch(`/dashboard/X${qs ? `?${qs}` : ''}`, { signal })
if (!res.ok) throw new Error(`X: HTTP ${res.status}`)
return res.json()
```

### Structured logging (backend)
**Source:** `src/job_rag/services/retrieval.py` line 16 + line 251-256.
**Apply to:** Each analytics function entry/exit + each route handler.

```python
log = get_logger(__name__)
# ...
log.info("dashboard_query", endpoint="top-skills", filters={"country": country, "seniority": seniority, "remote": remote}, n=total_postings)
```

### Loading / empty / error layered pattern (frontend widgets)
**Source:** `frontend/src/components/EmptyState.tsx` lines 18-33 + `frontend/src/components/ui/skeleton.tsx` lines 3-11 + UI-SPEC §9 widget-level pattern.
**Apply to:** All 3 widget cards (TopSkillsCard, SalaryBandsCard, CvVsMarketCard).

Canonical branch order (UI-SPEC §"Loading / Empty / Error Layered Pattern" lines 736-742):

```tsx
if (isError) return <Alert variant="destructive">…</Alert>
if (isPending) return <Skeleton …/>
if (data.total === 0) return <EmptyState …/>
return <ActualContent data={data} />
```

### TanStack Query queryKey + staleTime override
**Source:** `frontend/src/api/queryClient.ts` line 7 (default 30s) + UI-SPEC §"TanStack Query caching override" lines 540-545.
**Apply to:** All 3 widget useQuery calls.

```tsx
useQuery({
  queryKey: ['dashboard', '<widget>', filters],
  queryFn: ({ signal }) => fn(filters, signal),
  staleTime: 5 * 60_000,  // override Phase 4 default 30s
})
```

### URL state with default elision (frontend hook)
**Source:** UI-SPEC §10 (canonical — no codebase analog).
**Apply to:** `useDashboardFilters.ts` ONLY (Phase 5 has one URL-state hook).

---

## No Analog Found (net-new patterns; see canonical reference)

| File | Role | Data Flow | Canonical Reference |
|------|------|-----------|---------------------|
| `frontend/src/components/ui/chart.tsx` | shadcn Recharts wrapper | n/a | RESEARCH §"Standard Stack" + shadcn `chart` docs (ui.shadcn.com/docs/components/chart) — installed via `npx shadcn@latest add chart`, NOT hand-written |
| `frontend/src/components/dashboard/SalaryBandsCard.tsx` | Recharts BarChart consumer | useQuery → BarChart | UI-SPEC §7 (locked JSX skeleton lines 687-787) — no existing Recharts usage |
| `frontend/src/components/dashboard/useDashboardFilters.ts` | URL state hook | URL ↔ filters | UI-SPEC §10 (locked implementation lines 1160-1232) + RESEARCH §Pattern 5 — no existing useSearchParams wrapper |

---

## Metadata

**Analog search scope:** `src/job_rag/{api,services,db}/`, `tests/`, `frontend/src/{api,components,routes,test}/`
**Files scanned:** ~45 source files + 5 existing tests + 8 shadcn primitives + 7 API/utility files
**Pattern extraction date:** 2026-05-22
**Working tree root:** `/Users/adrian/Developer/job-rag/.claude/worktrees/gsd-plan-phase-05`
