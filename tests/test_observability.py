from unittest.mock import patch

from job_rag import observability


def _clear_caches() -> None:
    observability.get_openai_client.cache_clear()
    observability._langfuse_handler.cache_clear()


class TestIsEnabled:
    def test_disabled_when_keys_missing(self):
        with patch.object(observability.settings, "langfuse_public_key", ""):
            with patch.object(observability.settings, "langfuse_secret_key", ""):
                assert observability.is_enabled() is False

    def test_enabled_when_both_keys_set(self):
        with patch.object(observability.settings, "langfuse_public_key", "pk-test"):
            with patch.object(observability.settings, "langfuse_secret_key", "sk-test"):
                assert observability.is_enabled() is True

    def test_disabled_when_only_one_key_set(self):
        with patch.object(observability.settings, "langfuse_public_key", "pk-test"):
            with patch.object(observability.settings, "langfuse_secret_key", ""):
                assert observability.is_enabled() is False


class TestGetOpenAIClient:
    def test_returns_plain_openai_when_disabled(self):
        _clear_caches()
        with patch.object(observability.settings, "langfuse_public_key", ""):
            with patch.object(observability.settings, "langfuse_secret_key", ""):
                client = observability.get_openai_client()
                # Plain openai client has 'chat' attribute but isn't from langfuse
                assert client.__class__.__module__.startswith("openai")
        _clear_caches()


class TestGetLangchainCallbacks:
    def test_empty_when_disabled(self):
        _clear_caches()
        with patch.object(observability.settings, "langfuse_public_key", ""):
            with patch.object(observability.settings, "langfuse_secret_key", ""):
                assert observability.get_langchain_callbacks() == []
        _clear_caches()


class TestFlush:
    def test_flush_noop_when_disabled(self):
        with patch.object(observability.settings, "langfuse_public_key", ""):
            with patch.object(observability.settings, "langfuse_secret_key", ""):
                # Should not raise
                observability.flush()


# Phase 7: resume_upload trace tests (Plan 04 — D-32 / D-33 / T-07-07 / T-07-08)


import uuid  # noqa: E402
from unittest.mock import AsyncMock, MagicMock  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from job_rag.api.app import app  # noqa: E402
from job_rag.models import (  # noqa: E402
    RemotePolicy,
    ResumeExtraction,
    UserSkill,
    UserSkillProfile,
)


def _fake_extraction() -> ResumeExtraction:
    return ResumeExtraction(
        skills=[UserSkill(name="Python"), UserSkill(name="Rust")],
        target_roles=["AI Engineer"],
        preferred_locations=["Berlin"],
        min_salary_eur=70000,
        remote_preference=RemotePolicy.REMOTE,
        years_experience=5,
    )


def _override_session_user():
    from job_rag.api.auth import get_current_user_id
    from job_rag.api.deps import get_session
    from job_rag.config import settings as _settings

    async def override_session():
        yield AsyncMock()

    async def override_user():
        return _settings.seeded_user_id

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user_id] = override_user


@pytest.mark.asyncio
async def test_resume_upload_trace_has_four_spans(sample_resume_pdf):
    """D-32 / VALIDATION 07-04-15: trace records text_extract + llm_extract
    (auto) + diff_compute on upload; profile_save attaches on PATCH when
    extraction_id matches."""
    _override_session_user()

    mock_trace = MagicMock()
    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    try:
        with patch(
            "job_rag.api.routes.get_langfuse_client", return_value=mock_lf
        ), patch(
            "job_rag.api.routes.load_profile",
            new_callable=AsyncMock,
            return_value=UserSkillProfile(skills=[]),
        ), patch(
            "job_rag.api.routes.extract_resume",
            return_value=(_fake_extraction(), {}),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/profile/upload",
                    files={
                        "file": (
                            "test.pdf",
                            sample_resume_pdf,
                            "application/pdf",
                        )
                    },
                )
                assert resp.status_code == 200, resp.text
                extraction_id = resp.json()["extraction_id"]

                r2 = await client.patch(
                    "/profile",
                    json={
                        "skills": [{"name": "Python"}],
                        "extraction_id": extraction_id,
                    },
                )
                assert r2.status_code == 200, r2.text

        # Inspect captured trace.span() calls — extract the `name` kwarg.
        span_names = []
        for call in mock_trace.span.call_args_list:
            name = call.kwargs.get("name")
            if name is None and call.args:
                name = call.args[0]
            span_names.append(name)
        assert "text_extract" in span_names, span_names
        assert "diff_compute" in span_names, span_names
        assert "profile_save" in span_names, span_names
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_resume_trace_does_not_capture_text(sample_resume_pdf):
    """D-33 / T-07-07 / VALIDATION 07-04-16: raw resume text never lands in
    span metadata.

    The fixture's text contains "TEST FIXTURE" + "synthetic data" watermarks
    (committed by Plan 01 to mitigate T-07-foundation-PII). This test
    spies on every span().end(metadata=...) call and asserts neither
    substring appears in any metadata value.
    """
    _override_session_user()

    captured_metadata: list[dict] = []

    def _record_span(*args, **kwargs):
        span = MagicMock()

        def _end(metadata=None, **kw):
            if metadata:
                captured_metadata.append(metadata)

        span.end.side_effect = _end
        return span

    mock_trace = MagicMock()
    mock_trace.span.side_effect = _record_span
    mock_lf = MagicMock()
    mock_lf.trace.return_value = mock_trace

    try:
        with patch(
            "job_rag.api.routes.get_langfuse_client", return_value=mock_lf
        ), patch(
            "job_rag.api.routes.load_profile",
            new_callable=AsyncMock,
            return_value=UserSkillProfile(skills=[]),
        ), patch(
            "job_rag.api.routes.extract_resume",
            return_value=(_fake_extraction(), {}),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/profile/upload",
                    files={
                        "file": (
                            "test.pdf",
                            sample_resume_pdf,
                            "application/pdf",
                        )
                    },
                )
                assert resp.status_code == 200, resp.text

        for md in captured_metadata:
            for value in md.values():
                if isinstance(value, str):
                    assert "TEST FIXTURE" not in value, (
                        f"raw resume text leaked into trace metadata: {md}"
                    )
                    assert "synthetic data" not in value, (
                        f"raw resume text leaked into trace metadata: {md}"
                    )
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_langfuse_fail_open_when_keys_missing(
    sample_resume_pdf, monkeypatch
):
    """T-07-08 / VALIDATION 07-04-17: missing Langfuse keys leave the upload
    flow functional; no exception, 200 response, trace simply not recorded."""
    _override_session_user()

    monkeypatch.setattr(observability.settings, "langfuse_public_key", "")
    monkeypatch.setattr(observability.settings, "langfuse_secret_key", "")
    # Clear the lru_cache so the next get_langfuse_client call re-checks env.
    observability.get_langfuse_client.cache_clear()

    try:
        with patch(
            "job_rag.api.routes.load_profile",
            new_callable=AsyncMock,
            return_value=UserSkillProfile(skills=[]),
        ), patch(
            "job_rag.api.routes.extract_resume",
            return_value=(_fake_extraction(), {}),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/profile/upload",
                    files={
                        "file": (
                            "test.pdf",
                            sample_resume_pdf,
                            "application/pdf",
                        )
                    },
                )
        assert resp.status_code == 200, resp.text
        # Sanity: extraction_id is still a valid UUID even without tracing.
        uuid.UUID(resp.json()["extraction_id"])
    finally:
        app.dependency_overrides.clear()
        observability.get_langfuse_client.cache_clear()
