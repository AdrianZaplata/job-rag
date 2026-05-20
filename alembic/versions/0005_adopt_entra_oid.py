"""adopt entra oid: ensure users.entra_oid + idempotent UPDATE of seeded row

Revision ID: 0005
Revises: 0004
Create Date: 2026-05-20

D-10 (Phase 4): Bridges Phase 1's seeded_user_id to Adrian's real Entra oid
(captured out-of-band via D-09 AccessDenied UX → az keyvault secret set).

Runs blocking on container startup per Phase 1 D-04 (init_db() wraps
alembic upgrade head). On empty SEEDED_USER_ENTRA_OID env (bootstrap-pending
state), the UPDATE is a no-op — migration completes cleanly so container
starts; AUTH-06 guard then rejects every token until KV secret is filled.

NOTE (executor Rule 1 fix): the canonical table name in this codebase is
`users` (not `user_db` — the plan/RESEARCH skeleton was written without
verifying the actual ORM table name in src/job_rag/db/models.py::UserDB,
which sets __tablename__ = "users"). The `entra_oid` column itself was
already created by 0002_add_user_profile.py as `Text` with `unique=True`,
so this migration's column-add step is idempotent (skip if exists).

The partial unique index `ix_users_entra_oid_unique` (NULLS allowed via
postgresql_where) is added here even though 0002 created a regular unique
constraint — required by Plan 04-02 must-have truth #9. PG allows multiple
indexes on the same column; both filter to the same uniqueness semantics
(both allow multiple NULLs).

Pitfall 14: oid value is bound via :oid placeholder (parameterized SQL).
No string interpolation — even though the source is os.environ controlled by
Adrian, the bindparam discipline keeps the SQL surface clean.

Pgvector caveat per Phase 1 plan 01-02 D-02: env.py already registers
pgvector.sqlalchemy.Vector on connection.dialect.ischema_names BEFORE
context.configure(). No change here.
"""
import os
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "0005"
down_revision: str | Sequence[str] | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Phase 1 D-08 invariant: this canonical UUID MUST match config.py
# settings.seeded_user_id and the row inserted by 0002_add_user_profile.py.
# Migrations do NOT import from job_rag.config (avoid full app import order
# at migration runtime) — keep as a literal constant here.
SEEDED_USER_UUID = "00000000-0000-0000-0000-000000000001"


def _has_column(conn: sa.engine.Connection, table: str, column: str) -> bool:
    """Idempotency helper — check information_schema for column presence."""
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name = :t AND column_name = :c"
            ).bindparams(t=table, c=column)
        ).first()
    )


def _has_index(conn: sa.engine.Connection, index_name: str) -> bool:
    """Idempotency helper — check pg_indexes for index presence."""
    return bool(
        conn.execute(
            sa.text(
                "SELECT 1 FROM pg_indexes WHERE indexname = :n"
            ).bindparams(n=index_name)
        ).first()
    )


def upgrade() -> None:
    """Upgrade schema to Phase 4 shape."""
    conn = op.get_bind()

    # 1. Add entra_oid column to users (idempotent — 0002 may have already
    #    added it as Text/unique). Plan 04-02 contract: column must exist
    #    with NULL allowed; existing Text type satisfies VARCHAR(255) intent
    #    (TEXT is a superset).
    if not _has_column(conn, "users", "entra_oid"):
        op.add_column(
            "users",
            sa.Column("entra_oid", sa.String(255), nullable=True),
        )

    # 2. Idempotent UPDATE — bridge Phase 1's seeded UUID to Adrian's real oid
    #    when SEEDED_USER_ENTRA_OID is set. On empty env (bootstrap-pending),
    #    this is a no-op; migration still completes.
    oid = os.environ.get("SEEDED_USER_ENTRA_OID", "").strip()
    if oid:
        op.execute(
            sa.text(
                "UPDATE users SET entra_oid = :oid "
                "WHERE id = :seeded_uuid AND (entra_oid IS NULL OR entra_oid != :oid)"
            ).bindparams(oid=oid, seeded_uuid=SEEDED_USER_UUID)
        )

    # 3. Create partial unique index on entra_oid (when populated) — structural
    #    prep for future multi-user where oid is the authoritative lookup. Partial
    #    index excludes NULLs so existing rows without an oid don't violate.
    #    Idempotent: skip if already present (re-run safety on container restart).
    if not _has_index(conn, "ix_users_entra_oid_unique"):
        op.create_index(
            "ix_users_entra_oid_unique",
            "users",
            ["entra_oid"],
            unique=True,
            postgresql_where=sa.text("entra_oid IS NOT NULL"),
        )


def downgrade() -> None:
    """Reverse — drop the partial unique index. Do NOT drop the entra_oid
    column itself: it was created by 0002 (we only ensured presence here),
    and dropping it would lose data captured by the bootstrap flow.
    """
    conn = op.get_bind()
    if _has_index(conn, "ix_users_entra_oid_unique"):
        op.drop_index("ix_users_entra_oid_unique", table_name="users")
