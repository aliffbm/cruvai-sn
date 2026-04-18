"""AI Gateway models — LLM model registry, routing rules, request logging, and spend tracking.

These models power the LLM Gateway service, providing:
- Model registration with cost tracking and capabilities
- Priority-based routing rules for model selection
- Request logging for observability (tokens, cost, latency)
- Monthly spend aggregation per org/provider/model
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, Float, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AiModelConfig(TimestampMixin, Base):
    """Registered LLM models with cost tracking and capabilities."""

    __tablename__ = "ai_model_configs"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_model_config_org_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    slug: Mapped[str] = mapped_column(String(100), nullable=False)  # e.g., "claude-sonnet-4"
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # anthropic, openai, deepseek, xai
    model_id: Mapped[str] = mapped_column(
        String(200), nullable=False
    )  # Provider's model identifier, e.g., "claude-sonnet-4-20250514"
    capabilities: Mapped[dict | None] = mapped_column(
        JSON, default=dict
    )  # {vision, function_calling, json_mode, streaming, max_context_tokens}
    default_params: Mapped[dict | None] = mapped_column(
        JSON, default=dict
    )  # {temperature, max_tokens, top_p}

    # Cost tracking (USD per 1K tokens)
    cost_per_1k_input: Mapped[float] = mapped_column(Float, default=0.0)
    cost_per_1k_output: Mapped[float] = mapped_column(Float, default=0.0)
    cost_per_1k_cached_input: Mapped[float] = mapped_column(Float, default=0.0)

    # Fallback chain
    fallback_model_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_model_configs.id"), nullable=True
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    fallback_model: Mapped["AiModelConfig | None"] = relationship(
        remote_side="AiModelConfig.id", foreign_keys=[fallback_model_id]
    )


class AiRoutingRule(TimestampMixin, Base):
    """Priority-based rules for selecting which model handles a prompt."""

    __tablename__ = "ai_routing_rules"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)  # Lower = higher priority

    # Match criteria (any non-null field must match)
    match_category: Mapped[str | None] = mapped_column(String(100), nullable=True)
    match_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    match_prompt_slugs: Mapped[list | None] = mapped_column(JSON, nullable=True)

    # Target model
    model_config_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_model_configs.id"), nullable=False
    )

    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    model_config: Mapped["AiModelConfig"] = relationship()


class AiRequestLog(Base):
    """Immutable log of every LLM call for observability and cost tracking."""

    __tablename__ = "ai_request_logs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False, index=True
    )

    # What was called
    prompt_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    prompt_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_prompt_versions.id"), nullable=True
    )
    model_config_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("ai_model_configs.id"), nullable=True
    )
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)

    # Tokens and cost
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cached_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Numeric(10, 6), default=0.0)

    # Performance
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(
        String(20), default="success"
    )  # success, error, timeout
    finish_reason: Mapped[str | None] = mapped_column(String(50), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Context
    source: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # agent, chat, control_plane
    job_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_jobs.id"), nullable=True
    )


class AiMonthlySpend(Base):
    """Aggregated monthly spend per org/provider/model."""

    __tablename__ = "ai_monthly_spend"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "year_month", "provider", "model",
            name="uq_ai_monthly_spend"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    year_month: Mapped[str] = mapped_column(String(7), nullable=False)  # "2026-04"
    provider: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)

    total_requests: Mapped[int] = mapped_column(Integer, default=0)
    total_input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    total_cost_usd: Mapped[float] = mapped_column(Numeric(12, 6), default=0.0)
    total_errors: Mapped[int] = mapped_column(Integer, default=0)

    budget_limit_usd: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
