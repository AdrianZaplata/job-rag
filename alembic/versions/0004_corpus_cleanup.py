"""corpus cleanup: rename category->skill_type, add skill_category, structured Location

Revision ID: 0004
Revises: 0003
Create Date: 2026-04-27

HAND-WRITTEN -- DO NOT regenerate via `alembic revision --autogenerate`.

Pitfall 1 (autogenerate detects rename as drop+add): autogenerate cannot infer
that `category` and `skill_type` are the same column under a new name. It would
emit drop_column('category') + add_column('skill_type'), DESTROYING all 108
postings' skill data. The hand-written op.alter_column(new_column_name=...)
below is the safe path.

Pitfall 2 (NOT NULL with no default fails on existing rows): skill_category
is added nullable=True FIRST, backfilled via SQL CASE on skill_type, THEN
flipped to NOT NULL.

Pitfall 6 (op.alter_column does NOT rename associated indexes): the old
ix_job_requirements_category index keeps its name even after the column is
renamed. We DROP the old index by its OLD name BEFORE creating the new
indexes, otherwise we'd end up with two indexes covering the same column.

D-11: job_postings.location free-text column is dropped; replaced by 3 flat
columns location_country (String(2)) / location_city (String(255)) /
location_region (String(100)), all nullable. Existing free-text data is
intentionally lost from the column -- raw_text is preserved (D-15) and
re-extraction repopulates from there.

D-15: embeddings (job_postings.embedding, job_chunks.content,
job_chunks.embedding) are NOT touched. Migration only modifies structured
metadata columns.
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0004"
down_revision: str | Sequence[str] | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema to Phase 2 shape."""
    # 1. Rename `category` -> `skill_type` on job_requirements (D-04 step 1).
    #    PostgreSQL preserves data; the column's index keeps its OLD name
    #    (Pitfall 6) -- we drop it next.
    op.alter_column(
        "job_requirements",
        "category",
        new_column_name="skill_type",
    )

    # 2. Drop the old index BY ITS OLD NAME -- `op.alter_column` did not rename
    #    the index file, only the column it covers (Pitfall 6).
    op.drop_index(
        "ix_job_requirements_category",
        table_name="job_requirements",
    )

    # 3. Add skill_category as NULLABLE first (Pitfall 2). Backfill cannot run
    #    against a non-existent column, and we cannot mark NOT NULL until
    #    every row has a value.
    op.add_column(
        "job_requirements",
        sa.Column("skill_category", sa.String(20), nullable=True),
    )

    # 4. Backfill via SQL CASE -- mirrors models.derive_skill_category() in
    #    Python. Soft skill -> soft, domain -> domain, everything else -> hard.
    #    No bindparams (the 8 enum values are literal SQL constants -- safe).
    op.execute(
        """
        UPDATE job_requirements SET skill_category = CASE
            WHEN skill_type = 'soft_skill' THEN 'soft'
            WHEN skill_type = 'domain'     THEN 'domain'
            ELSE 'hard'
        END
        """
    )

    # 5. Now safe to flip NOT NULL -- every existing row was backfilled in step 4.
    op.alter_column(
        "job_requirements",
        "skill_category",
        nullable=False,
    )

    # 6. New indexes for the renamed/added columns (D-04 step 3).
    op.create_index(
        "ix_job_requirements_skill_type",
        "job_requirements",
        ["skill_type"],
        unique=False,
    )
    op.create_index(
        "ix_job_requirements_skill_category",
        "job_requirements",
        ["skill_category"],
        unique=False,
    )

    # 7. Add 3 flat Location columns on job_postings (D-11). All NULLABLE -- the
    #    re-extraction step (Plan 04) populates them. Until reextract runs,
    #    every row has all-null location_* columns; the dashboard (Phase 5)
    #    will show "--" until Plan 04 completes.
    op.add_column(
        "job_postings",
        sa.Column("location_country", sa.String(2), nullable=True),
    )
    op.add_column(
        "job_postings",
        sa.Column("location_city", sa.String(255), nullable=True),
    )
    op.add_column(
        "job_postings",
        sa.Column("location_region", sa.String(100), nullable=True),
    )

    # 8. Drop the old free-text location column (D-11). Data lost from this
    #    column is preserved in raw_text (D-15); re-extraction recovers it.
    op.drop_column("job_postings", "location")

    # 9. Country index (Claude's Discretion + Phase 5 will filter heavily).
    op.create_index(
        "ix_job_postings_location_country",
        "job_postings",
        ["location_country"],
        unique=False,
    )


def downgrade() -> None:
    """Reverse the upgrade. NOTE: re-adding `location` as NOT NULL would
    fail on rows where location_country/city/region are all null. Use
    nullable=True; the downgrade path is exercised in test only.
    """
    # Reverse step 9.
    op.drop_index(
        "ix_job_postings_location_country",
        table_name="job_postings",
    )

    # Reverse step 8 (re-add as nullable; downgrade is test-only).
    op.add_column(
        "job_postings",
        sa.Column("location", sa.String(255), nullable=True),
    )

    # Reverse step 7.
    op.drop_column("job_postings", "location_region")
    op.drop_column("job_postings", "location_city")
    op.drop_column("job_postings", "location_country")

    # Reverse step 6.
    op.drop_index(
        "ix_job_requirements_skill_category",
        table_name="job_requirements",
    )
    op.drop_index(
        "ix_job_requirements_skill_type",
        table_name="job_requirements",
    )

    # Reverse steps 5 + 3 (drop the new column).
    op.drop_column("job_requirements", "skill_category")

    # Reverse step 1 (rename back).
    op.alter_column(
        "job_requirements",
        "skill_type",
        new_column_name="category",
    )

    # Reverse step 2 (re-create the old index).
    op.create_index(
        "ix_job_requirements_category",
        "job_requirements",
        ["category"],
        unique=False,
    )
