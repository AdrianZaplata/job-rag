"""get_current_user_id v1 contract test.

Covers BACK-08 (D-08, D-10): the FastAPI dependency returns Settings.seeded_user_id
as a UUID for an allowlisted Entra oid. Phase 4 (Plan 04-02) rewrote the body to
parse the Entra JWT sub/oid claim and reject any non-allowlisted oid; the
dependency CONTRACT (returns the user UUID) holds across the rewrite, so the
core assertion (`result == settings.seeded_user_id`) is preserved.

Plan 05 lands the symbol; until then this test skips on ImportError.
"""

from unittest.mock import MagicMock

import pytest


@pytest.mark.asyncio
class TestGetCurrentUserId:
    async def test_returns_seeded_user_id(self, monkeypatch: pytest.MonkeyPatch):
        """v1 / Phase 4: returns Settings.seeded_user_id for allowlisted oid (D-10).

        Phase 4 (Plan 04-02) rewrote the body to:
        1. Validate Entra JWT via fastapi-azure-auth's azure_scheme (Depends).
        2. Compare `user.claims['oid']` against `settings.seeded_user_entra_oid`.
        3. Return `settings.seeded_user_id` on match; raise HTTPException(403) on miss.

        This happy-path test mocks a User instance with a matching oid and
        asserts the original dependency contract holds.
        """
        import importlib

        from job_rag.config import settings

        try:
            auth = importlib.import_module("job_rag.api.auth")
        except ImportError as e:
            pytest.skip(f"job_rag.api.auth not yet added (Plan 05): {e}")
        if not hasattr(auth, "get_current_user_id"):
            pytest.skip("get_current_user_id not yet added (Plan 05)")

        # Seed settings.seeded_user_entra_oid with a known value, then mock a
        # fastapi-azure-auth User instance whose claims.oid matches.
        monkeypatch.setattr(settings, "seeded_user_entra_oid", "adrian-test-oid")
        fake_user = MagicMock()
        fake_user.claims = {"oid": "adrian-test-oid", "sub": "adrian-sub"}

        result = await auth.get_current_user_id(user=fake_user)
        assert result == settings.seeded_user_id
        assert isinstance(result, type(settings.seeded_user_id))
