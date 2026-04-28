import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Index, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from job_rag.db.engine import Base


class JobPostingDB(Base):
    __tablename__ = "job_postings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    linkedin_job_id: Mapped[str | None] = mapped_column(String(20), unique=True, nullable=True)
    content_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    company: Mapped[str] = mapped_column(String(255), nullable=False)
    # Location columns (D-11 / 0004): flat 3-column representation. Pydantic
    # Location submodel mirrors these. NULL allowed during the post-migration
    # window before reextract populates them.
    location_country: Mapped[str | None] = mapped_column(String(2), nullable=True)
    location_city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    location_region: Mapped[str | None] = mapped_column(String(100), nullable=True)
    remote_policy: Mapped[str] = mapped_column(String(20), nullable=False)
    salary_min: Mapped[int | None] = mapped_column(nullable=True)
    salary_max: Mapped[int | None] = mapped_column(nullable=True)
    salary_raw: Mapped[str | None] = mapped_column(String(100), nullable=True)
    salary_period: Mapped[str] = mapped_column(String(10), default="unknown")
    seniority: Mapped[str] = mapped_column(String(20), nullable=False)
    employment_type: Mapped[str] = mapped_column(String(50), nullable=False)
    responsibilities: Mapped[str] = mapped_column(Text, nullable=False)
    benefits: Mapped[str] = mapped_column(Text, default="")
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    raw_text: Mapped[str] = mapped_column(Text, nullable=False)
    prompt_version: Mapped[str] = mapped_column(String(10), nullable=False)
    embedding = mapped_column(Vector(1536), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    # career_id (D-13): every v1 posting is an AI Engineer role; future career
    # expansion will be explicit. Unlike user_id, a DDL DEFAULT IS intentional
    # here — every row is the same value in v1. No index (Claude's Discretion —
    # all values identical in v1; index would add nothing).
    career_id: Mapped[str] = mapped_column(
        String(50), nullable=False, server_default="ai_engineer"
    )

    requirements: Mapped[list["JobRequirementDB"]] = relationship(
        back_populates="posting", cascade="all, delete-orphan"
    )
    chunks: Mapped[list["JobChunkDB"]] = relationship(
        back_populates="posting", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_job_postings_company", "company"),
        Index("ix_job_postings_seniority", "seniority"),
        Index("ix_job_postings_remote_policy", "remote_policy"),
        Index("ix_job_postings_location_country", "location_country"),
    )


class JobRequirementDB(Base):
    __tablename__ = "job_requirements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    skill: Mapped[str] = mapped_column(String(100), nullable=False)
    # skill_type renamed from `category` in 0004 (D-04). LLM-extracted (8 values).
    skill_type: Mapped[str] = mapped_column(String(20), nullable=False)
    # skill_category derived from skill_type at write via models.derive_skill_category() (D-03).
    skill_category: Mapped[str] = mapped_column(String(20), nullable=False)
    required: Mapped[bool] = mapped_column(nullable=False)

    posting: Mapped["JobPostingDB"] = relationship(back_populates="requirements")

    __table_args__ = (
        Index("ix_job_requirements_skill", "skill"),
        Index("ix_job_requirements_skill_type", "skill_type"),
        Index("ix_job_requirements_skill_category", "skill_category"),
    )


class JobChunkDB(Base):
    __tablename__ = "job_chunks"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    section: Mapped[str] = mapped_column(String(50), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    embedding = mapped_column(Vector(1536), nullable=True)

    posting: Mapped["JobPostingDB"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_job_chunks_posting_id", "posting_id"),
        Index("ix_job_chunks_section", "section"),
    )


class UserDB(Base):
    """Registered user. v1 has exactly one row (Adrian's SEEDED_USER_ID).

    Phase 4 swaps `id` to the Entra `oid` via 00NN_adopt_entra_oid.py.
    NOTE: `id` has NO default and NO server_default — value is app-injected
    from the JWT `sub`/`oid` claim (Pitfall 18, D-08, D-12).
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True)  # NO default
    entra_oid: Mapped[str | None] = mapped_column(Text, unique=True, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class UserProfileDB(Base):
    """User skill profile. v1 read path is data/profile.json (D-07);
    Phase 7 (PROF-01) flips the source to this table.

    NOTE: `user_id` has NO default and NO server_default — app/migration
    INSERT must supply the value (D-07, D-08, D-12).
    """

    __tablename__ = "user_profile"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"),
        primary_key=True,
        nullable=False,
    )
    # server_default values mirror alembic/versions/0002_add_user_profile.py
    # exactly so `alembic check` (must-have truth #7) reports no drift between
    # ORM models and migrations.
    skills_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    target_roles_json: Mapped[str] = mapped_column(Text, nullable=False, server_default="[]")
    preferred_locations_json: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="[]"
    )
    min_salary_eur: Mapped[int | None] = mapped_column(nullable=True)
    remote_preference: Mapped[str] = mapped_column(
        Text, nullable=False, server_default="unknown"
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
