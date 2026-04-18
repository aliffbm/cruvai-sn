import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TenantMixin, TimestampMixin


class UserStory(TenantMixin, TimestampMixin, Base):
    __tablename__ = "user_stories"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    external_id: Mapped[str | None] = mapped_column(String(100), nullable=True)  # SN story number
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    acceptance_criteria: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=3)  # 1-4
    status: Mapped[str] = mapped_column(
        String(50), default="backlog"
    )  # backlog, ready, in_progress, review, testing, done
    assigned_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    assigned_to_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    story_points: Mapped[int | None] = mapped_column(Integer, nullable=True)
    tags: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sn_sys_id: Mapped[str | None] = mapped_column(String(32), nullable=True)
    board_position: Mapped[int] = mapped_column(Integer, default=0)  # For ordering on kanban
    embedding = mapped_column(Vector(1536), nullable=True)

    # Epic support — stories can have a parent (epic)
    parent_story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_stories.id"), nullable=True, index=True
    )
    story_type: Mapped[str] = mapped_column(
        String(20), default="story"
    )  # epic, story
    figma_node_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Figma node ID for traceability
    figma_file_url: Mapped[str | None] = mapped_column(
        String(1000), nullable=True
    )  # Figma file/project URL consumed by the Portal agent as a design source

    # Relationships
    children: Mapped[list["UserStory"]] = relationship(
        back_populates="parent", foreign_keys=[parent_story_id]
    )
    parent: Mapped["UserStory | None"] = relationship(
        remote_side="UserStory.id", back_populates="children", foreign_keys=[parent_story_id]
    )
