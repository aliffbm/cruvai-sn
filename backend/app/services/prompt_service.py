"""Prompt Service — resolves, renders, and manages versioned prompts.

Enterprise-grade: per-org isolation, Jinja2 templating, version history,
deployment labels, in-memory cache, and OpenClaw-compatible render API.
"""

import hashlib
import logging
import random
import uuid
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any

import jinja2
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.models.control_plane import (
    AgentPrompt,
    AgentPromptLabel,
    AgentPromptVersion,
)

logger = logging.getLogger(__name__)

# Jinja2 environment — silently ignores undefined variables
_jinja_env = jinja2.Environment(undefined=jinja2.Undefined)


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class PromptService:
    """Centralized prompt management for agents and OpenClaw instances."""

    # --- Resolution ---

    async def resolve_prompt(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None,
        slug: str,
        label: str = "production",
    ) -> AgentPromptVersion | None:
        """Resolve a prompt version by slug and label.

        Resolution order:
        1. Org-specific prompt with matching slug + label
        2. System prompt (org_id=NULL) with matching slug + label
        """
        # Try org-specific first, then system
        for target_org_id in ([org_id, None] if org_id else [None]):
            result = await db.execute(
                select(AgentPromptLabel)
                .join(AgentPrompt, AgentPromptLabel.prompt_id == AgentPrompt.id)
                .where(
                    AgentPrompt.slug == slug,
                    AgentPrompt.is_active.is_(True),
                    AgentPromptLabel.label == label,
                    AgentPromptLabel.is_active.is_(True),
                    AgentPrompt.organization_id == target_org_id
                    if target_org_id
                    else AgentPrompt.organization_id.is_(None),
                )
                .options(selectinload(AgentPromptLabel.version))
            )
            prompt_label = result.scalar_one_or_none()
            if prompt_label:
                return prompt_label.version

        return None

    async def render_prompt(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None,
        slug: str,
        label: str = "production",
        variables: dict[str, Any] | None = None,
    ) -> str | None:
        """Resolve and render a prompt template with variables."""
        version = await self.resolve_prompt(db, org_id, slug, label)
        if not version:
            return None

        # Load default variables from the prompt
        result = await db.execute(
            select(AgentPrompt).where(AgentPrompt.id == version.prompt_id)
        )
        prompt = result.scalar_one_or_none()
        defaults = prompt.default_variables or {} if prompt else {}

        # Merge: defaults < provided variables
        merged = {**defaults, **(variables or {})}

        if prompt and prompt.template_format == "plain":
            return version.content

        try:
            template = _jinja_env.from_string(version.content)
            return template.render(**merged)
        except jinja2.TemplateError as e:
            logger.warning(f"Jinja2 render failed for {slug}: {e}, returning raw content")
            return version.content

    async def render_agent_system_prompt(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None,
        agent_type: str,
        variables: dict[str, Any] | None = None,
        label: str = "production",
    ) -> str | None:
        """Render the full system prompt for an agent type.

        Combines: shared-context + {agent_type}-agent-system
        """
        parts = []

        # Shared context (always included)
        shared = await self.render_prompt(db, org_id, "shared-context", label, variables)
        if shared:
            parts.append(shared)

        # Agent-specific prompt
        agent_slug = f"{agent_type}-agent-system"
        agent_prompt = await self.render_prompt(db, org_id, agent_slug, label, variables)
        if agent_prompt:
            parts.append(agent_prompt)

        return "\n\n".join(parts) if parts else None

    # --- Sync variants (for Celery workers) ---

    def resolve_prompt_sync(
        self, db: Session, org_id: uuid.UUID | None, slug: str, label: str = "production"
    ) -> AgentPromptVersion | None:
        for target_org_id in ([org_id, None] if org_id else [None]):
            result = db.execute(
                select(AgentPromptLabel)
                .join(AgentPrompt, AgentPromptLabel.prompt_id == AgentPrompt.id)
                .where(
                    AgentPrompt.slug == slug,
                    AgentPrompt.is_active.is_(True),
                    AgentPromptLabel.label == label,
                    AgentPromptLabel.is_active.is_(True),
                    AgentPrompt.organization_id == target_org_id
                    if target_org_id
                    else AgentPrompt.organization_id.is_(None),
                )
            )
            row = result.first()
            if row:
                prompt_label = row[0]
                # Load the version
                ver_result = db.execute(
                    select(AgentPromptVersion).where(
                        AgentPromptVersion.id == prompt_label.version_id
                    )
                )
                return ver_result.scalar_one_or_none()
        return None

    def render_prompt_sync(
        self, db: Session, org_id: uuid.UUID | None, slug: str,
        label: str = "production", variables: dict[str, Any] | None = None,
    ) -> str | None:
        version = self.resolve_prompt_sync(db, org_id, slug, label)
        if not version:
            return None

        prompt_result = db.execute(
            select(AgentPrompt).where(AgentPrompt.id == version.prompt_id)
        )
        prompt = prompt_result.scalar_one_or_none()
        defaults = prompt.default_variables or {} if prompt else {}
        merged = {**defaults, **(variables or {})}

        if prompt and prompt.template_format == "plain":
            return version.content

        try:
            template = _jinja_env.from_string(version.content)
            return template.render(**merged)
        except jinja2.TemplateError:
            return version.content

    def render_agent_system_prompt_sync(
        self, db: Session, org_id: uuid.UUID | None, agent_type: str,
        variables: dict[str, Any] | None = None, label: str = "production",
    ) -> str | None:
        parts = []
        shared = self.render_prompt_sync(db, org_id, "shared-context", label, variables)
        if shared:
            parts.append(shared)
        agent_prompt = self.render_prompt_sync(
            db, org_id, f"{agent_type}-agent-system", label, variables
        )
        if agent_prompt:
            parts.append(agent_prompt)
        return "\n\n".join(parts) if parts else None

    # --- Version Management ---

    async def create_version(
        self,
        db: AsyncSession,
        prompt_id: uuid.UUID,
        content: str,
        change_notes: str | None = None,
        sections: dict | None = None,
        variables_schema: dict | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentPromptVersion:
        """Create a new immutable version of a prompt."""
        # Get next version number
        result = await db.execute(
            select(func.coalesce(func.max(AgentPromptVersion.version_number), 0))
            .where(AgentPromptVersion.prompt_id == prompt_id)
        )
        max_version = result.scalar()

        version = AgentPromptVersion(
            prompt_id=prompt_id,
            version_number=max_version + 1,
            content=content,
            content_hash=_content_hash(content),
            sections=sections,
            variables_schema=variables_schema,
            change_notes=change_notes,
            created_by_id=user_id,
        )
        db.add(version)
        await db.flush()
        await db.refresh(version)
        return version

    async def promote_version(
        self,
        db: AsyncSession,
        prompt_id: uuid.UUID,
        version_id: uuid.UUID,
        label: str,
        user_id: uuid.UUID | None = None,
    ) -> AgentPromptLabel:
        """Point a deployment label to a specific version (create or update)."""
        result = await db.execute(
            select(AgentPromptLabel).where(
                AgentPromptLabel.prompt_id == prompt_id,
                AgentPromptLabel.label == label,
            )
        )
        existing = result.scalar_one_or_none()

        if existing:
            existing.version_id = version_id
            existing.activated_by_id = user_id
            existing.activated_at = datetime.now(timezone.utc)
            await db.flush()
            return existing
        else:
            prompt_label = AgentPromptLabel(
                prompt_id=prompt_id,
                version_id=version_id,
                label=label,
                activated_by_id=user_id,
                activated_at=datetime.now(timezone.utc),
            )
            db.add(prompt_label)
            await db.flush()
            await db.refresh(prompt_label)
            return prompt_label


# Singleton
prompt_service = PromptService()
