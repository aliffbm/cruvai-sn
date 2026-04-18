"""Agent Memory model — semantic memory with pgvector for agent learning.

Agents store learnings from past ServiceNow builds as typed memories.
Memories are retrieved via cosine similarity at the start of each agent run,
providing agents with institutional knowledge that improves over time.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin

# pgvector column type — requires pgvector extension enabled on PostgreSQL
# If pgvector is not installed, this will be a no-op and vector queries won't work
try:
    from pgvector.sqlalchemy import Vector
    HAS_PGVECTOR = True
except ImportError:
    HAS_PGVECTOR = False


class AgentMemory(TimestampMixin, Base):
    """Persistent agent memory with semantic search capability."""

    __tablename__ = "agent_memories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=True, index=True
    )

    # Memory classification
    memory_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # pattern, insight, fact, strategy, avoid
    category: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # portal, catalog, widget, deployment, csm, employee_center, general

    # Content
    key: Mapped[str] = mapped_column(String(500), nullable=False)  # Short identifier/title
    value: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Structured data
    summary: Mapped[str] = mapped_column(Text, nullable=False)  # Human-readable summary

    # Confidence and importance
    confidence: Mapped[float] = mapped_column(Float, default=0.5)  # 0.0-1.0
    importance: Mapped[float] = mapped_column(Float, default=0.5)  # 0.0-1.0
    access_count: Mapped[int] = mapped_column(Integer, default=0)  # Times retrieved

    # Provenance
    source_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_jobs.id"), nullable=True
    )
    evidence: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Supporting data that produced this memory

    # Lifecycle
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    expires_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_accessed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Embedding for semantic search (1536-dim for text-embedding-3-small)
    # Column added conditionally based on pgvector availability
    if HAS_PGVECTOR:
        embedding = mapped_column(Vector(1536), nullable=True)
