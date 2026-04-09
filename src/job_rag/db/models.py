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
    location: Mapped[str] = mapped_column(String(255), nullable=False)
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
    )


class JobRequirementDB(Base):
    __tablename__ = "job_requirements"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    posting_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("job_postings.id", ondelete="CASCADE"))
    skill: Mapped[str] = mapped_column(String(100), nullable=False)
    category: Mapped[str] = mapped_column(String(20), nullable=False)
    required: Mapped[bool] = mapped_column(nullable=False)

    posting: Mapped["JobPostingDB"] = relationship(back_populates="requirements")

    __table_args__ = (
        Index("ix_job_requirements_skill", "skill"),
        Index("ix_job_requirements_category", "category"),
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
