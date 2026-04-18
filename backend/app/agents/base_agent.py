"""Base Agent — foundation class and LangGraph state schema for complex agents.

Simple agents (catalog) use direct LLM calls.
Complex agents (portal, figma) inherit from BaseGraphAgent and use LangGraph
StateGraph with 4 phases: research → planning → execution → reflection.
"""

import logging
import uuid
from dataclasses import dataclass, field
from typing import Any, TypedDict

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class AgentState(TypedDict, total=False):
    """Shared state schema for LangGraph-based agents.

    Carries all context through the 4-phase agent lifecycle:
    research → planning → execution → reflection
    """

    # Core
    messages: list[dict]
    goal: str
    current_phase: str  # research, planning, execution, reflection

    # Work items
    tasks: list[dict]  # Decomposed work items from planning phase
    artifacts_created: list[dict]  # SN artifacts created during execution

    # Context
    story: dict  # User story details
    instance_context: dict  # SN instance info (version, capabilities)
    oob_assets: dict  # Discovered OOB widgets, themes, portals
    memory_context: list[dict]  # Retrieved agent memories

    # Governance
    pending_approvals: list[str]  # Actions waiting for human review
    decisions: list[dict]  # Audit trail of agent decisions

    # Job tracking
    job_id: str
    organization_id: str
    project_id: str

    # Completion
    completed: bool
    error: str | None
    summary: str


@dataclass
class AgentContext:
    """Runtime context injected into agents."""

    job_id: str
    organization_id: uuid.UUID
    project_id: uuid.UUID | None
    instance_id: uuid.UUID | None
    story_id: uuid.UUID | None
    db: Any  # SQLAlchemy Session
    connector: Any  # TableAPIConnector
    api_key: str
    system_prompt: str
    model: str = "claude-sonnet-4-20250514"


def create_initial_state(
    job_id: str,
    goal: str,
    story: dict | None = None,
    organization_id: str = "",
    project_id: str = "",
) -> AgentState:
    """Create the initial state for a LangGraph agent run."""
    return AgentState(
        messages=[],
        goal=goal,
        current_phase="research",
        tasks=[],
        artifacts_created=[],
        story=story or {},
        instance_context={},
        oob_assets={},
        memory_context=[],
        pending_approvals=[],
        decisions=[],
        job_id=job_id,
        organization_id=organization_id,
        project_id=project_id,
        completed=False,
        error=None,
        summary="",
    )


# ---------------------------------------------------------------------------
# Runtime enrichment — delegation + guidance injection
#
# Primary agents call build_enriched_system_prompt() to enrich their raw
# system prompt with (a) available specialists and (b) applicable guidance.
# Both come from the toolkit control-plane and respect org scoping.
# ---------------------------------------------------------------------------


def build_enriched_system_prompt(
    db: Session,
    *,
    agent_slug: str,
    base_system_prompt: str,
    org_id: uuid.UUID | None,
    triggers: list[str] | None = None,
    label: str = "production",
    max_guidance: int = 5,
) -> str:
    """Return `base_system_prompt` augmented with delegation + guidance sections.

    - Appends an "Available Specialists" section listing AgentCapability targets.
    - Appends an "Applicable Guidance" section with the top-N ranked guidance
      bodies for this agent and the provided `triggers` (typically keywords
      from the story title/description).
    """

    # Local imports avoid circular dependencies at module import time.
    from app.services.capability_service import capability_resolver
    from app.services.guidance_service import guidance_service

    sections: list[str] = [base_system_prompt.strip()] if base_system_prompt else []

    specialists = capability_resolver.get_specialists_for_sync(
        db, primary_agent_slug=agent_slug, org_id=org_id
    )
    delegation_block = capability_resolver.render_delegation_block(specialists)
    if delegation_block:
        sections.append(delegation_block)

    guidance_versions = guidance_service.resolve_guidance_for_agent_sync(
        db,
        org_id=org_id,
        agent_slug=agent_slug,
        triggers=triggers,
        label=label,
        top_n=max_guidance,
    )
    if guidance_versions:
        sections.append("## Applicable Guidance\n")
        for ver in guidance_versions:
            slug = ver.guidance.slug if ver.guidance else "(unknown)"
            name = ver.guidance.name if ver.guidance else slug
            sections.append(f"### {name} — `{slug}` (v{ver.version_number})")
            sections.append(ver.content.strip())
            sections.append("")

    return "\n\n".join(sections).strip()


def resolve_delegation_target(
    db: Session,
    *,
    primary_agent_slug: str,
    specialist_slug: str,
    org_id: uuid.UUID | None,
    current_depth: int,
) -> "Specialist | None":  # noqa: F821 - forward ref to capability_service
    """Validate a `delegate_to(specialist_slug, ...)` call at runtime.

    Enforces the max-depth cycle guard and confirms the target is an
    allowed capability of `primary_agent_slug`.
    """

    from app.services.capability_service import (
        MAX_DELEGATION_DEPTH, Specialist, capability_resolver,
    )

    if current_depth >= MAX_DELEGATION_DEPTH:
        logger.warning(
            "Delegation depth %d exceeds max %d; refusing delegate_to(%s)",
            current_depth, MAX_DELEGATION_DEPTH, specialist_slug,
        )
        return None
    specialists = capability_resolver.get_specialists_for_sync(
        db, primary_agent_slug=primary_agent_slug, org_id=org_id
    )
    for s in specialists:
        if s.specialist_slug == specialist_slug:
            return s
    logger.info(
        "delegate_to target %s not in capabilities of %s",
        specialist_slug, primary_agent_slug,
    )
    return None
