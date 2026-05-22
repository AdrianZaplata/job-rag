"""Phase 5 Wave 0 - skip-guarded test scaffolds for analytics service module.

Each test class skips cleanly until src/job_rag/services/analytics.py
exports the target symbol. No test edits required when Plan 05-02 lands.

Pattern: Plan 01-01 3-guard skip-on-missing (ImportError + hasattr).
"""

import importlib

import pytest

try:
    _analytics = importlib.import_module("job_rag.services.analytics")
except ImportError:
    _analytics = None


def _has(symbol: str) -> bool:
    """Return True iff the analytics module exports the given symbol."""
    return _analytics is not None and hasattr(_analytics, symbol)


pytestmark = pytest.mark.asyncio


@pytest.mark.skipif(
    not _has("top_skills"),
    reason="analytics.top_skills not yet shipped (Plan 05-02)",
)
class TestTopSkills:
    async def test_returns_skills_with_must_nice_split(self, dashboard_postings_factory):
        pytest.skip("Activated when Plan 05-02 lands top_skills implementation")

    async def test_soft_skills_hidden_by_default(self, dashboard_postings_factory):
        pytest.skip("Activated when Plan 05-02 lands top_skills implementation")

    async def test_include_soft_true_returns_soft_skills(self, dashboard_postings_factory):
        """E7: ?include_soft=true returns soft skills."""
        pytest.skip("Activated when Plan 05-02 lands top_skills implementation")

    async def test_limit_caps_result_size(self, dashboard_postings_factory):
        pytest.skip("Activated when Plan 05-02 lands top_skills implementation")


@pytest.mark.skipif(
    not _has("salary_bands"),
    reason="analytics.salary_bands not yet shipped (Plan 05-02)",
)
class TestSalaryBands:
    async def test_returns_p25_p50_p75(self, dashboard_postings_factory):
        pytest.skip("Activated when Plan 05-02 lands salary_bands implementation")

    async def test_month_normalized_to_year(self, dashboard_postings_factory):
        """E5: salary_period='month' rows normalized x 12."""
        pytest.skip("Activated when Plan 05-02 lands salary_bands implementation")

    async def test_hour_rows_excluded(self, dashboard_postings_factory):
        """E4: salary_period='hour' rows excluded from percentiles."""
        pytest.skip("Activated when Plan 05-02 lands salary_bands implementation")

    async def test_null_salary_excluded_from_count(self, dashboard_postings_factory):
        """E3: NULL salary_min rows excluded; postings_with_salary count is accurate."""
        pytest.skip("Activated when Plan 05-02 lands salary_bands implementation")

    async def test_empty_result_returns_none_percentiles(self, dashboard_postings_factory):
        """RESEARCH Pitfall 2: percentile_cont over empty result = NULL -> returns int|None."""
        pytest.skip("Activated when Plan 05-02 lands salary_bands implementation")


@pytest.mark.skipif(
    not _has("cv_match"),
    reason="analytics.cv_match not yet shipped (Plan 05-02)",
)
class TestCvMatch:
    async def test_returns_mean_score_postings_compared_top_missing(
        self, dashboard_postings_factory
    ):
        pytest.skip("Activated when Plan 05-02 lands cv_match implementation")

    async def test_empty_filter_returns_200(self, dashboard_postings_factory):
        """D-12 / E1: zero postings filter returns mean_score=None, postings_compared=0."""
        pytest.skip("Activated when Plan 05-02 lands cv_match implementation")

    async def test_top_3_missing_must_have_capped(self, dashboard_postings_factory):
        """D-11: top_missing_must_have caps at 3 via Counter.most_common(3)."""
        pytest.skip("Activated when Plan 05-02 lands cv_match implementation")

    async def test_uses_match_posting_formula_unchanged(self, dashboard_postings_factory):
        """D-10: re-uses match_posting() 0.7 must + 0.3 nice formula verbatim."""
        pytest.skip("Activated when Plan 05-02 lands cv_match implementation")


@pytest.mark.skipif(
    not _has("_apply_filters"),
    reason="analytics._apply_filters not yet shipped (Plan 05-02)",
)
class TestApplyFilters:
    async def test_country_pl_filters_to_pl_postings(self, dashboard_postings_factory):
        pytest.skip("Activated when Plan 05-02 lands _apply_filters implementation")

    async def test_country_eu_includes_eu27_and_region_eu(self, dashboard_postings_factory):
        """D-07 / E2: EU branch checks location_country IN EU-27 OR location_region = 'EU'."""
        pytest.skip("Activated when Plan 05-02 lands _apply_filters implementation")

    async def test_country_ww_no_filter(self, dashboard_postings_factory):
        pytest.skip("Activated when Plan 05-02 lands _apply_filters implementation")

    async def test_seniority_filter_applied(self, dashboard_postings_factory):
        pytest.skip("Activated when Plan 05-02 lands _apply_filters implementation")

    async def test_remote_any_no_filter(self, dashboard_postings_factory):
        pytest.skip("Activated when Plan 05-02 lands _apply_filters implementation")

    async def test_remote_remote_filters_to_remote_policy_remote(
        self, dashboard_postings_factory
    ):
        pytest.skip("Activated when Plan 05-02 lands _apply_filters implementation")

    async def test_remote_non_remote_filters_to_hybrid_onsite(
        self, dashboard_postings_factory
    ):
        pytest.skip("Activated when Plan 05-02 lands _apply_filters implementation")


@pytest.mark.skipif(
    not _has("EU_COUNTRY_CODES"),
    reason="analytics.EU_COUNTRY_CODES not yet shipped (Plan 05-02)",
)
class TestEuCountrySetMembership:
    def test_27_members(self):
        pytest.skip("Activated when Plan 05-02 lands EU_COUNTRY_CODES")

    def test_germany_included(self):
        pytest.skip("Activated when Plan 05-02 lands EU_COUNTRY_CODES")

    def test_poland_included(self):
        pytest.skip("Activated when Plan 05-02 lands EU_COUNTRY_CODES")

    def test_greece_iso_gr_not_el(self):
        """RESEARCH EU-27 ISO Snapshot: ISO uses GR; EU protocol uses EL. Corpus uses ISO."""
        pytest.skip("Activated when Plan 05-02 lands EU_COUNTRY_CODES")

    def test_uk_excluded(self):
        """UK departed 2020-01-31."""
        pytest.skip("Activated when Plan 05-02 lands EU_COUNTRY_CODES")

    def test_is_frozenset(self):
        pytest.skip("Activated when Plan 05-02 lands EU_COUNTRY_CODES")


@pytest.mark.skipif(
    not _has("top_skills"),
    reason="analytics.top_skills not yet shipped (Plan 05-02)",
)
class TestFilterEffects:
    """E12 - country filter actually changes SQL. Phase 5 success criterion #5 canary."""

    async def test_country_filter_changes_results(self, dashboard_postings_factory):
        pytest.skip(
            "Activated when Plan 05-02 lands top_skills + Plan 05-03 wires the route"
        )
