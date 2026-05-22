"""API authentication and rate limiting.

Phase 4 rewrites get_current_user_id() body to validate Entra JWT + guard against
non-allowlisted oid. Module-level azure_scheme instance handles JWT validation
(signature, iss, aud, exp, JWKS) once per request.

CIAM/External ID note: SingleTenantAzureAuthorizationCodeBearer does NOT support
overriding the openid_config_url; its discovery endpoint is hard-coded to
login.microsoftonline.com (workforce). For Entra External ID (ciamlogin.com)
the correct class is B2CMultiTenantAuthorizationCodeBearer, which accepts
openid_config_url precisely for this case. See Phase 4 CONTEXT.md D-07 amendment
and RESEARCH.md Open Question Q1.
"""
import hmac
import time
import uuid
from collections import defaultdict

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi_azure_auth import B2CMultiTenantAuthorizationCodeBearer
from fastapi_azure_auth.user import User

from job_rag.config import settings
from job_rag.logging import get_logger

log = get_logger(__name__)

_bearer = HTTPBearer(auto_error=False)


def _expected_issuer() -> str:
    """Build the Entra External ID issuer URL from Settings.

    Format: https://{tenant_id}.ciamlogin.com/{tenant_id}/v2.0

    Entra External ID tokens use the tenant ID as subdomain in the `iss`
    claim, NOT the friendly subdomain (which is only used in MSAL's
    authority URL during sign-in). Previously this used
    `entra_tenant_subdomain`, causing iss validation to fail with 401 for
    all real tokens — discovered during Phase 5 UAT, where the dashboard is
    the first prod page to exercise an authenticated backend call.

    The OIDC discovery endpoint at `{subdomain}.ciamlogin.com/.../openid-configuration`
    and at `{tenant_id}.ciamlogin.com/.../openid-configuration` both return the
    same metadata document with `issuer` set to the tenant-ID form, which is
    what real tokens carry — so the `openid_config_url` below can keep using
    the friendly subdomain without affecting iss validation here.
    """
    return (
        f"https://{settings.entra_tenant_id}.ciamlogin.com/"
        f"{settings.entra_tenant_id}/v2.0"
    )


async def _iss_callable(tid: str) -> str:
    """Library-required callable that returns the expected issuer.

    fastapi-azure-auth's B2CMultiTenantAuthorizationCodeBearer requires an
    iss_callable when validate_iss=True. For Entra External ID (single
    tenant from our perspective) the expected issuer is the same for every
    request — we ignore the `tid` claim and return the pinned issuer URL.
    Rejects per T-04-02-01 (wrong-tenant JWT mistaken for ours).
    """
    return _expected_issuer()


# Module-level azure_scheme instance — instantiated ONCE at import time.
# fastapi-azure-auth caches JWKS in-process (LRU) so per-request validation
# is just a signature check, not a network round-trip.
azure_scheme = B2CMultiTenantAuthorizationCodeBearer(
    app_client_id=settings.backend_audience.removeprefix("api://"),
    openid_config_url=(
        f"https://{settings.entra_tenant_subdomain}.ciamlogin.com/"
        f"{settings.entra_tenant_id}/v2.0/.well-known/openid-configuration"
    ),
    scopes={
        f"{settings.backend_audience}/access_as_user": "access_as_user",
    },
    validate_iss=True,
    iss_callable=_iss_callable,
)


async def require_api_key(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer),
) -> None:
    """Validate Bearer token against the configured API key.

    Legacy dev-only auth — Phase 4 protected routes use get_current_user_id
    instead. Kept for /health-style unauthenticated dev endpoints.

    Auth is skipped when ``settings.api_key`` is empty (local development).
    """
    if not settings.api_key:
        return
    if not credentials or not hmac.compare_digest(credentials.credentials, settings.api_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


class RateLimiter:
    """Simple in-memory sliding-window rate limiter.

    NOTE: This is per-process and keyed by client IP. Behind a reverse
    proxy or NAT, multiple users may share one bucket. In multi-worker
    deployments each worker has its own state, so effective limits scale
    with worker count. For production use behind a load balancer,
    replace with a Redis-backed limiter (e.g. slowapi + redis).
    """

    def __init__(self, calls: int, period: int) -> None:
        self.calls = calls
        self.period = period
        self._requests: dict[str, list[float]] = defaultdict(list)

    async def __call__(self, request: Request) -> None:
        client_ip = request.client.host if request.client else "unknown"
        now = time.time()
        window = [t for t in self._requests[client_ip] if now - t < self.period]
        if len(window) >= self.calls:
            raise HTTPException(status_code=429, detail="Rate limit exceeded")
        window.append(now)
        self._requests[client_ip] = window

        # Prune IPs whose entire window has expired
        stale = [
            ip for ip, ts in self._requests.items()
            if ip != client_ip and ts and now - ts[-1] >= self.period
        ]
        for ip in stale:
            del self._requests[ip]


# Pre-configured limiters (Phase 1 contracts — routes.py imports these).
standard_limit = RateLimiter(calls=30, period=60)   # 30 req/min
agent_limit = RateLimiter(calls=10, period=60)       # 10 req/min
ingest_limit = RateLimiter(calls=5, period=60)       #  5 req/min
# Dashboard fires 3 parallel widget fetches per page load; with React Query retries
# and the proxy-IP collapse behind SWA→ACA, 30/min trips on a couple of reloads.
dashboard_limit = RateLimiter(calls=120, period=60)  # 120 req/min


async def get_current_user_id(
    user: User = Depends(azure_scheme),
) -> uuid.UUID:
    """Resolve the current user's UUID (Phase 4 / AUTH-06 rewrite).

    Phase 1 D-10 function-body rewrite: every consumer was already wired via
    Depends(get_current_user_id) on /match /gaps /ingest /agent /agent/stream.
    Phase 4 swaps the body in place — no call-site changes.

    AUTH-06 single-user guard (D-08): reject any oid != settings.seeded_user_entra_oid.
    Rejected oid is logged via structlog (LAW audit) but NOT returned in the response
    body (would leak who-has-signed-up if multi-user is enabled later).

    The seeded_user_entra_oid env var starts EMPTY in bootstrap-pending state
    (before D-09 first-login OID capture). Treat empty as "deny all" — no token
    can match an empty string.
    """
    oid = user.claims.get("oid") if isinstance(user.claims, dict) else None
    if not settings.seeded_user_entra_oid or oid != settings.seeded_user_entra_oid:
        log.warning(
            "user_not_allowlisted",
            rejected_oid=oid,
            seeded_configured=bool(settings.seeded_user_entra_oid),
        )
        raise HTTPException(status_code=403, detail="user_not_allowlisted")
    return settings.seeded_user_id
