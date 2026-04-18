"""Connector models — pluggable integrations with external systems.

Connectors provide authenticated access to external APIs (LLM providers,
design tools, notification services, etc.). Each connector stores encrypted
credentials and defines available actions (HTTP operations).

Architecture:
- Connector: connection identity + encrypted credentials + auth type
- ConnectorAction: what a connector can do (HTTP method + endpoint + schemas)
- Template actions: OOB definitions (connector_id=NULL, platform_template set)
- Instance actions: per-connector copies hydrated from templates
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Connector(TimestampMixin, Base):
    """External system connection with encrypted credential storage."""

    __tablename__ = "connectors"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )

    # Identity
    platform: Mapped[str] = mapped_column(
        String(100), nullable=False
    )  # e.g., "anthropic", "openai", "figma", "slack", "github", "servicenow"
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    icon: Mapped[str | None] = mapped_column(String(100), nullable=True)
    instance_label: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Disambiguate multiples (e.g., "Dev Instance", "Prod Instance")

    # Auth
    connector_type: Mapped[str] = mapped_column(
        String(50), nullable=False, default="api_key"
    )  # api_key, bearer_token, basic_auth, oauth2, none
    credentials_encrypted: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Fernet-encrypted JSON blob of all credentials

    # Configuration
    config: Mapped[dict | None] = mapped_column(
        JSON, default=dict
    )  # {required_keys: [{key, label, type, required}], docs_url, auth_type}
    base_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # Default base URL for all actions

    # Status
    status: Mapped[str] = mapped_column(
        String(50), default="disconnected"
    )  # connected, disconnected, error
    status_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    actions: Mapped[list["ConnectorAction"]] = relationship(
        back_populates="connector", cascade="all, delete-orphan"
    )


class ConnectorAction(TimestampMixin, Base):
    """Defines an HTTP operation a connector can perform."""

    __tablename__ = "connector_actions"
    __table_args__ = (
        UniqueConstraint("connector_id", "slug", name="uq_action_connector_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    connector_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("connectors.id"), nullable=True, index=True
    )  # NULL = template action (OOB)
    platform_template: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )  # Set on templates, NULL on instance actions

    # Identity
    slug: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    category: Mapped[str | None] = mapped_column(String(100), nullable=True)  # Grouping

    # HTTP Definition
    method: Mapped[str] = mapped_column(String(10), nullable=False, default="GET")
    endpoint_path: Mapped[str] = mapped_column(
        String(500), nullable=False
    )  # URL path template (e.g., "/v1/chat/completions")
    base_url: Mapped[str | None] = mapped_column(
        String(500), nullable=True
    )  # Override connector's default
    headers_template: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # {key: "value with {credential_key} interpolation"}

    # Schemas
    parameters_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # JSON Schema for inputs
    response_schema: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # JSON Schema for outputs
    request_body_template: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Default body

    # Execution
    requires_confirmation: Mapped[bool] = mapped_column(Boolean, default=False)
    timeout_seconds: Mapped[int] = mapped_column(Integer, default=30)

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    connector: Mapped["Connector | None"] = relationship(back_populates="actions")
