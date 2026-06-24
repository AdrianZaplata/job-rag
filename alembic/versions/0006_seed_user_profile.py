"""seed Adrian's user_profile row (PROF-01 / Phase 7 D-03)

Revision ID: 0006
Revises: 0005
Create Date: 2026-05-28

Phase 7 D-03: seed the row that 0002_add_user_profile.py intentionally left empty.
The row is INSERTed via ON CONFLICT (user_id) DO NOTHING so re-running the migration
against an already-seeded DB is a no-op (T-07-03 mitigation). Downgrade deletes
ONLY the seeded UUID row.

D-03/D-04 invariant: the seed contents are embedded as a Python dict literal
generated from data/profile.json AT MIGRATION-AUTHOR TIME. We do NOT read the
JSON file at runtime because data/ is gitignored at the container layer; a fresh
ACA boot would crash on a runtime file read. To refresh the seed, edit
data/profile.json AND regenerate the _PROFILE literal in lockstep.

Migrations do NOT import from job_rag.config (avoid full app import order at
migration runtime) — the SEEDED_USER_UUID literal must match settings.seeded_user_id.
"""
import json
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0006"
down_revision: str | Sequence[str] | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Phase 1 D-08 invariant: this canonical UUID MUST match config.py
# settings.seeded_user_id and the row inserted by 0002_add_user_profile.py.
SEEDED_USER_UUID = "00000000-0000-0000-0000-000000000001"

# Embedded snapshot of data/profile.json as of 2026-05-28 (D-03/D-04 — data/ is
# gitignored at the container layer; runtime file-read would crash on fresh ACA
# boot). Update flow: edit data/profile.json AND regenerate this literal in
# lockstep, then ship a NEW migration (do NOT mutate this one in place — Alembic
# revisions are immutable history).
_PROFILE: dict[str, object] = {
    "skills": [
        {"name": "English"},
        {"name": "German"},
        {"name": "Polish"},
        {"name": "Python"},
        {"name": "FastAPI"},
        {"name": "TypeScript"},
        {"name": "React"},
        {"name": "React Native"},
        {"name": "Docker"},
        {"name": "PostgreSQL"},
        {"name": "C#"},
        {"name": "C++"},
        {"name": "SQLAlchemy"},
        {"name": "asyncpg"},
        {"name": "Pydantic"},
        {"name": "pydantic-settings"},
        {"name": "tenacity"},
        {"name": "Typer"},
        {"name": "Supabase"},
        {"name": "LangGraph"},
        {"name": "LangChain"},
        {"name": "Instructor"},
        {"name": "FastMCP"},
        {"name": "MCP"},
        {"name": "Ollama"},
        {"name": "Claude Code"},
        {"name": "Prompt Engineering"},
        {"name": "API integration"},
        {"name": "pgvector"},
        {"name": "vector databases"},
        {"name": "embeddings"},
        {"name": "cross-encoder reranking"},
        {"name": "semantic search"},
        {"name": "RAGAS"},
        {"name": "RAG"},
        {"name": "Langfuse"},
        {"name": "structlog"},
        {"name": "GitHub Actions"},
        {"name": "CI/CD"},
        {"name": "pip-audit"},
        {"name": "PyTorch"},
        {"name": "Stable Diffusion"},
        {"name": "LoRA fine-tuning"},
        {"name": "Hugging Face"},
        {"name": "Git"},
        {"name": "GitHub CLI"},
        {"name": "pytest"},
        {"name": "Ruff"},
        {"name": "Pyright"},
        {"name": "uv"},
        {"name": "Playwright"},
        {"name": "Maestro"},
        {"name": "Software Architecture"},
        {"name": "Performance Optimization"},
        {"name": "n8n"},
        {"name": "Unity"},
        {"name": "Unreal Engine"},
        {"name": "3D Graphics"},
        {"name": "SSE"},
        {"name": "async"},
        {"name": "sse-starlette"},
        {"name": "LLM"},
        {"name": "agent orchestration"},
    ],
    "target_roles": ["AI Engineer", "AI Application Engineer", "AI Software Engineer"],
    "preferred_locations": ["Berlin, Germany", "Germany", "Remote"],
    "min_salary": 65000,
    "remote_preference": "remote",
}


def upgrade() -> None:
    """Seed Adrian's user_profile row idempotently (T-07-03)."""
    op.execute(
        sa.text(
            "INSERT INTO user_profile "
            "(user_id, skills_json, target_roles_json, preferred_locations_json, "
            " min_salary_eur, remote_preference, updated_at) "
            "VALUES (:uid, :skills, :roles, :locs, :sal, :remote, now()) "
            "ON CONFLICT (user_id) DO NOTHING"
        ).bindparams(
            uid=SEEDED_USER_UUID,
            skills=json.dumps(_PROFILE["skills"]),
            roles=json.dumps(_PROFILE["target_roles"]),
            locs=json.dumps(_PROFILE["preferred_locations"]),
            sal=_PROFILE["min_salary"],
            remote=_PROFILE["remote_preference"],
        )
    )


def downgrade() -> None:
    """Reverse — delete ONLY the seeded UUID row; other rows untouched."""
    op.execute(
        sa.text(
            "DELETE FROM user_profile WHERE user_id = :uid"
        ).bindparams(uid=SEEDED_USER_UUID)
    )
