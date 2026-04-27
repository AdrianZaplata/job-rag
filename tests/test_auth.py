"""get_current_user_id v1 contract test.

Covers BACK-08 (D-08, D-10): the FastAPI dependency returns Settings.seeded_user_id
as a UUID. Phase 4 rewrites this exact function body to parse the Entra JWT
sub/oid claim - no other call site changes (D-10).

Plan 05 lands the symbol; until then this test skips on ImportError.
"""

import pytest


@pytest.mark.asyncio
class TestGetCurrentUserId:
    async def test_returns_seeded_user_id(self):
        """v1: returns Settings.seeded_user_id (D-10).

        Phase 4 rewrites the body to parse JWT - the test body itself does not
        change because the dependency contract (returns the user UUID) holds
        across the rewrite.
        """
        import importlib

        from job_rag.config import settings

        try:
            auth = importlib.import_module("job_rag.api.auth")
        except ImportError as e:
            pytest.skip(f"job_rag.api.auth not yet added (Plan 05): {e}")
        if not hasattr(auth, "get_current_user_id"):
            pytest.skip("get_current_user_id not yet added (Plan 05)")
        result = await auth.get_current_user_id()
        assert result == settings.seeded_user_id
        assert isinstance(result, type(settings.seeded_user_id))
