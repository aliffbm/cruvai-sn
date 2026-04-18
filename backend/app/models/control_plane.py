"""AI Control Plane models — versioned prompts and skills stored in DB.

Enterprise-grade: per-org isolation, immutable versions, deployment labels,
audit trail, and API-accessible for remote OpenClaw instances.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer,
    String, Text, UniqueConstraint, func
)
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class AgentPrompt(TimestampMixin, Base):
    __tablename__ = "agent_prompts"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_prompt_org_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )  # NULL = OOB system prompt (visible to all orgs)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_type: Mapped[str | None] = mapped_column(
        String(50), nullable=True
    )  # catalog, portal, atf, etc. NULL = shared across agents
    category: Mapped[str] = mapped_column(
        String(100), default="system"
    )  # system, task, shared_context, analysis
    tags: Mapped[dict | None] = mapped_column(JSON, default=list)
    template_format: Mapped[str] = mapped_column(String(20), default="jinja2")  # jinja2, plain
    default_variables: Mapped[dict | None] = mapped_column(JSON, default=dict)
    model_params: Mapped[dict | None] = mapped_column(
        JSON, default=dict
    )  # {"model": "...", "max_tokens": 4096, "temperature": 0.7}
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    versions: Mapped[list["AgentPromptVersion"]] = relationship(
        back_populates="prompt", order_by="AgentPromptVersion.version_number.desc()"
    )
    labels: Mapped[list["AgentPromptLabel"]] = relationship(back_populates="prompt")


class AgentPromptVersion(Base):
    __tablename__ = "agent_prompt_versions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_prompts.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # The Jinja2 template
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    sections: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # Structured sections for targeted editing
    variables_schema: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # JSON Schema for expected variables
    change_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    prompt: Mapped["AgentPrompt"] = relationship(back_populates="versions")


class AgentPromptLabel(TimestampMixin, Base):
    __tablename__ = "agent_prompt_labels"
    __table_args__ = (
        UniqueConstraint("prompt_id", "label", name="uq_prompt_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    prompt_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_prompts.id"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_prompt_versions.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)  # production, staging, canary
    traffic_weight: Mapped[int] = mapped_column(Integer, default=100)  # 0-100 for A/B testing
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    activated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    prompt: Mapped["AgentPrompt"] = relationship(back_populates="labels")
    version: Mapped["AgentPromptVersion"] = relationship()


class AgentSkill(TimestampMixin, Base):
    __tablename__ = "agent_skills"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_skill_org_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    agent_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    pre_conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    post_conditions: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_composite: Mapped[bool] = mapped_column(Boolean, default=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    steps: Mapped[list["AgentSkillStep"]] = relationship(
        back_populates="skill",
        foreign_keys="AgentSkillStep.skill_id",
        order_by="AgentSkillStep.step_number",
    )


class AgentSkillStep(TimestampMixin, Base):
    __tablename__ = "agent_skill_steps"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    skill_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_skills.id"), nullable=False, index=True
    )
    step_number: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    step_type: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # tool_call, llm_call, sub_skill, conditional, loop
    tool_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    sub_skill_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_skills.id"), nullable=True
    )
    prompt_slug: Mapped[str | None] = mapped_column(String(200), nullable=True)
    input_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    output_mapping: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    condition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retry_policy: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    is_approval_gate: Mapped[bool] = mapped_column(Boolean, default=False)

    skill: Mapped["AgentSkill"] = relationship(
        back_populates="steps", foreign_keys=[skill_id]
    )
    sub_skill: Mapped["AgentSkill | None"] = relationship(foreign_keys=[sub_skill_id])


# ---------------------------------------------------------------------------
# Toolkit ingestion models — governed guidance, specialist delegation, playbooks
# Mirrors the AgentPrompt/Version/Label governance pattern for authored content
# imported from the AI Knowledge Repository toolkit.
# ---------------------------------------------------------------------------


class AgentGuidance(TimestampMixin, Base):
    """Procedural/reference knowledge (parallels AgentPrompt but for skills/workflows).

    Used for the 31 SKILL.md files from ~/.claude/skills/. Unlike AgentSkill
    (which is for step-DAG orchestration), AgentGuidance holds markdown
    knowledge that gets injected into agent context at runtime.
    """

    __tablename__ = "agent_guidance"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_guidance_org_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )  # NULL = OOB system guidance (visible to all orgs)
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    guidance_type: Mapped[str] = mapped_column(
        String(50), default="procedural"
    )  # procedural, reference, template, checklist
    trigger_criteria: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    agent_types: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # list of agent_type slugs; NULL = global
    tags: Mapped[list | None] = mapped_column(JSON, default=list)
    source_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_origin: Mapped[str] = mapped_column(
        String(50), default="authored"
    )  # anthropic-toolkit, authored, community
    requires_rewrite: Mapped[bool] = mapped_column(
        Boolean, default=False
    )  # True when upstream ships LICENSE; blocks production promotion
    license_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    original_license_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_orphaned: Mapped[bool] = mapped_column(Boolean, default=False)

    versions: Mapped[list["AgentGuidanceVersion"]] = relationship(
        back_populates="guidance",
        order_by="AgentGuidanceVersion.version_number.desc()",
        foreign_keys="AgentGuidanceVersion.guidance_id",
    )
    labels: Mapped[list["AgentGuidanceLabel"]] = relationship(back_populates="guidance")


class AgentGuidanceVersion(Base):
    """Immutable version of guidance content. Mirrors AgentPromptVersion."""

    __tablename__ = "agent_guidance_versions"
    __table_args__ = (
        UniqueConstraint("guidance_id", "version_number", name="uq_guidance_version"),
        Index("ix_guidance_version_content_hash", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guidance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_guidance.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Markdown body
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)  # SHA-256
    frontmatter: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    sections: Mapped[dict | None] = mapped_column(
        JSON, nullable=True
    )  # H2 heading map for diff UI
    asset_manifest: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # list of {path, sha256, size, object_key}
    authorship: Mapped[str] = mapped_column(
        String(30), default="authored"
    )  # anthropic-toolkit, cruvai-authored, community, org-authored
    derived_from_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_guidance_versions.id"), nullable=True
    )
    rewrite_summary: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # Author's enhancement notes (IP defensibility artifact)
    change_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    guidance: Mapped["AgentGuidance"] = relationship(
        back_populates="versions", foreign_keys=[guidance_id]
    )
    derived_from: Mapped["AgentGuidanceVersion | None"] = relationship(
        remote_side="AgentGuidanceVersion.id", foreign_keys=[derived_from_version_id]
    )
    assets: Mapped[list["GuidanceAsset"]] = relationship(back_populates="version")


class AgentGuidanceLabel(TimestampMixin, Base):
    """Deployment label (production/staging/canary) pointing at a guidance version."""

    __tablename__ = "agent_guidance_labels"
    __table_args__ = (
        UniqueConstraint("guidance_id", "label", name="uq_guidance_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guidance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_guidance.id"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_guidance_versions.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    traffic_weight: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    activated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    guidance: Mapped["AgentGuidance"] = relationship(back_populates="labels")
    version: Mapped["AgentGuidanceVersion"] = relationship()


class AgentCapability(TimestampMixin, Base):
    """Delegation graph — who can delegate to whom among AgentDefinitions.

    Wires the 32 specialist agents into Cruvai's primary ServiceNow agents so
    the Portal agent can delegate React work to react-specialist, security
    audits to security-auditor, etc.
    """

    __tablename__ = "agent_capabilities"
    __table_args__ = (
        UniqueConstraint("primary_agent_id", "specialist_agent_id", name="uq_capability_pair"),
        CheckConstraint(
            "primary_agent_id <> specialist_agent_id", name="ck_capability_no_self"
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    primary_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_definitions.id"), nullable=False, index=True
    )
    specialist_agent_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_definitions.id"), nullable=False, index=True
    )
    delegation_context: Mapped[str | None] = mapped_column(Text, nullable=True)
    trigger_keywords: Mapped[list | None] = mapped_column(JSON, default=list)
    invocation_mode: Mapped[str] = mapped_column(
        String(20), default="sub_agent"
    )  # sub_agent, handoff, parallel
    priority: Mapped[int] = mapped_column(Integer, default=100)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)


class AgentPlaybook(TimestampMixin, Base):
    """ServiceNow archetype playbook (platform-product, scoped-app, etc.).

    Maps task patterns to primary+supporting agents and required guidance,
    so a Project's archetype drives agent routing automatically.
    """

    __tablename__ = "agent_playbooks"
    __table_args__ = (
        UniqueConstraint("organization_id", "slug", name="uq_playbook_org_slug"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=True, index=True
    )
    slug: Mapped[str] = mapped_column(String(200), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_uri: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_origin: Mapped[str] = mapped_column(String(50), default="authored")
    is_system: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_orphaned: Mapped[bool] = mapped_column(Boolean, default=False)

    versions: Mapped[list["AgentPlaybookVersion"]] = relationship(
        back_populates="playbook",
        order_by="AgentPlaybookVersion.version_number.desc()",
    )
    labels: Mapped[list["AgentPlaybookLabel"]] = relationship(back_populates="playbook")
    routes: Mapped[list["AgentPlaybookRoute"]] = relationship(
        back_populates="playbook", order_by="AgentPlaybookRoute.priority"
    )


class AgentPlaybookVersion(Base):
    """Immutable playbook snapshot."""

    __tablename__ = "agent_playbook_versions"
    __table_args__ = (
        UniqueConstraint("playbook_id", "version_number", name="uq_playbook_version"),
        Index("ix_playbook_version_content_hash", "content_hash"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_playbooks.id"), nullable=False, index=True
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)  # Raw markdown
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    stack_manifest: Mapped[list | None] = mapped_column(
        JSON, nullable=True
    )  # Parsed "canonical stack" table
    load_bearing_skills: Mapped[list | None] = mapped_column(
        JSON, default=list
    )  # list of guidance slugs
    change_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    playbook: Mapped["AgentPlaybook"] = relationship(back_populates="versions")


class AgentPlaybookLabel(TimestampMixin, Base):
    """Deployment label for a playbook version."""

    __tablename__ = "agent_playbook_labels"
    __table_args__ = (
        UniqueConstraint("playbook_id", "label", name="uq_playbook_label"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_playbooks.id"), nullable=False, index=True
    )
    version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_playbook_versions.id"), nullable=False
    )
    label: Mapped[str] = mapped_column(String(50), nullable=False)
    traffic_weight: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    activated_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    activated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    playbook: Mapped["AgentPlaybook"] = relationship(back_populates="labels")
    version: Mapped["AgentPlaybookVersion"] = relationship()


class AgentPlaybookRoute(TimestampMixin, Base):
    """Task-pattern → agents + guidance mapping inside a playbook."""

    __tablename__ = "agent_playbook_routes"
    __table_args__ = (
        Index("ix_playbook_route_priority", "playbook_id", "priority"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    playbook_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_playbooks.id"), nullable=False, index=True
    )
    task_pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    match_type: Mapped[str] = mapped_column(
        String(20), default="keywords"
    )  # regex, keywords, embedding
    primary_agent_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("agent_definitions.id"), nullable=True
    )
    supporting_agent_ids: Mapped[list | None] = mapped_column(
        JSON, default=list
    )  # list of agent_definition UUIDs
    required_guidance_ids: Mapped[list | None] = mapped_column(
        JSON, default=list
    )  # list of guidance UUIDs to force-inject
    priority: Mapped[int] = mapped_column(Integer, default=100)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    playbook: Mapped["AgentPlaybook"] = relationship(back_populates="routes")


class GuidanceAsset(TimestampMixin, Base):
    """Auxiliary file attached to a guidance version (fonts, templates, code samples)."""

    __tablename__ = "guidance_assets"
    __table_args__ = (
        UniqueConstraint(
            "guidance_version_id", "relative_path", name="uq_guidance_asset_path"
        ),
        Index("ix_guidance_asset_sha256", "sha256"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    guidance_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_guidance_versions.id"),
        nullable=False,
        index=True,
    )
    relative_path: Mapped[str] = mapped_column(String(500), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_backend: Mapped[str] = mapped_column(
        String(20), default="filesystem"
    )  # filesystem, s3, minio
    object_key: Mapped[str] = mapped_column(String(1000), nullable=False)
    is_text: Mapped[bool] = mapped_column(Boolean, default=False)

    version: Mapped["AgentGuidanceVersion"] = relationship(back_populates="assets")


class ToolkitIngestionRun(Base):
    """Tracks each invocation of the toolkit ingestion CLI for governance/reporting."""

    __tablename__ = "toolkit_ingestion_runs"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    finished_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    source_root: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_commit: Mapped[str | None] = mapped_column(String(64), nullable=True)
    triggered_by_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(30), default="running"
    )  # running, succeeded, failed, partial
    stats: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    error_log: Mapped[str | None] = mapped_column(Text, nullable=True)
