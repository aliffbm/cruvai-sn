"""Capability Service — resolves which specialist agents a primary can delegate to.

Used at runtime by base_agent to build the delegation prompt section and
to resolve `delegate_to(slug, task)` tool invocations.
"""

from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.agent import AgentDefinition
from app.models.control_plane import AgentCapability

logger = logging.getLogger(__name__)


# Max delegation depth — guards against A→B→A cycles regardless of DB content.
MAX_DELEGATION_DEPTH = 3


@dataclass(frozen=True)
class Specialist:
    specialist_id: uuid.UUID
    specialist_slug: str
    specialist_name: str
    description: str | None
    delegation_context: str | None
    trigger_keywords: list[str]
    invocation_mode: str
    priority: int
    requires_approval: bool


class CapabilityResolver:
    """In-memory cached resolver for AgentCapability rows.

    Cache is (primary_agent_slug, org_id) → (specialists, fetched_at_epoch).
    TTL is short (60s) because edits should take effect quickly.
    """

    _TTL_SECONDS = 60.0

    def __init__(self) -> None:
        self._cache: dict[tuple[str, str | None], tuple[list[Specialist], float]] = {}

    def invalidate(self) -> None:
        self._cache.clear()

    # -------------------------------------------------------------------
    # Sync (workers)
    # -------------------------------------------------------------------

    def get_specialists_for_sync(
        self,
        db: Session,
        primary_agent_slug: str,
        org_id: uuid.UUID | None = None,
    ) -> list[Specialist]:
        key = (primary_agent_slug, str(org_id) if org_id else None)
        cached = self._cache.get(key)
        now = time.monotonic()
        if cached and (now - cached[1]) < self._TTL_SECONDS:
            return cached[0]

        primary_id = db.execute(
            select(AgentDefinition.id).where(AgentDefinition.slug == primary_agent_slug)
        ).scalar_one_or_none()
        if primary_id is None:
            self._cache[key] = ([], now)
            return []

        rows = db.execute(
            select(AgentCapability, AgentDefinition)
            .join(AgentDefinition, AgentCapability.specialist_agent_id == AgentDefinition.id)
            .where(
                AgentCapability.primary_agent_id == primary_id,
                AgentCapability.is_active.is_(True),
                AgentDefinition.is_active.is_(True),
            )
            .order_by(AgentCapability.priority.asc())
        ).all()

        specialists = [
            Specialist(
                specialist_id=agent.id,
                specialist_slug=agent.slug,
                specialist_name=agent.name,
                description=agent.description,
                delegation_context=cap.delegation_context,
                trigger_keywords=list(cap.trigger_keywords or []),
                invocation_mode=cap.invocation_mode,
                priority=cap.priority,
                requires_approval=cap.requires_approval,
            )
            for cap, agent in rows
        ]
        self._cache[key] = (specialists, now)
        return specialists

    # -------------------------------------------------------------------
    # Async (API)
    # -------------------------------------------------------------------

    async def get_specialists_for(
        self,
        db: AsyncSession,
        primary_agent_slug: str,
        org_id: uuid.UUID | None = None,
    ) -> list[Specialist]:
        result = await db.execute(
            select(AgentDefinition.id).where(AgentDefinition.slug == primary_agent_slug)
        )
        primary_id = result.scalar_one_or_none()
        if primary_id is None:
            return []

        rows = (
            await db.execute(
                select(AgentCapability, AgentDefinition)
                .join(
                    AgentDefinition,
                    AgentCapability.specialist_agent_id == AgentDefinition.id,
                )
                .where(
                    AgentCapability.primary_agent_id == primary_id,
                    AgentCapability.is_active.is_(True),
                    AgentDefinition.is_active.is_(True),
                )
                .order_by(AgentCapability.priority.asc())
            )
        ).all()
        return [
            Specialist(
                specialist_id=agent.id,
                specialist_slug=agent.slug,
                specialist_name=agent.name,
                description=agent.description,
                delegation_context=cap.delegation_context,
                trigger_keywords=list(cap.trigger_keywords or []),
                invocation_mode=cap.invocation_mode,
                priority=cap.priority,
                requires_approval=cap.requires_approval,
            )
            for cap, agent in rows
        ]

    # -------------------------------------------------------------------
    # Delegation prompt block
    # -------------------------------------------------------------------

    def render_delegation_block(self, specialists: list[Specialist]) -> str:
        """Produce a markdown section to append to a primary agent's system prompt."""

        if not specialists:
            return ""
        lines = [
            "## Available Specialists",
            "",
            "You may delegate sub-tasks to these specialists using the "
            "`delegate_to(specialist_slug, task)` tool. Each delegation counts "
            f"against the overall step budget; max nesting depth is {MAX_DELEGATION_DEPTH}.",
            "",
        ]
        for s in specialists:
            line = f"- **`{s.specialist_slug}`** — {s.specialist_name}"
            if s.delegation_context:
                line += f": {s.delegation_context}"
            elif s.description:
                line += f": {s.description[:160]}"
            if s.trigger_keywords:
                line += f"  _(triggers: {', '.join(s.trigger_keywords)})_"
            lines.append(line)
        return "\n".join(lines)


# Singleton
capability_resolver = CapabilityResolver()
