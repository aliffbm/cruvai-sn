"""Playbook Service — resolves ServiceNow-archetype routing for a story.

Given a project's active playbook (e.g. `servicenow-platform-product`) and
a story's text, picks the primary agent, supporting agents to spawn in
parallel, and required guidance IDs to force-inject into context.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.control_plane import (
    AgentPlaybook, AgentPlaybookLabel, AgentPlaybookRoute, AgentPlaybookVersion,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PlaybookMatch:
    playbook_slug: str
    playbook_name: str
    primary_agent_id: uuid.UUID | None
    supporting_agent_ids: list[uuid.UUID]
    required_guidance_ids: list[uuid.UUID]
    matched_pattern: str
    match_type: str


class PlaybookService:
    """Selects routes based on task text and a project's active playbook."""

    def resolve_for_story_sync(
        self,
        db: Session,
        *,
        playbook_slug: str | None,
        story_title: str,
        story_description: str | None,
        org_id: uuid.UUID | None = None,
    ) -> PlaybookMatch | None:
        """Resolve the first matching route. Returns None if no match or no playbook."""

        if not playbook_slug:
            return None

        playbook = self._load_active_playbook(db, playbook_slug, org_id)
        if playbook is None:
            return None

        routes = db.execute(
            select(AgentPlaybookRoute)
            .where(
                AgentPlaybookRoute.playbook_id == playbook.id,
                AgentPlaybookRoute.is_active.is_(True),
            )
            .order_by(AgentPlaybookRoute.priority.asc())
        ).scalars().all()

        task_text = " ".join(filter(None, [story_title, story_description])).lower()

        for route in routes:
            if self._route_matches(route, task_text):
                return PlaybookMatch(
                    playbook_slug=playbook.slug,
                    playbook_name=playbook.name,
                    primary_agent_id=route.primary_agent_id,
                    supporting_agent_ids=[
                        uuid.UUID(s) if isinstance(s, str) else s
                        for s in (route.supporting_agent_ids or [])
                    ],
                    required_guidance_ids=[
                        uuid.UUID(g) if isinstance(g, str) else g
                        for g in (route.required_guidance_ids or [])
                    ],
                    matched_pattern=route.task_pattern,
                    match_type=route.match_type,
                )
        return None

    # ------------------------------------------------------------------

    def _load_active_playbook(
        self,
        db: Session,
        slug: str,
        org_id: uuid.UUID | None,
    ) -> AgentPlaybook | None:
        """Resolve org → system precedence, prefer `production` label when present."""

        for target in ([org_id, None] if org_id else [None]):
            row = db.execute(
                select(AgentPlaybook).where(
                    AgentPlaybook.slug == slug,
                    AgentPlaybook.is_active.is_(True),
                    AgentPlaybook.is_orphaned.is_(False),
                    AgentPlaybook.organization_id == target
                    if target is not None
                    else AgentPlaybook.organization_id.is_(None),
                )
            ).scalar_one_or_none()
            if row is not None:
                return row
        return None

    def _route_matches(self, route: AgentPlaybookRoute, task_text: str) -> bool:
        pattern = (route.task_pattern or "").strip()
        if not pattern or pattern == "*":
            return True
        if route.match_type == "regex":
            try:
                return re.search(pattern, task_text, re.IGNORECASE) is not None
            except re.error:
                logger.warning("Invalid regex in playbook route: %s", pattern)
                return False
        # Default: keywords — split on comma/semicolon, match any token as substring
        tokens = [t.strip().lower() for t in re.split(r"[,;|]", pattern) if t.strip()]
        if not tokens:
            return pattern.lower() in task_text
        return any(t in task_text for t in tokens)


# Singleton
playbook_service = PlaybookService()
