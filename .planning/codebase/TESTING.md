# Testing Patterns

**Analysis Date:** 2026-04-21

## Test Framework

**Runner:**
- pytest 9.0.3+ (see `pyproject.toml` dependency-groups)
- pytest-asyncio for async test support
- Config: `pyproject.toml` `[tool.pytest.ini_options]`
  - Test paths: `tests/`
  - Custom markers: `eval` for extraction accuracy tests (marked as excluded from CI)

**Assertion Library:**
- pytest's built-in assertions (no extra library)
- pytest.approx() for floating-point comparisons: `assert result["score"] == pytest.approx(expected, abs=0.01)` in `tests/test_matching.py` line 106

**Run Commands:**
```bash
# All tests except eval-marked ones (used by CI)
uv run pytest -m "not eval"

# All tests including eval/accuracy tests (requires data files)
uv run pytest

# Watch mode (using pytest-watch or manual rerun)
uv run pytest tests/ --tb=short -v

# Coverage (via coverage plugin if installed)
uv run pytest --cov=src/
```

## Test File Organization

**Location:**
- Tests colocated in `tests/` directory at project root (separate from `src/`)
- One test file per module: `test_extraction.py` for `src/job_rag/extraction/`, `test_matching.py` for `src/job_rag/services/matching.py`
- Shared fixtures: `tests/conftest.py` (available globally to all tests)

**Naming:**
- Test files: `test_<component>.py`
- Test classes: `Test<FunctionOrFeature>` (e.g., `TestExtractPosting`, `TestMatchPosting`)
- Test methods: `test_<scenario>` (e.g., `test_exact_match`, `test_partial_must_have_match`)

**Structure:**
```
tests/
├── conftest.py                      # Global fixtures
├── fixtures/
│   └── sample_posting.md            # Test data files
├── test_agent.py
├── test_api.py
├── test_extraction.py
├── test_extraction_accuracy.py      # Marked with @pytest.mark.eval
├── test_matching.py
├── test_mcp_server.py
├── test_models.py
├── test_observability.py
├── test_retrieval.py
└── test_security.py
```

## Test Structure

**Suite Organization (example from `tests/test_matching.py`):**
```python
@pytest.fixture
def profile() -> UserSkillProfile:
    """Create a test profile fixture."""
    return UserSkillProfile(
        skills=[UserSkill(name="Python"), UserSkill(name="Docker"), ...],
        target_roles=["AI Engineer"],
        preferred_locations=["Berlin, Germany"],
        min_salary=65000,
        remote_preference=RemotePolicy.REMOTE,
    )


class TestMatchPosting:
    """Group related tests for posting matching logic."""
    
    def test_perfect_must_have_match(self, profile):
        """Test scenario with full skill match."""
        posting = _make_posting(must_have=["Python", "Docker"], nice_to_have=["React"])
        result = match_posting(profile, posting)
        assert result["must_have_score"] == 1.0
        assert result["score"] == 1.0
    
    def test_partial_must_have_match(self, profile):
        """Test scenario with partial skill match."""
        posting = _make_posting(must_have=["Python", "Kubernetes"], nice_to_have=[])
        result = match_posting(profile, posting)
        assert result["must_have_score"] == pytest.approx(1 / 3, abs=0.01)
```

**Patterns:**
- Setup: Fixtures provide test data; helper functions like `_make_posting()` build test objects
- Teardown: FastAPI app dependency overrides cleared after each test: `app.dependency_overrides.clear()` in `tests/test_api.py`
- Assertions: Direct assertions on results; use pytest.approx() for floats

## Mocking

**Framework:** unittest.mock (standard library)
- `MagicMock` for object mocking
- `AsyncMock` for async functions
- `patch` context manager for patching modules

**Patterns (from `tests/test_api.py`):**
```python
async def test_search_with_generate(self):
    """Mock async route dependency and LLM call."""
    from job_rag.api.deps import get_session
    
    mock_session = AsyncMock()
    
    async def override_session():
        yield mock_session
    
    app.dependency_overrides[get_session] = override_session
    
    with patch("job_rag.api.routes.rag_query", new_callable=AsyncMock) as mock_rag:
        mock_rag.return_value = {"answer": "...", "sources": [...]}
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/search", params={"q": "RAG experience"})
    
    app.dependency_overrides.clear()
    assert response.status_code == 200
```

**What to Mock:**
- External API calls: OpenAI client, Langfuse endpoints
- Database sessions: `AsyncMock()` for `AsyncSession`
- LLM extraction: Mock `instructor.from_openai()` and its completion methods
- Expensive operations: Model loading (reranker, embeddings)

**What NOT to Mock:**
- Core business logic: `_normalize_skill()`, `_skill_matches()`, `match_posting()` are tested directly
- Data models: Pydantic models validated with real data, not mocks
- Database schema validation: Models tested with real initialization
- Configuration: Real `settings` object used unless testing behavior when settings change

**Why No DB/API Keys in Unit Tests:**
- Tests must run in CI without secrets
- Database operations tested via mocked sessions
- API calls intercepted via `patch()` to avoid real HTTP
- Extraction accuracy tests marked `@pytest.mark.eval` and run separately with real data files (not in CI)

## Fixtures and Factories

**Test Data (from `tests/conftest.py`):**
```python
@pytest.fixture
def sample_raw_text() -> str:
    """Load raw job posting text from fixture file."""
    path = "tests/fixtures/sample_posting.md"
    with open(path, encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def sample_posting() -> JobPosting:
    """Create a valid JobPosting instance for tests."""
    return JobPosting(
        title="Senior AI Engineer",
        company="TestCorp",
        location="Berlin, Germany",
        remote_policy=RemotePolicy.HYBRID,
        salary_min=70000,
        salary_max=90000,
        salary_raw="€70,000-€90,000/year",
        salary_period=SalaryPeriod.YEAR,
        seniority=Seniority.SENIOR,
        employment_type="Full-time",
        requirements=[
            JobRequirement(skill="Python", category=SkillCategory.LANGUAGE, required=True),
            JobRequirement(skill="LLM", category=SkillCategory.CONCEPT, required=True),
            ...
        ],
        responsibilities=["Design and implement RAG pipelines", ...],
        benefits=["30 vacation days", "Remote flexibility"],
        source_url="https://www.linkedin.com/jobs/view/1234567890/",
        raw_text="sample raw text",
    )
```

**Factory Pattern (from `tests/test_matching.py`):**
```python
def _make_posting(
    must_have: list[str],
    nice_to_have: list[str],
    remote_policy: str = "remote",
    salary_min: int | None = None,
    salary_max: int | None = None,
) -> MagicMock:
    """Create a mock posting with requirements."""
    posting = MagicMock()
    posting.id = uuid.uuid4()
    posting.title = "AI Engineer"
    posting.company = "TestCorp"
    posting.remote_policy = remote_policy
    posting.salary_min = salary_min
    posting.salary_max = salary_max
    
    requirements = []
    for skill in must_have:
        req = MagicMock()
        req.skill = skill
        req.required = True
        requirements.append(req)
    for skill in nice_to_have:
        req = MagicMock()
        req.skill = skill
        req.required = False
        requirements.append(req)
    
    posting.requirements = requirements
    return posting
```

**Location:**
- Global fixtures in `tests/conftest.py` accessible to all tests
- Local fixtures defined within test modules near their usage
- Factory functions (`_make_posting()`, `_make_requirement()`) defined at module level before test classes

## Coverage

**Requirements:** Not enforced by CI (no minimum coverage % checked)

**View Coverage:**
```bash
# Generate coverage report with pytest
uv run pytest --cov=src/ --cov-report=html

# View HTML report
open htmlcov/index.html
```

**Current Coverage (rough estimate from test file line counts):**
- Extraction: 73 lines of tests covering ~84 lines of source (`src/job_rag/extraction/extractor.py`)
- Matching: 166 lines of tests covering ~140 lines of source (`src/job_rag/services/matching.py`)
- API: 198 lines of tests covering routes, auth, endpoints
- Models: 132 lines of validation tests
- Total: ~1292 lines of test code across 10 test files

## Test Types

**Unit Tests:**
- Scope: Individual functions and small modules
- Approach: Isolated mocking of dependencies
- Examples:
  - `TestNormalizeSkill`: 4 tests for skill normalization (case, whitespace, hyphens, underscores)
  - `TestSkillMatches`: 2 tests for exact/fuzzy match logic
  - `TestExtractLinkedInId`: 5 tests for LinkedIn URL parsing
  - All in sync, fast execution (<1s per test)

**Integration Tests:**
- Scope: Multiple components working together
- Approach: Mocked external services (OpenAI, database), real business logic
- Examples:
  - `TestMatchPosting`: 8 tests with real matching algorithm against mock postings
  - `TestAggregateGaps`: aggregation across multiple postings
  - `TestMatchEndpoint`: API endpoint with mocked session but real matching logic
  - Run with `pytest tests/test_matching.py` etc.

**Async/Await Tests:**
- Scope: AsyncIO functions and endpoints
- Framework: pytest-asyncio
- Pattern: Mark with `@pytest.mark.asyncio` on test class or method
- Example from `tests/test_api.py`:
  ```python
  @pytest.mark.asyncio
  class TestHealthEndpoint:
      async def test_health_ok(self):
          # Uses AsyncClient, async context managers, await syntax
          async with AsyncClient(transport=transport, base_url="http://test") as client:
              response = await client.get("/health")
  ```
- Set backend: `@pytest.fixture def anyio_backend(): return "asyncio"`

**Extraction Accuracy Tests (Evaluation Tests):**
- Scope: LLM extraction quality against ground truth
- Marked: `@pytest.mark.eval` to exclude from regular CI
- Location: `tests/test_extraction_accuracy.py`
- Data: JSON files in `data/eval/` directory
  - `extraction_ground_truth.json`: manually verified expected results
  - `extraction_results.json`: stored LLM outputs
- Approach: Parameterized tests comparing each field (company, remote_policy, seniority, etc.)
- Run separately: `uv run pytest -m eval` (only when eval data is present)
- Example:
  ```python
  @pytest.mark.eval
  class TestExtractionAccuracy:
      @pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
      def test_company_name(self, expected: dict, extracted: dict):
          assert extracted["company"] == expected["company"]
  ```

## Common Patterns

**Async Testing:**
```python
@pytest.mark.asyncio
async def test_async_operation(self):
    """Test an async function."""
    result = await search_postings(session, "query", top_k=5)
    assert len(result) >= 0  # Assertion on coroutine result
```

**Error Testing (Validation):**
```python
def test_missing_required_field_raises(self):
    """Pydantic validation error on missing field."""
    with pytest.raises(ValidationError):
        JobPosting(
            title="Test",
            # missing company
            location="Berlin",
            ...
        )
```

**Dependency Override (FastAPI):**
```python
async def test_with_mocked_dependency(self):
    """Override FastAPI dependency for testing."""
    from job_rag.api.deps import get_session
    
    async def override_session():
        yield AsyncMock()
    
    app.dependency_overrides[get_session] = override_session
    
    # Test runs with mocked session
    response = await client.get("/search")
    
    app.dependency_overrides.clear()  # Cleanup
```

**Parameterized Tests:**
```python
CASES = _build_cases()
CASE_IDS = [c[0].get("company", "unknown") for c in CASES]

@pytest.mark.parametrize("expected,extracted", CASES, ids=CASE_IDS)
def test_company_name(self, expected: dict, extracted: dict):
    """Run same test with different parameters."""
    assert extracted["company"] == expected["company"]
```

## CI Integration

**Pipeline (from `.github/workflows/ci.yml`):**
1. Lint: `uv run ruff check src/ tests/`
2. Type check: `uv run pyright src/`
3. Test: `uv run pytest -m "not eval"` (excludes extraction accuracy tests)
4. Audit: `uv run pip-audit --ignore-vuln CVE-2025-69872`

**Test Exclusion in CI:**
- `pytest -m "not eval"` skips all tests marked with `@pytest.mark.eval`
- Extraction accuracy tests require data files and manual ground truth (not in CI)
- Allows CI to run quickly without slow evaluation

---

*Testing analysis: 2026-04-21*
