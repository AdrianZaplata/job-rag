"""add career_id column to job_postings

Revision ID: 0003
Revises: 0002
Create Date: 2026-04-27

D-13: every v1 posting is an AI Engineer role; future career expansion
will be explicit. Unlike user_id, a DDL DEFAULT IS intentional here —
backfills all pre-existing rows in one statement.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | Sequence[str] | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "job_postings",
        sa.Column(
            "career_id",
            sa.String(50),
            nullable=False,
            server_default="ai_engineer",  # DDL DEFAULT OK here (D-13)
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("job_postings", "career_id")
