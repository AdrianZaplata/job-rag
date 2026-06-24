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


# Phase 7 G-07-UAT-01: Langfuse SDK v4 migration tests.
#
# Replaces the Mock-based tests that let G-07-UAT-01 ship: a MagicMock()
# accepts any method call without raising, so `lf.trace(...)` calls looked
# fine in tests but were AttributeError on the installed Langfuse 4.x
# client. The FakeLangfuseClient below implements the v4 contract surface
# explicitly and raises AttributeError on every known v3 method name.


import uuid  # noqa: E402
from unittest.mock import AsyncMock  # noqa: E402

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from job_rag.api.app import app  # noqa: E402
from job_rag.models import (  # noqa: E402
    RemotePolicy,
    ResumeExtraction,
    UserSkill,
    UserSkillProfile,
)
from job_rag.observability import derive_langfuse_trace_id  # noqa: E402
from tests._langfuse_fake import FakeLangfuseClient  # noqa: E402


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


class TestDeriveLangfuseTraceId:
    def test_deterministic_for_same_seed(self):
        seed = uuid.UUID("11111111-1111-1111-1111-111111111111")
        id1 = derive_langfuse_trace_id(seed)
        id2 = derive_langfuse_trace_id(seed)
        assert id1 == id2
        assert len(id1) == 32
        assert all(c in "0123456789abcdef" for c in id1)

    def test_different_for_different_seeds(self):
        a = derive_langfuse_trace_id(
            uuid.UUID("11111111-1111-1111-1111-111111111111")
        )
        b = derive_langfuse_trace_id(
            uuid.UUID("22222222-2222-2222-2222-222222222222")
        )
        assert a != b


class TestRedactCurrentGenerationInput:
    def test_calls_both_update_and_set_trace_io(self):
        from job_rag.observability import redact_current_generation_input

        fake = FakeLangfuseClient()
        redact_current_generation_input(fake, char_count=42)
        gens = [k for m, k in fake.calls if m == "update_current_generation"]
        traces = [k for m, k in fake.calls if m == "set_current_trace_io"]
        assert len(gens) == 1
        assert len(traces) == 1
        assert gens[0]["input"] == {"text": "[REDACTED — char_count=42]"}
        assert traces[0]["input"] == {"text": "[REDACTED — char_count=42]"}

    def test_fail_open_when_client_raises(self):
        from job_rag.observability import redact_current_generation_input

        fake = FakeLangfuseClient(
            raise_on={"update_current_generation": RuntimeError("boom")}
        )
        # Must NOT raise:
        redact_current_generation_input(fake, char_count=99)
        # Trace-level write still attempted:
        traces = [k for m, k in fake.calls if m == "set_current_trace_io"]
        assert len(traces) == 1


class TestFakeLangfuseClient:
    def test_v3_method_names_raise_attributeerror(self):
        fake = FakeLangfuseClient()
        with pytest.raises(AttributeError, match="v3 API removed"):
            fake.trace(name="x")
        with pytest.raises(AttributeError, match="v3 API removed"):
            fake.update_current_observation(input={})

    def test_records_start_as_current_observation_calls(self):
        fake = FakeLangfuseClient()
        with fake.start_as_current_observation(
            name="foo",
            as_type="span",
            trace_context={"trace_id": "deadbeef" * 4},
            metadata={"x": 1},
        ):
            pass
        assert fake.span_names_recorded() == ["foo"]
        enter = next(k for m, k in fake.calls if m == "enter_observation")
        assert enter["trace_id"] == "deadbeef" * 4
        assert enter["metadata"] == {"x": 1}


class TestResumeUploadV4Tracing:
    """Integration tests for the v4 Langfuse trace contract on the upload
    + PATCH paths. Uses FakeLangfuseClient via dependency injection so any
    future v3 method-name regression fails CI."""

    @pytest.mark.asyncio
    async def test_post_upload_records_three_child_observations(
        self, sample_resume_pdf
    ):
        _override_session_user()
        fake = FakeLangfuseClient()
        try:
            with patch(
                "job_rag.api.routes.get_langfuse_client", return_value=fake
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
            extraction_id = uuid.UUID(resp.json()["extraction_id"])
            names = fake.span_names_recorded()
            assert names == [
                "resume_upload",
                "text_extract",
                "diff_compute",
            ], names
            first_enter = next(
                k for m, k in fake.calls if m == "enter_observation"
            )
            assert first_enter["trace_id"] == derive_langfuse_trace_id(
                extraction_id
            )
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_post_then_patch_share_trace_id(self, sample_resume_pdf):
        _override_session_user()
        fake = FakeLangfuseClient()
        try:
            with patch(
                "job_rag.api.routes.get_langfuse_client", return_value=fake
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
                    eid = resp.json()["extraction_id"]
                    r2 = await client.patch(
                        "/profile",
                        json={
                            "skills": [{"name": "Python"}],
                            "extraction_id": eid,
                        },
                    )
                    assert r2.status_code == 200, r2.text
            upload_root = next(
                k
                for m, k in fake.calls
                if m == "enter_observation" and k["name"] == "resume_upload"
            )
            save_span = next(
                k
                for m, k in fake.calls
                if m == "enter_observation" and k["name"] == "profile_save"
            )
            assert upload_root["trace_id"] == save_span["trace_id"]
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_no_resume_pii_in_recorded_payloads(
        self, sample_resume_pdf
    ):
        """T-07-07 + G-07-UAT-01 regression: raw resume bytes ('TEST FIXTURE'
        / 'synthetic data' watermarks) must NEVER appear in any recorded
        input/output/metadata. The redact_current_generation_input helper
        must ALSO have written the [REDACTED] marker to both generation
        input and trace-level input."""
        _override_session_user()
        fake = FakeLangfuseClient()
        try:
            with patch(
                "job_rag.api.routes.get_langfuse_client", return_value=fake
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

            def _flatten(obj):
                if isinstance(obj, str):
                    yield obj
                elif isinstance(obj, dict):
                    for v in obj.values():
                        yield from _flatten(v)
                elif isinstance(obj, (list, tuple)):
                    for v in obj:
                        yield from _flatten(v)

            for payload in fake.all_recorded_inputs():
                for s in _flatten(payload):
                    assert "TEST FIXTURE" not in s, f"PII leaked: {s!r}"
                    assert "synthetic data" not in s, f"PII leaked: {s!r}"

            # And the redaction helper DID overwrite both layers:
            gen_inputs = [
                k["input"]
                for m, k in fake.calls
                if m == "update_current_generation" and "input" in k
            ]
            trace_inputs = [
                k["input"]
                for m, k in fake.calls
                if m == "set_current_trace_io" and "input" in k
            ]
            assert any(
                isinstance(i, dict)
                and "[REDACTED — char_count=" in i.get("text", "")
                for i in gen_inputs
            ), gen_inputs
            assert any(
                isinstance(i, dict)
                and "[REDACTED — char_count=" in i.get("text", "")
                for i in trace_inputs
            ), trace_inputs
        finally:
            app.dependency_overrides.clear()

    @pytest.mark.asyncio
    async def test_v3_method_calls_would_fail_loudly(self):
        """SDK-regression guard. If a future PR writes ``lf.trace(...)`` in
        production code AND the test uses FakeLangfuseClient, the test
        suite catches it — fixing the why-tests-passed gap that let
        G-07-UAT-01 ship."""
        fake = FakeLangfuseClient()
        with pytest.raises(AttributeError, match="v3 API removed"):
            fake.trace(name="resume_upload")
        with pytest.raises(AttributeError, match="v3 API removed"):
            fake.update_current_observation(input={"redacted": True})

    @pytest.mark.asyncio
    async def test_fail_open_when_langfuse_disabled(
        self, sample_resume_pdf, monkeypatch
    ):
        """T-07-08: missing keys leave the upload functional, no exception."""
        _override_session_user()
        monkeypatch.setattr(
            observability.settings, "langfuse_public_key", ""
        )
        monkeypatch.setattr(
            observability.settings, "langfuse_secret_key", ""
        )
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
            uuid.UUID(resp.json()["extraction_id"])
        finally:
            app.dependency_overrides.clear()
            observability.get_langfuse_client.cache_clear()
