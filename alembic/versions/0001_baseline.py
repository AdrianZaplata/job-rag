"""baseline schema — job_postings + job_requirements + job_chunks + pgvector

Revision ID: 0001
Revises:
Create Date: 2026-04-27

Captures the pre-Phase-1 schema that already lived in Adrian's dev DB
(108 postings). On dev: this migration is `alembic stamp head`'d
without re-running DDL (D-01). On a fresh DB: it creates the vector
extension and the three corpus tables.

The users + user_profile tables and career_id column are intentionally
NOT here — they belong to 0002 and 0003 so they actually apply against
the dev DB (which gets stamped at 0001).
"""
from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # Pgvector extension MUST come first — column types below depend on it.
    # IF NOT EXISTS makes this a no-op when the DBA pre-creates the extension
    # (Phase 3 production scenario; Pitfall 9, T-02-01).
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "job_postings",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("linkedin_job_id", sa.String(length=20), nullable=True),
        sa.Column("content_hash", sa.String(length=64), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("company", sa.String(length=255), nullable=False),
        sa.Column("location", sa.String(length=255), nullable=False),
        sa.Column("remote_policy", sa.String(length=20), nullable=False),
        sa.Column("salary_min", sa.Integer(), nullable=True),
        sa.Column("salary_max", sa.Integer(), nullable=True),
        sa.Column("salary_raw", sa.String(length=100), nullable=True),
        sa.Column("salary_period", sa.String(length=10), nullable=False),
        sa.Column("seniority", sa.String(length=20), nullable=False),
        sa.Column("employment_type", sa.String(length=50), nullable=False),
        sa.Column("responsibilities", sa.Text(), nullable=False),
        sa.Column("benefits", sa.Text(), nullable=False),
        sa.Column("source_url", sa.String(length=500), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("prompt_version", sa.String(length=10), nullable=False),
        sa.Column(
            "embedding",
            Vector(1536),
            nullable=True,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("content_hash"),
        sa.UniqueConstraint("linkedin_job_id"),
    )
    op.create_index(
        "ix_job_postings_company", "job_postings", ["company"], unique=False
    )
    op.create_index(
        "ix_job_postings_remote_policy",
        "job_postings",
        ["remote_policy"],
        unique=False,
    )
    op.create_index(
        "ix_job_postings_seniority",
        "job_postings",
        ["seniority"],
        unique=False,
    )

    op.create_table(
        "job_requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("posting_id", sa.Uuid(), nullable=False),
        sa.Column("skill", sa.String(length=100), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=False),
        sa.Column("required", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(
            ["posting_id"], ["job_postings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_job_requirements_category",
        "job_requirements",
        ["category"],
        unique=False,
    )
    op.create_index(
        "ix_job_requirements_skill",
        "job_requirements",
        ["skill"],
        unique=False,
    )

    op.create_table(
        "job_chunks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("posting_id", sa.Uuid(), nullable=False),
        sa.Column("section", sa.String(length=50), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column(
            "embedding",
            Vector(1536),
            nullable=True,
        ),
        sa.ForeignKeyConstraint(
            ["posting_id"], ["job_postings.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_job_chunks_posting_id",
        "job_chunks",
        ["posting_id"],
        unique=False,
    )
    op.create_index(
        "ix_job_chunks_section",
        "job_chunks",
        ["section"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema — drop tables in reverse FK order; leave pgvector ext."""
    op.drop_index("ix_job_chunks_section", table_name="job_chunks")
    op.drop_index("ix_job_chunks_posting_id", table_name="job_chunks")
    op.drop_table("job_chunks")
    op.drop_index("ix_job_requirements_skill", table_name="job_requirements")
    op.drop_index("ix_job_requirements_category", table_name="job_requirements")
    op.drop_table("job_requirements")
    op.drop_index("ix_job_postings_seniority", table_name="job_postings")
    op.drop_index("ix_job_postings_remote_policy", table_name="job_postings")
    op.drop_index("ix_job_postings_company", table_name="job_postings")
    op.drop_table("job_postings")
    # NOTE: pgvector extension intentionally not dropped on downgrade.
