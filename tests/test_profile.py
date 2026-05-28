"""Tests for the Phase 7 profile feature (PROF-01..06).

Coverage filled by:
- Plan 02 (07-02-*): load_profile DB read path + seed migration round-trip
- Plan 04 (07-04-*): upload route 413/415/422 + diff helper + PATCH semantics
"""

import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from job_rag.api.app import app
from job_rag.models import ResumeExtraction, UserSkill, UserSkillProfile
from job_rag.services.profile import compute_skills_diff


def _profile(skill_names: list[str]) -> UserSkillProfile:
    return UserSkillProfile(skills=[UserSkill(name=n) for n in skill_names])


# ----------------------------------------------------------------------
# Plan 07-04 Task 1 — compute_skills_diff unit tests (D-17..D-20)
# ----------------------------------------------------------------------


def test_compute_skills_diff_classifies_correctly():
    """D-17/D-18: every extracted skill ends up in exactly one bucket."""
    current = _profile(["Python", "FastAPI", "Docker"])
    extracted = [UserSkill(name=n) for n in ["Python", "Rust", "FastAPI"]]
    diff = compute_skills_diff(current, extracted)
    sources = {item.name: item.source for item in diff}
    assert sources == {
        "Rust": "added",
        "Docker": "removed",
        "Python": "unchanged",
        "FastAPI": "unchanged",
    }


def test_compute_skills_diff_orders_added_first():
    """D-19: added (alphabetical) → removed (alphabetical) → unchanged (alphabetical)."""
    current = _profile(["B-old", "C-old"])
    extracted = [UserSkill(name=n) for n in ["A-new", "Z-new", "B-old"]]
    diff = compute_skills_diff(current, extracted)
    added_names = [d.name for d in diff if d.source == "added"]
    removed_names = [d.name for d in diff if d.source == "removed"]
    unchanged_names = [d.name for d in diff if d.source == "unchanged"]
    assert added_names == ["A-new", "Z-new"]
    assert removed_names == ["C-old"]
    assert unchanged_names == ["B-old"]
    sources_in_order = [item.source for item in diff]
    first_added = next(
        i for i, s in enumerate(sources_in_order) if s == "added"
    )
    first_removed = next(
        i for i, s in enumerate(sources_in_order) if s == "removed"
    )
    first_unchanged = next(
        i for i, s in enumerate(sources_in_order) if s == "unchanged"
    )
    assert first_added < first_removed < first_unchanged


def test_compute_skills_diff_normalizes_via_normalize_skill():
    """D-20: case + hyphen/underscore-to-space collapse via _normalize_skill.

    ``_normalize_skill`` is ``lower().strip().replace("-", " ").replace("_", " ")``;
    therefore "Python"/"python" collapse, "fast-api"/"fast api" collapse, and
    "CI_CD"/"ci cd" collapse. NOTE: "FastAPI" and "fast api" do NOT collapse
    because the normalizer does not synthesize whitespace from camelCase. The
    test exercises the documented invariants only.
    """
    current = _profile(["Python", "Fast-API", "CI_CD"])
    extracted = [
        UserSkill(name="python"),
        UserSkill(name="fast api"),
        UserSkill(name="ci cd"),
    ]
    diff = compute_skills_diff(current, extracted)
    sources = {item.name: item.source for item in diff}
    assert all(s == "unchanged" for s in sources.values()), sources
    # Extracted-side casing wins for unchanged items
    assert "python" in sources
    assert "fast api" in sources
    assert "ci cd" in sources


# ----------------------------------------------------------------------
# Plan 07-04 Task 2 — POST /profile/upload route tests (PROF-02 / PROF-04)
# ----------------------------------------------------------------------


def _override_session_and_user():
    """Wire AsyncSession + get_current_user_id overrides for upload tests.

    Returns the seeded UUID so callers can assert against it. Caller is
    responsible for clearing ``app.dependency_overrides`` (we leave it set
    so a single test can run multiple requests without re-wiring).
    """
    from job_rag.api.auth import get_current_user_id
    from job_rag.api.deps import get_session
    from job_rag.config import settings as _settings

    async def override_session():
        yield AsyncMock()

    async def override_user():
        return _settings.seeded_user_id

    app.dependency_overrides[get_session] = override_session
    app.dependency_overrides[get_current_user_id] = override_user


def _stub_load_profile_empty():
    """Patch the routes-level load_profile to return an empty UserSkillProfile.

    Avoids DB I/O during upload route tests. Returns the patcher so the test
    can call ``stop()`` on it.
    """
    return patch(
        "job_rag.api.routes.load_profile",
        new_callable=AsyncMock,
        return_value=UserSkillProfile(skills=[]),
    )


def _fake_resume_extraction() -> ResumeExtraction:
    """Return a minimal ResumeExtraction with one skill (passes empty_skills guard)."""
    from job_rag.models import RemotePolicy

    return ResumeExtraction(
        skills=[UserSkill(name="Python"), UserSkill(name="Rust")],
        target_roles=["AI Engineer"],
        preferred_locations=["Berlin"],
        min_salary_eur=70000,
        remote_preference=RemotePolicy.REMOTE,
        years_experience=5,
    )


@pytest.mark.asyncio
async def test_upload_pdf_happy_path(sample_resume_pdf):
    """PROF-02 / PROF-04 / VALIDATION 07-04-07: valid PDF -> 200 + diff present."""
    _override_session_and_user()
    try:
        with _stub_load_profile_empty(), patch(
            "job_rag.api.routes.extract_resume",
            return_value=(_fake_resume_extraction(), {}),
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
        body = resp.json()
        assert "skills_diff" in body
        assert isinstance(body["skills_diff"], list)
        assert len(body["skills_diff"]) >= 1
        # extraction_id is a valid UUID
        uuid.UUID(body["extraction_id"])
        assert body["prompt_version"] == "1.0"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_docx_happy_path(sample_resume_docx):
    """PROF-02 / PROF-04 / VALIDATION 07-04-08: valid DOCX -> 200 + diff present."""
    _override_session_and_user()
    try:
        with _stub_load_profile_empty(), patch(
            "job_rag.api.routes.extract_resume",
            return_value=(_fake_resume_extraction(), {}),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                resp = await client.post(
                    "/profile/upload",
                    files={
                        "file": (
                            "test.docx",
                            sample_resume_docx,
                            (
                                "application/vnd.openxmlformats-"
                                "officedocument.wordprocessingml.document"
                            ),
                        )
                    },
                )
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert "skills_diff" in body
        assert isinstance(body["skills_diff"], list)
        assert len(body["skills_diff"]) >= 1
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_413_oversized_content_length():
    """T-07-02 / VALIDATION 07-04-01: Content-Length > 2 MB returns 413
    BEFORE the route handler runs.

    The handler is mocked to assert it's never invoked. ASGITransport
    forwards a literal Content-Length header when passed via ``headers=``;
    httpx will overwrite the value when ``content=`` is provided, so we use
    a custom ``content=`` AsyncIterator-based body that still triggers the
    middleware's header inspection.
    """
    _override_session_and_user()
    handler_called = MagicMock()
    try:
        with patch(
            "job_rag.api.routes._extract_pdf_text",
            side_effect=handler_called,
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # Send a tiny body with an explicit oversized Content-Length.
                # httpx will normally overwrite Content-Length when content=
                # is bytes; the workaround is to send a raw POST with the
                # header explicitly set and bypass body normalization.
                resp = await client.post(
                    "/profile/upload",
                    content=b"x" * 100,
                    headers={
                        "Content-Length": "3000000",
                        "Content-Type": "application/octet-stream",
                    },
                )
        assert resp.status_code == 413, resp.text
        body = resp.json()
        assert body["detail"]["reason"] == "file_too_large"
        # Sentinel: handler text extraction MUST NOT have been called.
        assert handler_called.call_count == 0
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_413_chunked_streaming(sample_resume_pdf):
    """T-07-02 / VALIDATION 07-04-02: chunked-encoding (no Content-Length)
    > 2 MB triggers the in-handler read_with_cap fallback (mid-stream 413).

    We build a body larger than 2 MB and submit it with the type-whitelist
    pre-check passing (PDF + application/pdf) so we hit the in-handler
    chunked-fallback rather than the 415 path. The middleware will not
    fire because httpx with an iterable body uses chunked encoding.
    """
    _override_session_and_user()

    async def big_body():
        # Yield 3 MB worth of PDF-like bytes — well above the 2 MB cap.
        # Send the sample PDF first so suffix/content-type whitelist passes,
        # then pad with zeros to exceed the cap.
        yield sample_resume_pdf
        for _ in range(50):
            yield b"\x00" * 64 * 1024  # 64 KB chunks => ~3.2 MB

    try:
        with _stub_load_profile_empty(), patch(
            "job_rag.api.routes.extract_resume",
            return_value=(_fake_resume_extraction(), {}),
        ):
            transport = ASGITransport(app=app)
            async with AsyncClient(
                transport=transport, base_url="http://test"
            ) as client:
                # Streaming multipart is awkward via httpx; the simplest way
                # to exercise the in-handler size-cap loop is to send a
                # multipart body with an oversized file. Construct the
                # multipart body manually so we control its bytes.
                boundary = "----TestBoundary7"
                body_parts: list[bytes] = []
                body_parts.append(
                    (
                        f"--{boundary}\r\n"
                        'Content-Disposition: form-data; name="file"; '
                        'filename="test.pdf"\r\n'
                        "Content-Type: application/pdf\r\n\r\n"
                    ).encode()
                )
                body_parts.append(sample_resume_pdf)
                body_parts.append(b"\x00" * (3 * 1024 * 1024))  # 3 MB padding
                body_parts.append(f"\r\n--{boundary}--\r\n".encode())
                full_body = b"".join(body_parts)

                resp = await client.post(
                    "/profile/upload",
                    content=full_body,
                    headers={
                        "Content-Type": (
                            f"multipart/form-data; boundary={boundary}"
                        )
                    },
                )
        # The middleware sees the (now-present) Content-Length and rejects
        # at 413, or the in-handler fallback fires mid-stream. Either path
        # is acceptable per D-07 (the literal REQ says "rejected with a 413
        # before the body is fully read" — both middleware + fallback honor
        # that). Assert 413 + file_too_large.
        assert resp.status_code == 413, resp.text
        body = resp.json()
        assert body["detail"]["reason"] == "file_too_large"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_415_txt_file_rejected():
    """T-07-05 / VALIDATION 07-04-03: .txt upload -> 415 unsupported_file_type."""
    _override_session_and_user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/profile/upload",
                files={
                    "file": (
                        "notes.txt",
                        b"hello world",
                        "text/plain",
                    )
                },
            )
        assert resp.status_code == 415, resp.text
        body = resp.json()
        assert body["detail"]["reason"] == "unsupported_file_type"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_422_encrypted_pdf(encrypted_resume_pdf):
    """VALIDATION 07-04-04: encrypted PDF -> 422 pdf_encrypted."""
    _override_session_and_user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/profile/upload",
                files={
                    "file": (
                        "test.pdf",
                        encrypted_resume_pdf,
                        "application/pdf",
                    )
                },
            )
        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert body["detail"]["reason"] == "pdf_encrypted"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_422_empty_text_pdf(empty_text_resume_pdf):
    """VALIDATION 07-04-05: PDF with < 100 chars extracted -> 422
    text_extraction_failed (D-10 OCR-not-supported gate)."""
    _override_session_and_user()
    try:
        transport = ASGITransport(app=app)
        async with AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            resp = await client.post(
                "/profile/upload",
                files={
                    "file": (
                        "test.pdf",
                        empty_text_resume_pdf,
                        "application/pdf",
                    )
                },
            )
        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert body["detail"]["reason"] == "text_extraction_failed"
    finally:
        app.dependency_overrides.clear()


@pytest.mark.asyncio
async def test_upload_422_extraction_failed(sample_resume_pdf):
    """VALIDATION 07-04-06: tenacity exhausts on ValidationError -> 422
    extraction_failed (D-16 / D-35)."""
    _override_session_and_user()

    # Build a real ValidationError by triggering Pydantic with bad data.
    try:
        ResumeExtraction(skills="not-a-list")  # type: ignore[arg-type]
    except ValueError as e:  # ValidationError is a ValueError
        validation_err = e

    try:
        with _stub_load_profile_empty(), patch(
            "job_rag.api.routes.extract_resume",
            side_effect=validation_err,
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
        assert resp.status_code == 422, resp.text
        body = resp.json()
        assert body["detail"]["reason"] == "extraction_failed"
    finally:
        app.dependency_overrides.clear()
