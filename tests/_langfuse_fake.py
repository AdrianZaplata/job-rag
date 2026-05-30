"""Contract-faithful fake of the Langfuse 4.x client surface.

Replaces the Mock-based tests that let G-07-UAT-01 slip through: a
``MagicMock()`` accepts any method call without raising, so v3 calls like
``lf.trace(...)`` looked fine in tests but were ``AttributeError``s in
production. This fake implements EXACTLY the v4 surface and raises
``AttributeError`` on every known v3 method name.

Used by ``tests/test_observability.py`` — never imported by production code.
"""
from __future__ import annotations

import contextlib
import hashlib
from typing import Any, Iterator


# v3 names that MUST raise AttributeError if accessed — keeps the next SDK
# regression from slipping through silently.
_V3_REMOVED_NAMES = frozenset({
    "trace",
    "update_current_observation",
    "span",  # was a method on trace, not Langfuse, but guard anyway
})


class _FakeObservation:
    """Stand-in for LangfuseSpan / LangfuseGeneration as a context manager."""

    def __init__(
        self,
        parent: "FakeLangfuseClient",
        name: str,
        as_type: str,
        trace_id: str | None,
        metadata: dict | None,
        input_: Any,
        output: Any,
    ) -> None:
        self._parent = parent
        self.name = name
        self.as_type = as_type
        self.trace_id = trace_id
        self.metadata = metadata or {}
        self.input = input_
        self.output = output
        self.id = f"obs-{len(parent.calls)}"

    def __enter__(self) -> "_FakeObservation":
        self._parent.calls.append((
            "enter_observation",
            {
                "name": self.name,
                "as_type": self.as_type,
                "trace_id": self.trace_id,
                "metadata": dict(self.metadata),
                "input": self.input,
            },
        ))
        self._parent._active_stack.append(self)
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self._parent.calls.append(("exit_observation", {"name": self.name}))
        self._parent._active_stack.pop()

    def update(self, **kwargs: Any) -> None:
        self._parent.calls.append((
            "observation_update",
            {"name": self.name, **kwargs},
        ))

    def end(self, **kwargs: Any) -> None:
        # v4 spans do NOT need explicit end() — the context manager handles it.
        # We still implement it so legacy patterns don't crash, but record
        # it so tests can detect lingering v3 idioms in production code.
        self._parent.calls.append((
            "observation_end_called",
            {"name": self.name, **kwargs},
        ))


class FakeLangfuseClient:
    """Fake of ``langfuse.Langfuse`` implementing the v4 contract.

    Every call is recorded in ``self.calls`` as ``(method_name, kwargs_dict)``.
    Access to any v3 method name raises ``AttributeError`` with a migration
    hint.

    Optional ``raise_on`` attribute lets tests force a specific method to
    raise — used to verify fail-open semantics.
    """

    def __init__(self, *, raise_on: dict[str, Exception] | None = None) -> None:
        self.calls: list[tuple[str, dict]] = []
        self._active_stack: list[_FakeObservation] = []
        self._raise_on = raise_on or {}
        self._authed = True

    # ---- v4 surface ----

    def create_trace_id(self, seed: str | None = None) -> str:
        if "create_trace_id" in self._raise_on:
            raise self._raise_on["create_trace_id"]
        self.calls.append(("create_trace_id", {"seed": seed}))
        if seed is None:
            return "00" * 16
        return hashlib.blake2b(seed.encode("utf-8"), digest_size=16).hexdigest()

    @contextlib.contextmanager
    def start_as_current_observation(
        self,
        *,
        name: str,
        as_type: str = "span",
        trace_context: dict | None = None,
        input: Any = None,
        output: Any = None,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> Iterator[_FakeObservation]:
        if "start_as_current_observation" in self._raise_on:
            raise self._raise_on["start_as_current_observation"]
        trace_id = (trace_context or {}).get("trace_id")
        obs = _FakeObservation(
            self,
            name=name,
            as_type=as_type,
            trace_id=trace_id,
            metadata=metadata,
            input_=input,
            output=output,
        )
        with obs:
            yield obs

    def start_observation(
        self,
        *,
        name: str,
        as_type: str = "span",
        trace_context: dict | None = None,
        metadata: dict | None = None,
        **kwargs: Any,
    ) -> _FakeObservation:
        self.calls.append(
            ("start_observation", {"name": name, "as_type": as_type})
        )
        trace_id = (trace_context or {}).get("trace_id")
        return _FakeObservation(
            self,
            name=name,
            as_type=as_type,
            trace_id=trace_id,
            metadata=metadata,
            input_=None,
            output=None,
        )

    def update_current_span(self, **kwargs: Any) -> None:
        if "update_current_span" in self._raise_on:
            raise self._raise_on["update_current_span"]
        current = self._active_stack[-1].name if self._active_stack else None
        self.calls.append(
            ("update_current_span", {"current": current, **kwargs})
        )

    def update_current_generation(self, **kwargs: Any) -> None:
        if "update_current_generation" in self._raise_on:
            raise self._raise_on["update_current_generation"]
        current = self._active_stack[-1].name if self._active_stack else None
        self.calls.append(
            ("update_current_generation", {"current": current, **kwargs})
        )

    def set_current_trace_io(self, **kwargs: Any) -> None:
        if "set_current_trace_io" in self._raise_on:
            raise self._raise_on["set_current_trace_io"]
        self.calls.append(("set_current_trace_io", kwargs))

    def get_current_trace_id(self) -> str | None:
        if not self._active_stack:
            return None
        return self._active_stack[-1].trace_id

    def get_current_observation_id(self) -> str | None:
        if not self._active_stack:
            return None
        return self._active_stack[-1].id

    def flush(self) -> None:
        self.calls.append(("flush", {}))

    def auth_check(self) -> bool:
        return self._authed

    def shutdown(self) -> None:
        self.calls.append(("shutdown", {}))

    # ---- v3 guard ----

    def __getattr__(self, name: str) -> Any:
        if name in _V3_REMOVED_NAMES:
            raise AttributeError(
                f"Langfuse v3 API removed in v4: '{name}'. "
                "Migrate to start_as_current_observation / update_current_span / "
                "update_current_generation. See observability.py docstring."
            )
        raise AttributeError(name)

    # ---- test helpers ----

    def span_names_recorded(self) -> list[str]:
        """Return the ordered list of span names that entered the context."""
        return [
            kwargs["name"]
            for method, kwargs in self.calls
            if method == "enter_observation"
        ]

    def all_recorded_inputs(self) -> list[Any]:
        """Return every input/metadata payload written via any method.

        Used by the PII-redaction test to scan for resume bytes.
        """
        payloads: list[Any] = []
        for method, kwargs in self.calls:
            for key in ("input", "output", "metadata"):
                if key in kwargs:
                    payloads.append(kwargs[key])
        return payloads
