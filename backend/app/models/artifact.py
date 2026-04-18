import uuid

from sqlalchemy import ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column
from pgvector.sqlalchemy import Vector

from app.models.base import Base, TenantMixin, TimestampMixin


class Artifact(TenantMixin, TimestampMixin, Base):
    __tablename__ = "artifacts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    project_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("projects.id"), nullable=False, index=True
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_jobs.id"), nullable=False
    )
    story_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("user_stories.id"), nullable=True
    )
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servicenow_instances.id"), nullable=False
    )
    sn_table: Mapped[str] = mapped_column(String(100), nullable=False)
    sn_sys_id: Mapped[str] = mapped_column(String(32), nullable=False)
    sn_scope: Mapped[str] = mapped_column(String(100), default="global")
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    artifact_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # script_include, business_rule, client_script, ui_policy, catalog_item, flow, subflow, atf_test, notification, rest_api, spoke, record_producer, ui_action
    content_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    script_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(50), default="draft"
    )  # draft, pending_review, approved, deployed, rolled_back
    deployed_to_update_set_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    embedding = mapped_column(Vector(1536), nullable=True)


class ArtifactVersion(TimestampMixin, Base):
    __tablename__ = "artifact_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    artifact_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("artifacts.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content_snapshot: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    script_content: Mapped[str | None] = mapped_column(Text, nullable=True)
    change_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    changed_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    changed_by_job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_jobs.id"), nullable=True
    )
