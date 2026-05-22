"""Phase 5 Wave 1 - test bodies for analytics service module.

Plan 05-01 scaffolded skip-guarded class shells with pytest.skip() bodies.
Plan 05-02 (this file) fills the bodies with real assertions targeting:
  - src/job_rag/services/analytics.py exports top_skills, salary_bands,
    cv_match, _apply_filters, EU_COUNTRY_CODES

Test strategy (per 05-PATTERNS.md B.1 + 05-RESEARCH.md Test Data Strategy):
  - SQL-heavy functions (top_skills, salary_bands) use MagicMock + AsyncMock
    on session.execute, modeling SQLAlchemy result rows. This matches the
    existing test_lifespan.py / test_mcp_server.py pattern. PostgreSQL
    `percentile_cont` cannot run on SQLite, and aiosqlite is not a project
    dependency, so we avoid an in-process DB.
  - cv_match Python-fold tests inject a list of `JobPostingDB` rows directly
    via the dashboard_postings_factory and let the SQL pre-filter mock return
    those rows. The Python-side fold over `match_posting()` is hermetic.
  - TestApplyFilters tests verify the stmt mutation by introspecting the
    SQLAlchemy Select expression (.whereclause / compiled string).
  - TestEuCountrySetMembership tests are pure-Python (constant inspection).
  - TestFilterEffects exercises top_skills 4 times with different mocked
    rowsets per country to prove the call site changes results.
"""

import importlib
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from job_rag.models import RemotePolicy, UserSkill, UserSkillProfile

try:
    _analytics = importlib.import_module("job_rag.services.analytics")
except ImportError:
    _analytics = None


def _has(symbol: str) -> bool:
    """Return True iff the analytics module exports the given symbol."""
    return _analytics is not None and hasattr(_analytics, symbol)


pytestmark = pytest.mark.asyncio


def _make_top_skills_mock_session(
    *,
    rows: list[dict],
    total_postings: int = 12,
    unique_skills: int | None = None,
) -> MagicMock:
    """Build a MagicMock AsyncSession that returns `rows` for the GROUP BY query,
    a scalar `total_postings` for the count query, and a scalar `unique_skills`
    (defaults to len(rows)) for the DISTINCT query.

    The mock issues three execute() calls in this exact order (matches the
    implementation in top_skills):
      1. SELECT skill, must_count, nice_count, total ... GROUP BY skill
      2. SELECT count() ... (total_postings)
      3. SELECT count(DISTINCT skill) ... (unique_skills)
    """
    if unique_skills is None:
        unique_skills = len(rows)

    row_objs = []
    for r in rows:
        m = MagicMock()
        m.skill = r["skill"]
        m.must_count = r["must_count"]
        m.nice_count = r["nice_count"]
        m.total = r["total"]
        row_objs.append(m)

    skills_result = MagicMock()
    skills_result.all.return_value = row_objs

    total_result = MagicMock()
    total_result.scalar_one.return_value = total_postings

    unique_result = MagicMock()
    unique_result.scalar_one.return_value = unique_skills

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[skills_result, total_result, unique_result])
    return session


def _make_salary_bands_mock_session(
    *,
    p25: int | None,
    p50: int | None,
    p75: int | None,
    postings_with_salary: int,
    total_postings: int,
) -> MagicMock:
    """Build a MagicMock AsyncSession for salary_bands tests.

    Two execute() calls:
      1. percentile_cont aggregate (returns .one())
      2. total count (returns .scalar_one())
    """
    percentile_row = MagicMock()
    percentile_row.p25 = p25
    percentile_row.p50 = p50
    percentile_row.p75 = p75
    percentile_row.postings_with_salary = postings_with_salary

    percentile_result = MagicMock()
    percentile_result.one.return_value = percentile_row

    total_result = MagicMock()
    total_result.scalar_one.return_value = total_postings

    session = MagicMock()
    session.execute = AsyncMock(side_effect=[percentile_result, total_result])
    return session


def _make_cv_match_mock_session(*, postings: list) -> MagicMock:
    """Build a MagicMock AsyncSession that returns `postings` from the SQL
    pre-filter. cv_match issues a single execute() (select(JobPostingDB)).
    """
    scalars = MagicMock()
    scalars.all.return_value = postings

    exec_result = MagicMock()
    exec_result.scalars.return_value = scalars

    session = MagicMock()
    session.execute = AsyncMock(return_value=exec_result)
    return session


@pytest.fixture
def synthetic_profile() -> UserSkillProfile:
    """Profile that knows Python + AWS — used by cv_match formula tests."""
    return UserSkillProfile(
        skills=[UserSkill(name="Python"), UserSkill(name="AWS")],
        target_roles=["AI Engineer"],
        preferred_locations=[],
        min_salary=60000,
        remote_preference=RemotePolicy.REMOTE,
    )


@pytest.mark.skipif(
    not _has("top_skills"),
    reason="analytics.top_skills not yet shipped (Plan 05-02)",
)
class TestTopSkills:
    async def test_returns_skills_with_must_nice_split(self, dashboard_postings_factory):
        from job_rag.services.analytics import top_skills

        session = _make_top_skills_mock_session(
            rows=[
                {"skill": "Python", "must_count": 6, "nice_count": 0, "total": 6},
                {"skill": "AWS", "must_count": 3, "nice_count": 0, "total": 3},
                {"skill": "SQL", "must_count": 2, "nice_count": 0, "total": 2},
            ],
            total_postings=12,
            unique_skills=8,
        )

        result = await top_skills(session)

        assert set(result.keys()) >= {"skills", "total_postings", "unique_skills"}
        assert isinstance(result["skills"], list)
        for s in result["skills"]:
            assert {"skill", "must_count", "nice_count", "total"} <= set(s.keys())
        python_row = next((s for s in result["skills"] if s["skill"] == "Python"), None)
        assert python_row is not None
        assert python_row["must_count"] == 6
        assert result["total_postings"] == 12
        assert result["unique_skills"] == 8

    async def test_soft_skills_hidden_by_default(self, dashboard_postings_factory):
        """D-13: skill_category != 'soft' WHERE clause when include_soft=False (default)."""
        from job_rag.services.analytics import top_skills

        # Mock returns only hard skills since the WHERE clause filtered soft out at SQL.
        session = _make_top_skills_mock_session(
            rows=[
                {"skill": "Python", "must_count": 6, "nice_count": 0, "total": 6},
                {"skill": "AWS", "must_count": 3, "nice_count": 0, "total": 3},
            ],
        )
        result = await top_skills(session)
        skill_names = {s["skill"] for s in result["skills"]}
        assert "communication" not in skill_names
        assert "teamwork" not in skill_names

        # Inspect the SQL stmt that was passed to execute - the first call's stmt
        # MUST include the soft-skill exclusion clause.
        first_call_stmt = session.execute.call_args_list[0].args[0]
        compiled_sql = str(
            first_call_stmt.compile(compile_kwargs={"literal_binds": True})
        )
        assert "skill_category" in compiled_sql
        assert "soft" in compiled_sql

    async def test_include_soft_true_returns_soft_skills(self, dashboard_postings_factory):
        """E7: ?include_soft=true returns soft skills."""
        from job_rag.services.analytics import top_skills

        session = _make_top_skills_mock_session(
            rows=[
                {"skill": "Python", "must_count": 6, "nice_count": 0, "total": 6},
                {"skill": "communication", "must_count": 0, "nice_count": 2, "total": 2},
                {"skill": "teamwork", "must_count": 0, "nice_count": 1, "total": 1},
            ],
        )
        result = await top_skills(session, include_soft=True)
        skill_names = {s["skill"] for s in result["skills"]}
        assert "communication" in skill_names
        assert "teamwork" in skill_names

        # The first execute() stmt MUST NOT include the soft-skill exclusion.
        first_call_stmt = session.execute.call_args_list[0].args[0]
        compiled_sql = str(
            first_call_stmt.compile(compile_kwargs={"literal_binds": True})
        )
        # When include_soft=True, no skill_category != 'soft' clause in the SQL.
        assert "skill_category != 'soft'" not in compiled_sql.replace('"', "'")

    async def test_limit_caps_result_size(self, dashboard_postings_factory):
        from job_rag.services.analytics import top_skills

        # The mock returns 3 rows; in real SQL the LIMIT 3 would constrain it.
        # We verify by inspecting the stmt that LIMIT was applied.
        session = _make_top_skills_mock_session(
            rows=[
                {"skill": "Python", "must_count": 6, "nice_count": 0, "total": 6},
                {"skill": "AWS", "must_count": 3, "nice_count": 0, "total": 3},
                {"skill": "SQL", "must_count": 2, "nice_count": 0, "total": 2},
            ],
        )
        result = await top_skills(session, limit=3)
        assert len(result["skills"]) <= 3

        first_call_stmt = session.execute.call_args_list[0].args[0]
        compiled_sql = str(first_call_stmt.compile(compile_kwargs={"literal_binds": True}))
        assert "LIMIT 3" in compiled_sql.upper()


@pytest.mark.skipif(
    not _has("salary_bands"),
    reason="analytics.salary_bands not yet shipped (Plan 05-02)",
)
class TestSalaryBands:
    async def test_returns_p25_p50_p75(self, dashboard_postings_factory):
        from job_rag.services.analytics import salary_bands

        session = _make_salary_bands_mock_session(
            p25=60000, p50=75000, p75=90000,
            postings_with_salary=8, total_postings=12,
        )
        result = await salary_bands(session)
        assert result["p25"] == 60000
        assert result["p50"] == 75000
        assert result["p75"] == 90000
        assert result["postings_with_salary"] == 8
        assert result["total_postings"] == 12
        assert result["currency"] == "EUR"

    async def test_month_normalized_to_year(self, dashboard_postings_factory):
        """E5: salary_period='month' rows normalized x 12 - verify via SQL stmt inspection."""
        from job_rag.services.analytics import salary_bands

        session = _make_salary_bands_mock_session(
            p25=50000, p50=72000, p75=90000,
            postings_with_salary=8, total_postings=12,
        )
        await salary_bands(session)

        # The percentile stmt MUST normalize month -> year via CASE WHEN
        # salary_period = 'month' THEN salary_min * 12 ELSE salary_min END.
        percentile_stmt = session.execute.call_args_list[0].args[0]
        compiled_sql = str(
            percentile_stmt.compile(compile_kwargs={"literal_binds": True})
        )
        # Look for the month normalization clause.
        assert "month" in compiled_sql.lower()
        # Multiplication by 12 must appear somewhere in the case expression.
        assert "* 12" in compiled_sql or "*12" in compiled_sql

    async def test_hour_rows_excluded(self, dashboard_postings_factory):
        """E4: salary_period='hour' rows excluded from percentiles."""
        from job_rag.services.analytics import salary_bands

        session = _make_salary_bands_mock_session(
            p25=60000, p50=75000, p75=90000,
            postings_with_salary=8, total_postings=12,
        )
        await salary_bands(session)

        # Verify the WHERE clause restricts salary_period IN ('year', 'month')
        # (i.e. excludes 'hour').
        percentile_stmt = session.execute.call_args_list[0].args[0]
        compiled_sql = str(
            percentile_stmt.compile(compile_kwargs={"literal_binds": True})
        ).lower()
        # The IN clause for ('year', 'month') must appear.
        assert "year" in compiled_sql and "month" in compiled_sql
        # 'hour' MUST NOT appear in the WHERE clause directly as an included value.
        # Acceptable patterns: salary_period IN ('year', 'month').
        assert "in ('year', 'month')" in compiled_sql or "in ('month', 'year')" in compiled_sql

    async def test_null_salary_excluded_from_count(self, dashboard_postings_factory):
        """E3: NULL salary_min rows excluded; postings_with_salary count is accurate."""
        from job_rag.services.analytics import salary_bands

        # postings_with_salary < total_postings because at least one row has NULL
        session = _make_salary_bands_mock_session(
            p25=60000, p50=75000, p75=90000,
            postings_with_salary=8, total_postings=12,
        )
        result = await salary_bands(session)
        assert result["postings_with_salary"] < result["total_postings"]

        # The percentile stmt MUST include salary_min IS NOT NULL.
        percentile_stmt = session.execute.call_args_list[0].args[0]
        compiled_sql = str(
            percentile_stmt.compile(compile_kwargs={"literal_binds": True})
        ).lower()
        assert "is not null" in compiled_sql

    async def test_empty_result_returns_none_percentiles(self, dashboard_postings_factory):
        """RESEARCH Pitfall 2: percentile_cont over empty result = NULL -> returns int|None."""
        from job_rag.services.analytics import salary_bands

        session = _make_salary_bands_mock_session(
            p25=None, p50=None, p75=None,
            postings_with_salary=0, total_postings=0,
        )
        result = await salary_bands(session, country="PL", seniority="lead")
        assert result["p25"] is None
        assert result["p50"] is None
        assert result["p75"] is None
        assert result["postings_with_salary"] == 0


@pytest.mark.skipif(
    not _has("cv_match"),
    reason="analytics.cv_match not yet shipped (Plan 05-02)",
)
class TestCvMatch:
    async def test_returns_mean_score_postings_compared_top_missing(
        self, dashboard_postings_factory, synthetic_profile, monkeypatch
    ):
        from job_rag.services import analytics

        # Use the factory's full 12-posting variety.
        postings = dashboard_postings_factory()
        session = _make_cv_match_mock_session(postings=postings)

        # Stub load_profile to return the synthetic profile (no data/profile.json read).
        monkeypatch.setattr(analytics, "load_profile", lambda *, user_id: synthetic_profile)

        result = await analytics.cv_match(session, uuid.uuid4())
        assert "mean_score" in result
        assert "postings_compared" in result
        assert "top_missing_must_have" in result
        # mean_score is float or None.
        assert result["mean_score"] is None or isinstance(result["mean_score"], float)
        assert isinstance(result["postings_compared"], int)
        assert isinstance(result["top_missing_must_have"], list)
        assert len(result["top_missing_must_have"]) <= 3
        for item in result["top_missing_must_have"]:
            assert {"skill", "count", "percentage"} <= set(item.keys())

    async def test_empty_filter_returns_200(
        self, dashboard_postings_factory, synthetic_profile, monkeypatch
    ):
        """D-12 / E1: zero postings filter returns mean_score=None, postings_compared=0."""
        from job_rag.services import analytics

        session = _make_cv_match_mock_session(postings=[])
        monkeypatch.setattr(analytics, "load_profile", lambda *, user_id: synthetic_profile)

        result = await analytics.cv_match(session, uuid.uuid4())
        assert result["mean_score"] is None
        assert result["postings_compared"] == 0
        assert result["top_missing_must_have"] == []

    async def test_top_3_missing_must_have_capped(
        self, dashboard_postings_factory, monkeypatch
    ):
        """D-11: top_missing_must_have caps at 3 via Counter.most_common(3)."""
        from job_rag.services import analytics

        # Profile knows nothing - everything is "missing".
        empty_profile = UserSkillProfile(
            skills=[],
            target_roles=[],
            preferred_locations=[],
            min_salary=None,
            remote_preference=RemotePolicy.UNKNOWN,
        )

        # Full 12-posting fixture has > 3 unique must-have skills total.
        postings = dashboard_postings_factory()
        session = _make_cv_match_mock_session(postings=postings)
        monkeypatch.setattr(analytics, "load_profile", lambda *, user_id: empty_profile)

        result = await analytics.cv_match(session, uuid.uuid4())
        assert len(result["top_missing_must_have"]) <= 3

    async def test_uses_match_posting_formula_unchanged(
        self, dashboard_postings_factory, synthetic_profile, monkeypatch
    ):
        """D-10: re-uses match_posting() 0.7 must + 0.3 nice formula verbatim."""
        from job_rag.services import analytics
        from job_rag.services.matching import match_posting

        postings = dashboard_postings_factory()
        session = _make_cv_match_mock_session(postings=postings)
        monkeypatch.setattr(analytics, "load_profile", lambda *, user_id: synthetic_profile)

        result = await analytics.cv_match(session, uuid.uuid4())

        # Compute expected mean manually using match_posting directly.
        expected_scores = [match_posting(synthetic_profile, p)["score"] for p in postings]
        expected_mean = round(sum(expected_scores) / len(expected_scores), 3)
        assert result["mean_score"] == expected_mean
        assert result["postings_compared"] == len(postings)


@pytest.mark.skipif(
    not _has("_apply_filters"),
    reason="analytics._apply_filters not yet shipped (Plan 05-02)",
)
class TestApplyFilters:
    """Verify _apply_filters mutates the SQL select with the right WHERE clauses.

    We inspect the compiled SQL string rather than executing against a DB,
    since project doesn't ship aiosqlite and PG isn't available in unit tests.
    """

    def _compiled(self, stmt) -> str:
        return str(stmt.compile(compile_kwargs={"literal_binds": True}))

    async def test_country_pl_filters_to_pl_postings(self, dashboard_postings_factory):
        from sqlalchemy import select

        from job_rag.db.models import JobPostingDB
        from job_rag.services.analytics import _apply_filters

        stmt = _apply_filters(select(JobPostingDB), country="PL")
        sql = self._compiled(stmt)
        assert "location_country" in sql.lower()
        assert "'pl'" in sql.lower()

    async def test_country_eu_includes_eu27_and_region_eu(self, dashboard_postings_factory):
        """D-07 / E2: EU branch checks location_country IN EU-27 OR location_region = 'EU'."""
        from sqlalchemy import select

        from job_rag.db.models import JobPostingDB
        from job_rag.services.analytics import _apply_filters

        stmt = _apply_filters(select(JobPostingDB), country="EU")
        sql = self._compiled(stmt).lower()
        # Should have IN clause with EU codes AND an OR for location_region.
        assert " in (" in sql
        assert "location_region" in sql
        assert "'eu'" in sql
        # OR connector between the two branches.
        assert " or " in sql

    async def test_country_ww_no_filter(self, dashboard_postings_factory):
        from sqlalchemy import select

        from job_rag.db.models import JobPostingDB
        from job_rag.services.analytics import _apply_filters

        stmt_before = select(JobPostingDB)
        stmt_after = _apply_filters(stmt_before, country="WW")
        # The "WW" branch should add NO country WHERE clause.
        sql_after = self._compiled(stmt_after).lower()
        assert "location_country" not in sql_after

    async def test_seniority_filter_applied(self, dashboard_postings_factory):
        from sqlalchemy import select

        from job_rag.db.models import JobPostingDB
        from job_rag.services.analytics import _apply_filters

        stmt = _apply_filters(select(JobPostingDB), seniority="senior")
        sql = self._compiled(stmt).lower()
        assert "seniority" in sql
        assert "'senior'" in sql

    async def test_remote_any_no_filter(self, dashboard_postings_factory):
        from sqlalchemy import select

        from job_rag.db.models import JobPostingDB
        from job_rag.services.analytics import _apply_filters

        stmt = _apply_filters(select(JobPostingDB), remote="any")
        sql = self._compiled(stmt).lower()
        # No remote_policy WHERE clause when remote == "any".
        assert "remote_policy" not in sql

    async def test_remote_remote_filters_to_remote_policy_remote(
        self, dashboard_postings_factory
    ):
        from sqlalchemy import select

        from job_rag.db.models import JobPostingDB
        from job_rag.services.analytics import _apply_filters

        stmt = _apply_filters(select(JobPostingDB), remote="remote")
        sql = self._compiled(stmt).lower()
        assert "remote_policy" in sql
        assert "'remote'" in sql

    async def test_remote_non_remote_filters_to_hybrid_onsite(
        self, dashboard_postings_factory
    ):
        from sqlalchemy import select

        from job_rag.db.models import JobPostingDB
        from job_rag.services.analytics import _apply_filters

        stmt = _apply_filters(select(JobPostingDB), remote="non_remote")
        sql = self._compiled(stmt).lower()
        assert "remote_policy" in sql
        assert "'hybrid'" in sql
        assert "'onsite'" in sql


@pytest.mark.skipif(
    not _has("EU_COUNTRY_CODES"),
    reason="analytics.EU_COUNTRY_CODES not yet shipped (Plan 05-02)",
)
class TestEuCountrySetMembership:
    def test_27_members(self):
        from job_rag.services.analytics import EU_COUNTRY_CODES

        assert len(EU_COUNTRY_CODES) == 27

    def test_germany_included(self):
        from job_rag.services.analytics import EU_COUNTRY_CODES

        assert "DE" in EU_COUNTRY_CODES

    def test_poland_included(self):
        from job_rag.services.analytics import EU_COUNTRY_CODES

        assert "PL" in EU_COUNTRY_CODES

    def test_greece_iso_gr_not_el(self):
        """RESEARCH EU-27 ISO Snapshot: ISO uses GR; EU protocol uses EL. Corpus uses ISO."""
        from job_rag.services.analytics import EU_COUNTRY_CODES

        assert "GR" in EU_COUNTRY_CODES
        assert "EL" not in EU_COUNTRY_CODES

    def test_uk_excluded(self):
        """UK departed 2020-01-31."""
        from job_rag.services.analytics import EU_COUNTRY_CODES

        assert "GB" not in EU_COUNTRY_CODES
        assert "UK" not in EU_COUNTRY_CODES

    def test_is_frozenset(self):
        from job_rag.services.analytics import EU_COUNTRY_CODES

        assert isinstance(EU_COUNTRY_CODES, frozenset)


@pytest.mark.skipif(
    not _has("top_skills"),
    reason="analytics.top_skills not yet shipped (Plan 05-02)",
)
class TestFilterEffects:
    """E12 - country filter actually changes SQL. Phase 5 success criterion #5 canary."""

    async def test_country_filter_changes_results(self, dashboard_postings_factory):
        """Call top_skills 4 times with different country filters and assert
        that the compiled SQL stmt differs across calls. This is the success
        criterion canary: a buggy implementation that ignores `country` would
        produce identical SQL for all 4 invocations.
        """
        from job_rag.services.analytics import top_skills

        compiled_sqls = []
        for country in ("PL", "DE", "EU", "WW"):
            session = _make_top_skills_mock_session(
                rows=[
                    {"skill": "Python", "must_count": 3, "nice_count": 0, "total": 3},
                ],
                total_postings=4 if country == "PL" else (5 if country == "DE" else (10 if country == "EU" else 12)),
            )
            result = await top_skills(session, country=country)
            # Capture the compiled SQL of the GROUP BY stmt for diff comparison.
            first_call_stmt = session.execute.call_args_list[0].args[0]
            compiled_sqls.append(
                str(first_call_stmt.compile(compile_kwargs={"literal_binds": True}))
            )
            # Also assert that total_postings is taken from the mocked scalar.
            assert isinstance(result["total_postings"], int)

        # All 4 compiled SQL strings must differ pairwise (WW has no clause; PL/DE
        # have country='PL'/'DE'; EU has IN (...) OR location_region = 'EU').
        unique = set(compiled_sqls)
        assert len(unique) == 4, (
            f"Expected 4 distinct SQLs for PL/DE/EU/WW; got {len(unique)}.\n"
            + "\n---\n".join(compiled_sqls)
        )
