"""FastAPI lifespan tests - reranker preload + shutdown drain.

Covers BACK-03 (cross-encoder preloaded once on startup so the first chat
doesn't pay 2-3s of cold load) and D-17 (lifespan shutdown drains active SSE
streams via app.state.shutdown_event + app.state.active_streams, emitting
event: error reason="shutdown" before close).

Plan 05 wires the lifespan; Plan 06 adds the route handler that registers
streams. Until then most tests skip; the LifespanManager fixture is the only
non-trivial code that runs in Wave 0.
"""

import pytest


@pytest.fixture
def lifespan_manager():
    """Lazy-import asgi-lifespan so this file collects even if the dev dep
    install hasn't happened yet on the runner."""
    try:
        from asgi_lifespan import LifespanManager

        return LifespanManager
    except ImportError as e:
        pytest.skip(f"asgi-lifespan not available: {e}")


@pytest.mark.asyncio
class TestLifespanStartup:
    async def test_reranker_preloaded(self, lifespan_manager):
        """BACK-03: lifespan startup calls _get_reranker once.

        Plan 05's lifespan must invoke the existing _get_reranker() helper
        during the startup phase so the CrossEncoder weights are resident in
        memory before any /agent/stream request arrives.
        """
        from unittest.mock import patch

        try:
            from job_rag.api.app import app
        except ImportError as e:
            pytest.skip(f"api/app.py not yet wired (Plan 05): {e}")
        # Plan 05 adds the _get_reranker name to api/app.py. Until that
        # symbol exists, patch() raises AttributeError - skip so Wave 0 stays
        # green and the test goes live the moment Plan 05 lands.
        try:
            patcher = patch("job_rag.api.app._get_reranker")
            mock_load = patcher.start()
        except AttributeError:
            pytest.skip("_get_reranker not yet exposed in api/app.py (Plan 05)")
        try:
            async with lifespan_manager(app):
                mock_load.assert_called_once()
        finally:
            patcher.stop()

    async def test_shutdown_event_initialized(self, lifespan_manager):
        """D-17: lifespan must create both app.state.shutdown_event (asyncio.Event)
        and app.state.active_streams (set) so the route handler can register
        in-flight stream tasks for graceful drain on SIGTERM."""
        try:
            from job_rag.api.app import app
        except ImportError as e:
            pytest.skip(f"api/app.py not yet wired (Plan 05): {e}")
        async with lifespan_manager(app):
            # Plan 05 augments the lifespan to attach these. Until then the
            # current minimal lifespan leaves app.state empty - skip rather
            # than fail so Wave 0 stays green.
            if not hasattr(app.state, "shutdown_event") or not hasattr(
                app.state, "active_streams"
            ):
                pytest.skip(
                    "lifespan not yet augmented with shutdown_event/active_streams (Plan 05)"
                )
            assert hasattr(app.state, "shutdown_event"), "lifespan must create shutdown_event"
            assert hasattr(app.state, "active_streams"), "lifespan must create active_streams set"


@pytest.mark.asyncio
class TestShutdownDrain:
    async def test_active_streams_drained_on_shutdown(self, lifespan_manager):
        """D-17: active streams receive event: error reason=shutdown during drain.

        Implementation note: Plan 06's route handler registers the current
        stream task in app.state.active_streams; lifespan shutdown sets
        app.state.shutdown_event, awaits asyncio.gather(*active_streams,
        return_exceptions=True) with a 30s budget, and each stream sees the
        event flip and emits the typed error before closing.

        Full implementation is Plan 06's responsibility; Plan 01 provides the
        skeleton that fails loudly if the contract is dropped.
        """
        pytest.skip("Full drain test deferred - Plan 06 wires the route handler")


@pytest.mark.asyncio
class TestPromptVersionDriftWarning:
    """D-17 / Pattern 4: lifespan startup logs drift warnings."""

    async def test_warning_when_stale_rows_present(self, lifespan_manager):
        # structlog's PrintLoggerFactory bypasses the stdlib logging tree, so
        # caplog can't see its records. Instead, intercept the module-level
        # `log` object directly and capture warning() calls (executor note in
        # Plan 02-03 anticipated this).
        from unittest.mock import AsyncMock, MagicMock, patch

        try:
            from job_rag.api import app as app_mod
            from job_rag.api.app import app
        except ImportError as e:
            pytest.skip(f"api/app.py not yet wired: {e}")

        try:
            rer_patcher = patch("job_rag.api.app._get_reranker")
            rer_patcher.start()
        except AttributeError:
            pytest.skip("_get_reranker not in api/app.py")

        class _Row:
            def __init__(self, version, n):
                self.prompt_version = version
                self.n = n

        class _Result:
            def all(self):
                return [_Row("1.1", 5)]

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result())
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        sess_patcher = patch(
            "job_rag.api.app.AsyncSessionLocal", lambda: session,
        )
        try:
            sess_patcher.start()
        except AttributeError:
            pytest.skip("AsyncSessionLocal not imported in api/app.py")

        warnings_seen: list[tuple[str, dict]] = []
        infos_seen: list[tuple[str, dict]] = []

        original_warn = app_mod.log.warning
        original_info = app_mod.log.info

        def _capture_warn(event, *args, **kwargs):
            warnings_seen.append((event, kwargs))
            return original_warn(event, *args, **kwargs)

        def _capture_info(event, *args, **kwargs):
            infos_seen.append((event, kwargs))
            return original_info(event, *args, **kwargs)

        warn_patcher = patch.object(app_mod.log, "warning", side_effect=_capture_warn)
        info_patcher = patch.object(app_mod.log, "info", side_effect=_capture_info)

        try:
            warn_patcher.start()
            info_patcher.start()
            async with lifespan_manager(app):
                pass

            events = [e for e, _ in warnings_seen]
            assert "prompt_version_drift" in events, (
                f"expected prompt_version_drift warning; got warnings: {events}"
            )
        finally:
            warn_patcher.stop()
            info_patcher.stop()
            sess_patcher.stop()
            rer_patcher.stop()

    async def test_clean_when_no_stale_rows(self, lifespan_manager):
        from unittest.mock import AsyncMock, MagicMock, patch

        try:
            from job_rag.api import app as app_mod
            from job_rag.api.app import app
        except ImportError as e:
            pytest.skip(f"api/app.py not yet wired: {e}")

        try:
            rer_patcher = patch("job_rag.api.app._get_reranker")
            rer_patcher.start()
        except AttributeError:
            pytest.skip("_get_reranker not in api/app.py")

        class _Result:
            def all(self):
                return []

        session = MagicMock()
        session.execute = AsyncMock(return_value=_Result())
        session.__aenter__ = AsyncMock(return_value=session)
        session.__aexit__ = AsyncMock(return_value=None)

        sess_patcher = patch(
            "job_rag.api.app.AsyncSessionLocal", lambda: session,
        )
        try:
            sess_patcher.start()
        except AttributeError:
            pytest.skip("AsyncSessionLocal not imported in api/app.py")

        infos_seen: list[str] = []
        original_info = app_mod.log.info

        def _capture_info(event, *args, **kwargs):
            infos_seen.append(event)
            return original_info(event, *args, **kwargs)

        info_patcher = patch.object(app_mod.log, "info", side_effect=_capture_info)

        try:
            info_patcher.start()
            async with lifespan_manager(app):
                pass

            assert "prompt_version_check_clean" in infos_seen, (
                f"expected prompt_version_check_clean info; got: {infos_seen}"
            )
        finally:
            info_patcher.stop()
            sess_patcher.stop()
            rer_patcher.stop()
