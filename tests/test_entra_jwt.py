"""Phase 4 Entra JWT validation + OID allowlist tests.

Skip-on-missing pattern: tests stay green during Wave 0 (Plan 02 has not yet
landed azure_scheme); they activate the moment Plan 02 lands the rewritten
auth.py module. Pattern matches tests/test_auth.py::TestGetCurrentUserId.
"""
import importlib
import uuid
from unittest.mock import MagicMock

import pytest

from job_rag.config import settings


class TestSettingsHasNewFields:
    """Active this wave — Plan 01 ships the 4 new Settings fields."""

    def test_entra_tenant_id_present(self) -> None:
        assert isinstance(settings.entra_tenant_id, str)

    def test_entra_tenant_subdomain_present(self) -> None:
        assert isinstance(settings.entra_tenant_subdomain, str)

    def test_backend_audience_present(self) -> None:
        assert isinstance(settings.backend_audience, str)

    def test_seeded_user_entra_oid_present(self) -> None:
        assert isinstance(settings.seeded_user_entra_oid, str)


def _load_auth_or_skip():
    """Skip until Plan 02 lands azure_scheme + rewritten get_current_user_id."""
    try:
        auth = importlib.import_module("job_rag.api.auth")
    except ImportError as e:
        pytest.skip(f"job_rag.api.auth not importable (deps not yet installed): {e}")
    if not hasattr(auth, "azure_scheme"):
        pytest.skip("azure_scheme not yet added by Plan 02")
    if not hasattr(auth, "get_current_user_id"):
        pytest.skip("get_current_user_id not yet rewritten by Plan 02")
    return auth


@pytest.mark.asyncio
class TestEntraJwtValidation:
    """Activates when Plan 02 lands the rewritten get_current_user_id body."""

    async def test_rejects_mismatched_oid_with_403(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        auth = _load_auth_or_skip()
        monkeypatch.setattr(settings, "seeded_user_entra_oid", "expected-oid-uuid")
        fake_user = MagicMock()
        fake_user.claims = {"oid": "wrong-oid-uuid", "sub": "wrong-sub"}
        with pytest.raises(Exception) as exc_info:
            await auth.get_current_user_id(user=fake_user)
        # 403 with literal user_not_allowlisted detail per D-08
        assert getattr(exc_info.value, "status_code", None) == 403


@pytest.mark.asyncio
class TestOidGuard:
    """Activates when Plan 02 lands the rewritten get_current_user_id body."""

    async def test_empty_seeded_oid_rejects_everything(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Bootstrap-pending state — empty seeded_user_entra_oid denies all."""
        auth = _load_auth_or_skip()
        monkeypatch.setattr(settings, "seeded_user_entra_oid", "")
        fake_user = MagicMock()
        fake_user.claims = {"oid": "any-oid", "sub": "any-sub"}
        with pytest.raises(Exception) as exc_info:
            await auth.get_current_user_id(user=fake_user)
        assert getattr(exc_info.value, "status_code", None) == 403

    async def test_matching_oid_returns_seeded_user_id(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        auth = _load_auth_or_skip()
        monkeypatch.setattr(settings, "seeded_user_entra_oid", "adrian-oid")
        fake_user = MagicMock()
        fake_user.claims = {"oid": "adrian-oid", "sub": "adrian-sub"}
        result = await auth.get_current_user_id(user=fake_user)
        assert result == settings.seeded_user_id
        assert isinstance(result, uuid.UUID)
