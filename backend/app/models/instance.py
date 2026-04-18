import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, LargeBinary, String
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TenantMixin, TimestampMixin


class ServiceNowInstance(TenantMixin, TimestampMixin, Base):
    __tablename__ = "servicenow_instances"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    instance_url: Mapped[str] = mapped_column(String(500), nullable=False)
    instance_type: Mapped[str] = mapped_column(String(50), default="dev")  # dev, test, staging, prod
    auth_method: Mapped[str] = mapped_column(String(50), default="basic")  # basic, oauth2
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    last_health_check: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    health_status: Mapped[str] = mapped_column(String(50), default="unknown")  # healthy, degraded, unreachable, unknown
    sn_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    installed_plugins: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    credentials: Mapped[list["InstanceCredential"]] = relationship(back_populates="instance")


class InstanceCredential(TimestampMixin, Base):
    __tablename__ = "instance_credentials"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("servicenow_instances.id"), nullable=False
    )
    credential_type: Mapped[str] = mapped_column(String(50), default="basic")  # basic, oauth2_client
    username_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    password_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    client_id_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    client_secret_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    access_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    token_expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    refresh_token_encrypted: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    instance: Mapped["ServiceNowInstance"] = relationship(back_populates="credentials")
