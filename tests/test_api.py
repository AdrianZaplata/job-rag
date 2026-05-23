import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from job_rag.api.app import app


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.asyncio
class TestHealthEndpoint:
    async def test_health_ok(self):
        with patch("job_rag.api.routes.get_session") as mock_dep:
            mock_session = AsyncMock()
            mock_session.execute = AsyncMock()

            async def session_gen():
                yield mock_session

            mock_dep.return_value = session_gen()
            app.dependency_overrides[
                __import__("job_rag.api.deps", fromlist=["get_session"]).get_session
            ] = lambda: session_gen()

            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # Override the dependency properly
                from job_rag.api.deps import get_session

                async def override_session():
                    yield mock_session

                app.dependency_overrides[get_session] = override_session
                response = await client.get("/health")

            app.dependency_overrides.clear()

        assert response.status_code == 200
        assert response.json()["status"] == "ok"


@pytest.mark.asyncio
class TestSearchEndpoint:
    async def test_search_no_generate(self):
        from job_rag.api.deps import get_session

        mock_session = AsyncMock()

        async def override_session():
            yield mock_session

        mock_results = [
            {
                "posting": MagicMock(
                    id=uuid.uuid4(),
                    title="AI Engineer",
                    company="TestCorp",
                    location="Berlin",
                    remote_policy="remote",
                    seniority="senior",
                ),
                "distance": 0.2,
                "similarity": 0.8,
            }
        ]

        app.dependency_overrides[get_session] = override_session

        with patch("job_rag.api.routes.search_postings", new_callable=AsyncMock) as mock_search:
            mock_search.return_value = mock_results
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                params = {"q": "RAG experience", "generate": "false"}
                response = await client.get("/search", params=params)

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "results" in data
        assert len(data["results"]) == 1
        assert data["results"][0]["company"] == "TestCorp"

    async def test_search_with_generate(self):
        from job_rag.api.deps import get_session

        mock_session = AsyncMock()

        async def override_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_session

        with patch("job_rag.api.routes.rag_query", new_callable=AsyncMock) as mock_rag:
            mock_rag.return_value = {
                "answer": "Based on the postings, TestCorp values RAG experience.",
                "sources": [{"id": "123", "title": "AI Eng", "company": "TestCorp"}],
            }
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/search", params={"q": "RAG experience"})

        app.dependency_overrides.clear()

        assert response.status_code == 200
        data = response.json()
        assert "answer" in data
        assert "sources" in data


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


@pytest.mark.asyncio
class TestAgentEndpoint:
    async def test_agent_returns_answer(self):
        with patch("job_rag.api.routes.run_agent", new_callable=AsyncMock) as mock_run:
            mock_run.return_value = {
                "query": "test",
                "answer": "Synthesized answer.",
                "tool_calls": [{"name": "search_jobs", "args": {"query": "rag"}}],
                "message_count": 3,
            }
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.post("/agent", json={"query": "test"})

        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Synthesized answer."
        assert len(data["tool_calls"]) == 1

    async def test_agent_stream_emits_sse_events(self):
        # Plan 06: stream_agent now yields Pydantic AgentEvent instances
        # (Plan 04). The route handler converts via to_sse(event). Use the
        # typed events so the route's `event.type` access works correctly.
        from asgi_lifespan import LifespanManager

        from job_rag.api.sse import FinalEvent, TokenEvent, ToolStartEvent

        async def fake_stream(_query):
            yield ToolStartEvent(
                type="tool_start", name="search_jobs", args={"query": "rag"}
            )
            yield TokenEvent(type="token", content="Hello")
            yield FinalEvent(type="final", content="Hello")

        with patch("job_rag.api.routes.stream_agent", side_effect=fake_stream):
            async with LifespanManager(app, startup_timeout=60):
                transport = ASGITransport(app=app)
                async with AsyncClient(
                    transport=transport, base_url="http://test"
                ) as client:
                    response = await client.post(
                        "/agent/stream", json={"query": "test"}
                    )
                    body = response.text

        assert response.status_code == 200
        assert "event: tool_start" in body
        assert "event: token" in body
        assert "event: final" in body


@pytest.mark.asyncio
class TestGapsEndpoint:
    async def test_gaps_no_postings(self):
        from job_rag.api.auth import get_current_user_id
        from job_rag.api.deps import get_session
        from job_rag.config import settings

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_session():
            yield mock_session

        async def override_user():
            return settings.seeded_user_id

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user_id] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/gaps")

        app.dependency_overrides.clear()

        assert response.status_code == 404


# ===== Phase 1 BACK-01 (CORS), BACK-05 (heartbeat), BACK-06 (timeout/error) =====
# Plan 06: TestCORS + TestAgentStream + test_no_gzip_middleware. The
# AgentStream tests stream the full response body up to a small byte
# budget so the test runner cannot hang on a never-finishing fake_agent.
import asyncio  # noqa: E402
import json  # noqa: E402

from asgi_lifespan import LifespanManager  # noqa: E402


@pytest.mark.asyncio
class TestCORS:
    """BACK-01: CORS middleware config per D-26."""

    async def test_preflight_localhost_5173(self):
        """Allowed origin succeeds OPTIONS preflight with the echoed origin."""
        async with LifespanManager(app, startup_timeout=60):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.options(
                    "/health",
                    headers={
                        "Origin": "http://localhost:5173",
                        "Access-Control-Request-Method": "GET",
                        "Access-Control-Request-Headers": "Authorization",
                    },
                )
        # FastAPI CORSMiddleware returns 200 for an allowed preflight.
        assert resp.status_code in (200, 204), f"preflight status: {resp.status_code}"
        assert (
            resp.headers.get("access-control-allow-origin") == "http://localhost:5173"
        )

    async def test_preflight_unknown_rejected(self):
        """Disallowed origin does NOT receive the allow-origin header."""
        async with LifespanManager(app, startup_timeout=60):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.options(
                    "/health",
                    headers={
                        "Origin": "http://evil.com",
                        "Access-Control-Request-Method": "GET",
                    },
                )
        # CORSMiddleware omits allow-origin (or returns 400) for unknown origins.
        assert resp.headers.get("access-control-allow-origin") != "http://evil.com"

    async def test_no_wildcard_origin(self):
        """Defensive: app must never be configured with `*` allow_origin (D-26)."""
        # Starlette types `m.cls` as `_MiddlewareFactory` which doesn't expose
        # `__name__` statically; runtime classes always have it. Use getattr.
        cors_mw = [
            m for m in app.user_middleware
            if getattr(m.cls, "__name__", "") == "CORSMiddleware"
        ]
        assert cors_mw, "CORSMiddleware not registered"
        # Starlette stores middleware kwargs in `.kwargs` (newer) or `.options`
        # (legacy). Try both attributes for forward compatibility.
        kwargs = getattr(cors_mw[0], "kwargs", None) or getattr(
            cors_mw[0], "options", {}
        )
        if isinstance(kwargs, dict):
            origins = kwargs.get("allow_origins")
            if origins is not None:
                assert "*" not in origins, f"Wildcard origin present: {origins}"


def test_no_gzip_middleware():
    """D-18 / Pitfall 6: GZipMiddleware must not be registered.

    sse-starlette raises NotImplementedError on compressed transfer-encoding,
    and EventSource clients receive a buffered binary blob instead of streamed
    events. The runtime introspection of `app.user_middleware` is the
    authoritative check (the source-comment grep matches anti-regression
    comments and is not a reliable signal).
    """
    # Starlette types `m.cls` as `_MiddlewareFactory` which doesn't expose
    # `__name__` statically; runtime classes always have it. Use getattr.
    names = {getattr(m.cls, "__name__", "") for m in app.user_middleware}
    assert "GZipMiddleware" not in names, f"GZipMiddleware present: {names}"


def test_ingest_route_uses_async_pipeline():
    """Regression: /ingest must call ingest_from_source (async) not ingest_file
    (sync wrapper). Plan 06 / D-24."""
    import inspect

    from job_rag.api.routes import ingest

    src = inspect.getsource(ingest)
    assert "ingest_from_source" in src, (
        "ingest route still uses sync ingest_file path — async pipeline required"
    )
    assert "MarkdownFileSource" in src, (
        "ingest route must construct MarkdownFileSource"
    )


@pytest.mark.asyncio
class TestAgentStream:
    """BACK-05 heartbeat, BACK-06 timeout, D-18 headers, D-19 sanitization."""

    async def _stream_bytes(
        self,
        monkeypatch,
        fake_agent,
        *,
        timeout_seconds=None,
        heartbeat_seconds=None,
        max_bytes=8192,
        client_timeout=10.0,
    ):
        """Helper: start /agent/stream and read up to max_bytes bytes.

        Mutates settings via monkeypatch so the timeout/heartbeat values are
        bounded for CI wall-clock; pytest restores them after the test.
        Patches `job_rag.api.routes.stream_agent` (the imported symbol the
        route handler closes over) rather than `job_rag.agent.stream` so the
        replacement actually takes effect.
        """
        from job_rag.config import settings as _settings

        if timeout_seconds is not None:
            monkeypatch.setattr(_settings, "agent_timeout_seconds", timeout_seconds)
        if heartbeat_seconds is not None:
            monkeypatch.setattr(
                _settings, "heartbeat_interval_seconds", heartbeat_seconds
            )
        monkeypatch.setattr("job_rag.api.routes.stream_agent", fake_agent)

        async with LifespanManager(app, startup_timeout=60):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test", timeout=client_timeout
            ) as client:
                async with client.stream(
                    "POST", "/agent/stream", json={"query": "test"}
                ) as resp:
                    content = b""
                    try:
                        async for chunk in resp.aiter_bytes():
                            content += chunk
                            if len(content) >= max_bytes:
                                break
                    except (RuntimeError, StopAsyncIteration):
                        # The fake_hanging_agent path closes the stream after
                        # the timeout error frame; httpx may surface this as
                        # a benign RuntimeError — we have what we need.
                        pass
                    return resp, content.decode("utf-8", errors="replace")

    async def test_heartbeat_emitted(self, monkeypatch):
        """D-15 / BACK-05: heartbeat frame visible at the configured cadence.

        sse-starlette enforces ``ping >= 1`` (int seconds). The fixture's
        100ms-per-yield pace is faster than the minimum heartbeat interval,
        so the stream completes before a single heartbeat would fire — for
        this test we use a custom agent that pauses ~2.5s between yields
        so at least one 1s-interval heartbeat reliably interleaves.
        """
        from job_rag.api.sse import FinalEvent, TokenEvent

        async def slow_agent(_q):
            await asyncio.sleep(2.5)
            yield TokenEvent(type="token", content="slow")
            yield FinalEvent(type="final", content="slow")

        resp, body = await self._stream_bytes(
            monkeypatch,
            slow_agent,
            heartbeat_seconds=1,
            timeout_seconds=10,
            max_bytes=8192,
            client_timeout=15.0,
        )
        assert resp.status_code == 200
        assert "event: heartbeat" in body or '"type":"heartbeat"' in body, (
            f"no heartbeat event in stream body: {body[:500]}"
        )

    async def test_timeout_emits_error(self, monkeypatch, fake_hanging_agent):
        """BACK-06 / D-16: fake_hanging_agent + 1s timeout -> error frame."""
        resp, body = await self._stream_bytes(
            monkeypatch,
            fake_hanging_agent,
            timeout_seconds=1,
            heartbeat_seconds=10,
            max_bytes=4096,
            client_timeout=10.0,
        )
        assert resp.status_code == 200
        assert "event: error" in body, f"no error event: {body[:500]}"
        assert '"reason":"agent_timeout"' in body, (
            f"no agent_timeout reason in body: {body[:500]}"
        )

    async def test_internal_exception_sanitized(self, monkeypatch):
        """D-19 / T-06-01: unhandled exception emitted as sanitized error event.

        _sanitize bounds the message to 200 chars and strips newline / CR
        characters. It operates on `str(exc)` — Python's exception str() does
        NOT include the formatted "Traceback (most recent call last):" header
        (that comes from `traceback.format_exc()` which the route handler does
        not invoke). The test asserts the documented invariants: no newlines /
        CRs in the wire-format message, length bound respected, and the
        absence of stack-frame markers (`File "..."` / line N / `in <fn>`)
        that only appear in formatted tracebacks.
        """

        async def exploding_agent(_q):
            # Multiline message with embedded line breaks + a long body that
            # exceeds the 200-char bound. _sanitize must collapse newlines to
            # spaces and truncate at 200 chars.
            raise RuntimeError(
                "secret leak: line one\n"
                "line two with /etc/passwd path\r\n"
                + ("padding " * 100)  # forces length truncation
            )
            yield  # unreachable; declares this as an async generator

        resp, body = await self._stream_bytes(
            monkeypatch,
            exploding_agent,
            timeout_seconds=10,
            heartbeat_seconds=10,
            max_bytes=8192,
            client_timeout=10.0,
        )
        assert '"reason":"internal"' in body, f"no internal reason: {body[:500]}"
        # Pull the first error frame's data and assert sanitization invariants.
        for line in body.splitlines():
            if not line.startswith("data: "):
                continue
            try:
                data = json.loads(line[len("data: "):])
            except json.JSONDecodeError:
                continue
            if data.get("type") == "error" and data.get("reason") == "internal":
                msg = data.get("message", "")
                assert "\n" not in msg, f"newline in sanitized msg: {msg!r}"
                assert "\r" not in msg, f"CR in sanitized msg: {msg!r}"
                assert len(msg) <= 200, f"msg too long: {len(msg)} chars"
                # _sanitize only operates on `str(exc)` — it never invokes
                # traceback.format_exc, so stack-frame markers should never
                # be present unless the user's exception message contains
                # them literally. This test crafts an exception without
                # those markers, so they must not appear.
                assert 'File "' not in msg, (
                    f"stack frame leaked: {msg!r}"
                )
                return
        pytest.fail(
            f"no error/internal frame with sanitized message: {body[:500]}"
        )

    async def test_content_encoding_identity(self, monkeypatch, fake_slow_agent):
        """D-18 / Pitfall 6: response declares Content-Encoding: identity."""
        resp, _ = await self._stream_bytes(
            monkeypatch,
            fake_slow_agent,
            timeout_seconds=10,
            heartbeat_seconds=10,
            max_bytes=512,
        )
        assert resp.headers.get("content-encoding") == "identity"

    async def test_x_accel_buffering(self, monkeypatch, fake_slow_agent):
        """D-18: response declares X-Accel-Buffering: no (nginx hint)."""
        resp, _ = await self._stream_bytes(
            monkeypatch,
            fake_slow_agent,
            timeout_seconds=10,
            heartbeat_seconds=10,
            max_bytes=512,
        )
        assert resp.headers.get("x-accel-buffering") == "no"


# ===== Phase 5 Wave 0 - dashboard endpoint scaffold =====


def _dashboard_routes_present() -> bool:
    """Skip-guard for TestDashboardEndpoints.

    Probes the OpenAPI for /dashboard/top-skills registration. Plan 05-03
    will land the routes; until then the entire TestDashboardEndpoints class
    skips cleanly without ImportError at collection time.
    """
    try:
        paths = app.openapi().get("paths", {})
        return "/dashboard/top-skills" in paths
    except Exception:  # noqa: BLE001 - any failure means routes aren't shipped
        return False


@pytest.mark.skipif(
    not _dashboard_routes_present(),
    reason="Phase 5 /dashboard/* routes not yet shipped (Plan 05-03)",
)
@pytest.mark.asyncio
class TestDashboardEndpoints:
    """Phase 5 Plan 05-03 dashboard endpoint integration tests.

    Pattern (per Plan 05-02 SUMMARY guidance): MagicMock+AsyncMock for the
    AsyncSession dependency, monkeypatch the analytics callees (bound names in
    routes.py) so the SQL pipeline never runs. ASGITransport+AsyncClient drives
    the FastAPI handler end-to-end.

    Each test clears `app.dependency_overrides` at the end (existing pattern
    from TestMatchEndpoint) to prevent override leak across tests.
    """

    async def test_top_skills_returns_200_with_pydantic_shape(self):
        from job_rag.api.auth import get_current_user_id
        from job_rag.api.deps import get_session
        from job_rag.config import settings

        async def override_session():
            yield AsyncMock()

        async def override_user():
            return settings.seeded_user_id

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user_id] = override_user

        mock_result = {
            "skills": [
                {"skill": "Python", "must_count": 5, "nice_count": 2, "total": 7},
            ],
            "total_postings": 10,
            "unique_skills": 1,
        }

        with patch(
            "job_rag.api.routes.analytics_top_skills",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/dashboard/top-skills?country=DE")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert "skills" in body
        assert "total_postings" in body
        assert "unique_skills" in body
        assert body["total_postings"] == 10
        assert body["unique_skills"] == 1
        assert body["skills"][0]["skill"] == "Python"
        assert body["skills"][0]["must_count"] == 5
        assert body["skills"][0]["nice_count"] == 2
        assert body["skills"][0]["total"] == 7

    async def test_salary_bands_returns_200_with_pydantic_shape(self):
        from job_rag.api.auth import get_current_user_id
        from job_rag.api.deps import get_session
        from job_rag.config import settings

        async def override_session():
            yield AsyncMock()

        async def override_user():
            return settings.seeded_user_id

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user_id] = override_user

        mock_result = {
            "p25": 60000,
            "p50": 75000,
            "p75": 90000,
            "postings_with_salary": 8,
            "total_postings": 12,
            "currency": "EUR",
        }

        with patch(
            "job_rag.api.routes.analytics_salary_bands",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/dashboard/salary-bands?country=DE")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["currency"] == "EUR"
        assert body["p25"] == 60000
        assert body["p50"] == 75000
        assert body["p75"] == 90000
        assert body["postings_with_salary"] == 8
        assert body["total_postings"] == 12

    async def test_cv_vs_market_returns_200_with_pydantic_shape(self):
        from job_rag.api.auth import get_current_user_id
        from job_rag.api.deps import get_session
        from job_rag.config import settings

        async def override_session():
            yield AsyncMock()

        async def override_user():
            return settings.seeded_user_id

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user_id] = override_user

        mock_result = {
            "mean_score": 0.42,
            "postings_compared": 98,
            "top_missing_must_have": [
                {"skill": "AWS", "count": 42, "percentage": 42.9},
            ],
        }

        with patch(
            "job_rag.api.routes.analytics_cv_match",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get("/dashboard/cv-vs-market?country=DE")

        app.dependency_overrides.clear()

        assert response.status_code == 200
        body = response.json()
        assert body["mean_score"] == 0.42
        assert body["postings_compared"] == 98
        assert len(body["top_missing_must_have"]) == 1
        assert body["top_missing_must_have"][0]["skill"] == "AWS"
        assert body["top_missing_must_have"][0]["count"] == 42
        assert body["top_missing_must_have"][0]["percentage"] == 42.9

    async def test_unauthed_request_returns_401(self):
        """T-AUTH-06 carry-forward: Depends(get_current_user_id) rejects unauthed.

        Without overriding get_current_user_id, the real dep delegates to
        fastapi-azure-auth's azure_scheme which rejects requests lacking a
        valid Bearer token. Phase 4 D-08 returns 401 (no token) or 403
        (wrong oid). Assert NOT 200.
        """
        # Clear any leaked overrides; do NOT set get_current_user_id override
        app.dependency_overrides.clear()

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/top-skills")

        # 401 (no token) or 403 (wrong oid) -- never 200
        assert response.status_code in (401, 403), (
            f"unauthed dashboard request returned {response.status_code}; "
            f"expected 401 or 403. Body: {response.text}"
        )

    async def test_invalid_country_returns_422(self):
        """T-INPUT-VALIDATION: ?country=ZZ -> 422 (Pydantic enum rejects bad strings)."""
        from job_rag.api.auth import get_current_user_id
        from job_rag.api.deps import get_session
        from job_rag.config import settings

        async def override_session():
            yield AsyncMock()

        async def override_user():
            return settings.seeded_user_id

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user_id] = override_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/dashboard/top-skills?country=ZZ")

        app.dependency_overrides.clear()

        assert response.status_code == 422, (
            f"expected 422, got {response.status_code}: {response.text}"
        )

    async def test_country_filter_exercises_4_values(self):
        """E12 - country filter exercises PL / DE / EU / WW; each returns 200.

        Plan 05-02's TestFilterEffects already asserts distinct numeric outputs
        per filter value; this test only confirms the enum accepts all four
        canonical values without 422.
        """
        from job_rag.api.auth import get_current_user_id
        from job_rag.api.deps import get_session
        from job_rag.config import settings

        async def override_session():
            yield AsyncMock()

        async def override_user():
            return settings.seeded_user_id

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user_id] = override_user

        mock_result = {"skills": [], "total_postings": 0, "unique_skills": 0}

        with patch(
            "job_rag.api.routes.analytics_top_skills",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                for country in ("PL", "DE", "EU", "WW"):
                    response = await client.get(f"/dashboard/top-skills?country={country}")
                    assert response.status_code == 200, (
                        f"country={country} failed: {response.status_code} {response.text}"
                    )

        app.dependency_overrides.clear()

    async def test_top_skills_openapi_named_schema(self):
        """PATTERNS B.2: assert components.schemas.DashboardTopSkillsResponse exists.

        Drives openapi-typescript codegen toward named TS interfaces rather
        than inline `Record<string, unknown>` types.
        """
        schema = app.openapi()
        assert "DashboardTopSkillsResponse" in schema["components"]["schemas"]
        assert "DashboardSalaryBandsResponse" in schema["components"]["schemas"]
        assert "DashboardCvMatchResponse" in schema["components"]["schemas"]

        # The /dashboard/top-skills 200 response references the named schema via $ref
        top_skills_resp = schema["paths"]["/dashboard/top-skills"]["get"]["responses"]["200"]
        json_content = top_skills_resp["content"]["application/json"]["schema"]
        # Pydantic v2 emits either a direct $ref or an allOf wrapping a $ref.
        ref_value = json_content.get("$ref") or (
            json_content.get("allOf", [{}])[0].get("$ref") if json_content.get("allOf") else None
        )
        assert ref_value == "#/components/schemas/DashboardTopSkillsResponse", (
            f"expected $ref to DashboardTopSkillsResponse, got: {json_content}"
        )

    async def test_d12_zero_postings_returns_200_not_404(self):
        """D-12 / E1: zero-posting filter -> HTTP 200 with zero-state body, NOT 404.

        Dashboard endpoints have a different contract than /gaps: they DO NOT
        raise HTTPException(404) when filters match zero postings; the zero
        state is a legitimate (and frequently observed) UI condition.
        """
        from job_rag.api.auth import get_current_user_id
        from job_rag.api.deps import get_session
        from job_rag.config import settings

        async def override_session():
            yield AsyncMock()

        async def override_user():
            return settings.seeded_user_id

        app.dependency_overrides[get_session] = override_session
        app.dependency_overrides[get_current_user_id] = override_user

        mock_result = {
            "mean_score": None,
            "postings_compared": 0,
            "top_missing_must_have": [],
        }

        with patch(
            "job_rag.api.routes.analytics_cv_match",
            new_callable=AsyncMock,
            return_value=mock_result,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/dashboard/cv-vs-market?country=PL&seniority=lead"
                )

        app.dependency_overrides.clear()

        assert response.status_code == 200  # NOT 404
        body = response.json()
        assert body["mean_score"] is None
        assert body["postings_compared"] == 0
        assert body["top_missing_must_have"] == []
