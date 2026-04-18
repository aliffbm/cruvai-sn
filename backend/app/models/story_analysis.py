"""Story design review models — analysis, notes, AC verification.

Phase 2 of the governance layer:
  - StoryAnalysis: authored by the AI Agent Analyzer, reviewable pre-build.
  - StoryNote: append-only audit trail (requirement changes, build outcomes).
  - StoryACResult: (F13, landed alongside to avoid churn) per-AC verification
    result produced after a build agent completes.

All tables enforce attribution: which agent produced the record, which job.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class StoryAnalysis(TimestampMixin, Base):
    """AI-authored technical design for a story. Reviewable, approvable, versioned.

    Latest `approved` row is the authoritative design; `require_analysis_approval`
    gates agent dispatch when enabled on the project.
    """

    __tablename__ = "story_analyses"
    __table_args__ = (
        UniqueConstraint("story_id", "version_number", name="uq_analysis_story_version"),
        Index("ix_analysis_content_hash", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_stories.id"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(
        String(30), default="draft", nullable=False
    )  # draft, approved, outdated, superseded
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)

    # Human-readable outputs
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    design_rationale: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Structured outputs
    oob_reuse: Mapped[list | None] = mapped_column(JSON, default=list)
    design_patterns_applied: Mapped[list | None] = mapped_column(JSON, default=list)
    proposed_artifacts: Mapped[list | None] = mapped_column(JSON, default=list)
    acceptance_criteria_mapping: Mapped[list | None] = mapped_column(JSON, default=list)
    specialist_consults: Mapped[list | None] = mapped_column(JSON, default=list)
    applicable_guidance: Mapped[list | None] = mapped_column(JSON, default=list)
    risks: Mapped[list | None] = mapped_column(JSON, default=list)
    dependencies_on_other_stories: Mapped[list | None] = mapped_column(JSON, default=list)
    estimated_story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Attribution (required for AI content transparency)
    authored_by_agent_slug: Mapped[str] = mapped_column(String(100), nullable=False)
    authored_by_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_jobs.id"), nullable=True
    )
    authored_by_model: Mapped[str | None] = mapped_column(String(100), nullable=True)

    # Review
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    reviewed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_reason: Mapped[str | None] = mapped_column(Text, nullable=True)


class StoryNote(Base):
    """Append-only audit note on a story. Never updated, never deleted.

    note_type enum:
      requirement_change — auto-written on story PATCH when description/AC change
      analysis_update    — auto-written when a StoryAnalysis is created/approved
      approval           — auto-written when an analysis is approved
      build_outcome      — auto-written when an AgentJob completes
      ac_verification    — auto-written when StoryACResult is produced (F13)
      manual             — user-authored note via the UI
    """

    __tablename__ = "story_notes"
    __table_args__ = (
        Index("ix_story_note_story_created", "story_id", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_stories.id"), nullable=False, index=True
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    note_type: Mapped[str] = mapped_column(String(40), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    diff: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    related_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)

    # Attribution — actor is either a user (manual) or an agent job (auto)
    author_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    author_agent_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    author_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_jobs.id"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class StoryACResult(TimestampMixin, Base):
    """AC verification outcome produced after a build agent completes (F13).

    One row per AC item per build job, so each job's verification is a snapshot.
    """

    __tablename__ = "story_ac_results"
    __table_args__ = (
        Index("ix_ac_result_story_job", "story_id", "job_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    story_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_stories.id"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_jobs.id"), nullable=False, index=True
    )
    criterion_text: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False
    )  # pass, fail, inferred, skipped, error
    evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    evaluated_by_agent_slug: Mapped[str | None] = mapped_column(String(100), nullable=True)
    evaluated_by_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
