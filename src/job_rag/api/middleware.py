"""ASGI middleware for the FastAPI app (Phase 7 D-07 / T-07-02).

``ResumeUploadSizeGuard`` enforces the 2 MB pre-body cap on
``POST /profile/upload`` BEFORE the body is materialized into memory, per
REQ-PROF-02 literal ("rejected with a 413 before the body is fully read").

The chunked-encoding fallback (no ``Content-Length`` header) is handled
inside the route handler via a size-accumulating ``read_with_cap`` loop —
this middleware only covers the headers-known-up-front case.

Mounted on the app in :mod:`job_rag.api.app` ABOVE the existing
``CORSMiddleware`` so OPTIONS preflight still flows through CORS handling
even for the upload route (the size guard only fires on POST).
"""

from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from job_rag.config import settings
from job_rag.logging import get_logger

log = get_logger(__name__)


class ResumeUploadSizeGuard(BaseHTTPMiddleware):
    """Reject oversized POST /profile/upload uploads at the headers stage.

    Inspects ``Content-Length`` BEFORE invoking the downstream handler;
    returns 413 JSON when the declared size exceeds
    ``settings.max_resume_size_bytes``. All other paths/methods pass
    through to ``call_next`` untouched. A bogus header (non-integer) is
    treated as 0 — the chunked-encoding fallback in the handler will
    catch the actual size as the body streams in.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):  # type: ignore[no-untyped-def]
        if request.url.path == "/profile/upload" and request.method == "POST":
            cl = request.headers.get("content-length")
            if cl is not None:
                try:
                    cl_int = int(cl)
                except ValueError:
                    # Bogus header — let the chunked-encoding fallback in the
                    # handler catch the real size mid-stream.
                    cl_int = 0
                if cl_int > settings.max_resume_size_bytes:
                    log.warning(
                        "resume_upload_rejected_oversized",
                        content_length=cl_int,
                        cap=settings.max_resume_size_bytes,
                    )
                    return JSONResponse(
                        status_code=413,
                        content={
                            "detail": {
                                "reason": "file_too_large",
                                "message": "Resume must be <=2 MB.",
                            }
                        },
                    )
        return await call_next(request)
