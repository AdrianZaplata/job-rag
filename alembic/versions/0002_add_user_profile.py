"""add users + user_profile tables, seed Adrian's row

Revision ID: 0002
Revises: 0001
Create Date: 2026-04-27

D-06/D-07: introduce a users table + user_profile table for the multi-user-
ready schema. The user_id column carries no server-side or Python default
(per Pitfall 18 + D-08 + D-12). Seed row INSERT uses ON CONFLICT (id) DO NOTHING
so rerunning the migration cannot overwrite an existing row (T-02-02).
SEEDED_USER_ID is sourced from settings.seeded_user_id — single source of
truth across config.py, this migration, and tests/test_alembic.py.
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op
from job_rag.config import settings

# Pin SEEDED_USER_ID to the Settings literal — prevents drift across the
# three places this UUID appears (config.py, this migration, tests). Do
# NOT re-declare the UUID literal here (Pitfall 18 regression surface).
SEEDED_USER_ID = settings.seeded_user_id

# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | Sequence[str] | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "users",
        # NO server_default on id! Phase 4 swaps in the Entra `oid`; v1
        # gets the seed row INSERTed below (D-06, D-08).
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("entra_oid", sa.Text, unique=True, nullable=True),
        sa.Column("email", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    op.create_table(
        "user_profile",
        # NOT NULL, NO DEFAULT — Pitfall 18 guarantee (D-07, D-08, D-12).
        # tests/test_alembic.py::test_no_default_uuid_on_user_id_columns
        # actively scans this file for any DEFAULT/server_default near
        # `user_id` and fails the suite if found.
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            primary_key=True,
            nullable=False,
        ),
        sa.Column("skills_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column("target_roles_json", sa.Text, nullable=False, server_default="[]"),
        sa.Column(
            "preferred_locations_json",
            sa.Text,
            nullable=False,
            server_default="[]",
        ),
        sa.Column("min_salary_eur", sa.Integer, nullable=True),
        sa.Column(
            "remote_preference",
            sa.Text,
            nullable=False,
            server_default="unknown",
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )

    # Seed Adrian's user row — idempotent via ON CONFLICT (T-02-02).
    op.execute(
        sa.text(
            "INSERT INTO users (id, email) VALUES (:user_id, :email) "
            "ON CONFLICT (id) DO NOTHING"
        ).bindparams(
            user_id=SEEDED_USER_ID,
            email="adrianzaplata@gmail.com",
        )
    )


def downgrade() -> None:
    """Downgrade schema — drop child first for FK discipline."""
    op.drop_table("user_profile")
    op.drop_table("users")
