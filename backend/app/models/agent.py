import uuid

from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class AgentDefinition(TimestampMixin, Base):
    __tablename__ = "agent_definitions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # catalog, atf, integration, documentation, cmdb, code_review, update_set
    system_prompt_version: Mapped[str] = mapped_column(String(20), default="1.0.0")
    available_tools: Mapped[dict] = mapped_column(JSON, default=list)
    default_model: Mapped[str] = mapped_column(String(50), default="claude-sonnet-4-20250514")
    max_steps: Mapped[int] = mapped_column(Integer, default=50)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    direct_invokable: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # True = user can assign this agent directly to a Kanban story
