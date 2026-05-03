import os
import urllib.parse
import uuid
from typing import Annotated

from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

_DEFAULT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/job_rag"
_DEFAULT_ASYNC_DATABASE_URL = "postgresql+asyncpg://postgres:postgres@localhost:5432/job_rag"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = _DEFAULT_DATABASE_URL
    async_database_url: str = _DEFAULT_ASYNC_DATABASE_URL
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    embedding_model: str = "text-embedding-3-small"
    rag_model: str = "gpt-4o-mini"
    reranker_model: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"
    data_dir: str = "data/postings"
    profile_path: str = "data/profile.json"
    langfuse_public_key: str = ""
    langfuse_secret_key: str = ""
    langfuse_host: str = "https://cloud.langfuse.com"
    agent_model: str = "gpt-4o-mini"
    api_key: str = Field(default="", validation_alias="JOB_RAG_API_KEY")

    # CORS allow-list for the FastAPI app. Default = local Vite dev server only.
    # NEVER set this to "*" in production (D-26): credentialed CORS + wildcard origin
    # is a hard security failure and CORSMiddleware will refuse to combine the two.
    # Override via ALLOWED_ORIGINS env var as a comma-separated list, e.g.
    # "http://localhost:5173,https://app.example.com" — _split_origins handles the
    # split. The Annotated[..., NoDecode] disables Pydantic Settings' default JSON
    # decoding for complex types so the validator sees the raw string instead of
    # a JSONDecodeError on plain CSV input.
    allowed_origins: Annotated[list[str], NoDecode] = Field(default=["http://localhost:5173"])

    # Hardcoded Python constant (D-08): the v1 single-user UUID. The IDENTICAL literal
    # MUST also appear in alembic/versions/0002_add_user_profile.py — Plan 02 enforces
    # this in its migration test. Do NOT add a validation_alias here: there is
    # deliberately no env-var override path (T-01-02 / threat register). Phase 4
    # rewrites this field's role: the dependency get_current_user_id() pivots from
    # returning seeded_user_id to parsing the Entra JWT, and a dedicated migration
    # rebinds the FK row to the real Entra `oid` (D-09).
    seeded_user_id: uuid.UUID = uuid.UUID("00000000-0000-0000-0000-000000000001")

    # ge=1 guards against env-misconfig (0 or negative) that would silently break
    # asyncio.wait_for and sse-starlette's ping kwarg downstream (D-15, D-25).
    agent_timeout_seconds: int = Field(default=60, ge=1)
    heartbeat_interval_seconds: int = Field(default=15, ge=1)

    @field_validator("allowed_origins", mode="before")
    @classmethod
    def _split_origins(cls, v: str | list[str]) -> list[str]:
        """Accept either a CSV string (env var) or a list (Python default)."""
        if isinstance(v, str):
            return [o.strip() for o in v.split(",") if o.strip()]
        return v

    @model_validator(mode="after")
    def _compose_db_urls_from_parts(self) -> "Settings":
        """Build DATABASE_URL/ASYNC_DATABASE_URL from POSTGRES_* parts when in ACA.

        The ACA compute module wires POSTGRES_HOST/USER/DB env vars and exposes
        POSTGRES_ADMIN_PASSWORD via KV secretRef, but does NOT set DATABASE_URL
        directly (passwords would have to live in plain env). The docker
        entrypoint composes the URL once at startup, but `az containerapp exec`
        spawns a fresh shell that bypasses the entrypoint — so the CLI
        (job-rag ingest, etc.) sees only the default localhost URL and fails.
        Composing here makes any code path correct regardless of launcher.
        """
        host = os.environ.get("POSTGRES_HOST")
        if not host:
            return self
        if self.database_url != _DEFAULT_DATABASE_URL:
            return self  # Caller already supplied an explicit URL; respect it.

        user = os.environ.get("POSTGRES_USER")
        db = os.environ.get("POSTGRES_DB")
        password = os.environ.get("POSTGRES_ADMIN_PASSWORD")
        if not (user and db and password):
            return self  # Incomplete parts — keep localhost default and let the connection error surface naturally.

        encoded_pw = urllib.parse.quote(password, safe="")
        self.database_url = (
            f"postgresql://{user}:{encoded_pw}@{host}:5432/{db}?sslmode=require"
        )
        self.async_database_url = (
            f"postgresql+asyncpg://{user}:{encoded_pw}@{host}:5432/{db}?ssl=require"
        )
        return self


settings = Settings()
