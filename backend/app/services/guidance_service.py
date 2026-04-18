"""Guidance Service — resolves, renders, ranks, and governs AgentGuidance.

Mirrors PromptService but adds:
  - Promotion guard: licensed guidance can't reach `production` until a
    `cruvai-authored` version exists (§4a of the plan).
  - Trigger-based ranking for agent runtime injection.
  - Weighted-random label resolution for canary/A-B testing.
"""

from __future__ import annotations

import hashlib
import logging
import random
import uuid
from datetime import datetime, timezone
from typing import Any, Iterable

import jinja2
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session, selectinload

from app.models.control_plane import (
    AgentGuidance, AgentGuidanceLabel, AgentGuidanceVersion,
)

logger = logging.getLogger(__name__)

_jinja_env = jinja2.Environment(undefined=jinja2.Undefined)


class PromotionBlocked(RuntimeError):
    """Raised when a governance rule forbids a label promotion."""


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


class GuidanceService:
    """Runtime + admin service for AgentGuidance."""

    # -------------------------------------------------------------------
    # Resolution (sync — called from workers; async variants below)
    # -------------------------------------------------------------------

    def resolve_guidance_sync(
        self,
        db: Session,
        org_id: uuid.UUID | None,
        slug: str,
        label: str = "production",
    ) -> AgentGuidanceVersion | None:
        """Resolve a guidance version by slug + label.

        Order: org-specific → system (org_id=NULL). Weighted-random pick
        across label rows sharing the same label (canary support).
        """

        for target_org_id in ([org_id, None] if org_id else [None]):
            condition = (
                AgentGuidance.organization_id == target_org_id
                if target_org_id
                else AgentGuidance.organization_id.is_(None)
            )
            rows = db.execute(
                select(AgentGuidanceLabel)
                .join(AgentGuidance, AgentGuidanceLabel.guidance_id == AgentGuidance.id)
                .where(
                    AgentGuidance.slug == slug,
                    AgentGuidance.is_active.is_(True),
                    AgentGuidance.is_orphaned.is_(False),
                    AgentGuidanceLabel.label == label,
                    AgentGuidanceLabel.is_active.is_(True),
                    condition,
                )
            ).scalars().all()
            if not rows:
                continue
            chosen = _weighted_choice(rows)
            if chosen is None:
                continue
            ver = db.execute(
                select(AgentGuidanceVersion).where(
                    AgentGuidanceVersion.id == chosen.version_id
                )
            ).scalar_one_or_none()
            if ver is not None:
                return ver
        return None

    def render_guidance_sync(
        self,
        db: Session,
        org_id: uuid.UUID | None,
        slug: str,
        label: str = "production",
        variables: dict[str, Any] | None = None,
    ) -> str | None:
        version = self.resolve_guidance_sync(db, org_id, slug, label)
        if version is None:
            return None
        try:
            return _jinja_env.from_string(version.content).render(**(variables or {}))
        except jinja2.TemplateError:
            # Guidance bodies are often plain markdown; render failure falls back to raw content.
            return version.content

    def resolve_guidance_for_agent_sync(
        self,
        db: Session,
        org_id: uuid.UUID | None,
        agent_slug: str,
        triggers: Iterable[str] | None = None,
        *,
        label: str = "production",
        top_n: int = 5,
    ) -> list[AgentGuidanceVersion]:
        """Return top-N guidance versions relevant to a given agent + trigger words.

        Ranking:
          - +2 for every matching element in guidance.agent_types
          - +1 per trigger-keyword hit in trigger_criteria.keywords
          - +0.5 if agent_types is NULL (global)
        """

        label_rows = db.execute(
            select(AgentGuidanceLabel, AgentGuidance)
            .join(AgentGuidance, AgentGuidanceLabel.guidance_id == AgentGuidance.id)
            .where(
                AgentGuidance.is_active.is_(True),
                AgentGuidance.is_orphaned.is_(False),
                AgentGuidanceLabel.label == label,
                AgentGuidanceLabel.is_active.is_(True),
                (
                    AgentGuidance.organization_id.is_(None)
                    if org_id is None
                    else (
                        (AgentGuidance.organization_id == org_id)
                        | AgentGuidance.organization_id.is_(None)
                    )
                ),
            )
        ).all()

        triggers_lc = [t.lower() for t in (triggers or [])]

        def score(g: AgentGuidance) -> float:
            s = 0.0
            agent_types = list(g.agent_types or [])
            if agent_types:
                if agent_slug in agent_types:
                    s += 2.0
            else:
                s += 0.5
            keywords = []
            if g.trigger_criteria and isinstance(g.trigger_criteria, dict):
                keywords = [str(k).lower() for k in (g.trigger_criteria.get("keywords") or [])]
            for kw in keywords:
                if any(kw in t for t in triggers_lc):
                    s += 1.0
            return s

        # Filter org precedence (org row shadows system row by slug)
        best_by_slug: dict[str, tuple[AgentGuidanceLabel, AgentGuidance, float]] = {}
        for lbl, g in label_rows:
            sc = score(g)
            if sc <= 0:
                continue
            prev = best_by_slug.get(g.slug)
            # Prefer org-owned over system when tied; higher score always wins
            if prev is None or sc > prev[2] or (
                sc == prev[2] and prev[1].organization_id is None and g.organization_id is not None
            ):
                best_by_slug[g.slug] = (lbl, g, sc)

        ranked = sorted(best_by_slug.values(), key=lambda t: t[2], reverse=True)[:top_n]
        if not ranked:
            return []
        version_ids = [lbl.version_id for (lbl, _g, _s) in ranked]
        versions = db.execute(
            select(AgentGuidanceVersion).where(AgentGuidanceVersion.id.in_(version_ids))
        ).scalars().all()
        by_id = {v.id: v for v in versions}
        return [by_id[vid] for vid in version_ids if vid in by_id]

    # -------------------------------------------------------------------
    # Async variants (for API routes)
    # -------------------------------------------------------------------

    async def resolve_guidance(
        self,
        db: AsyncSession,
        org_id: uuid.UUID | None,
        slug: str,
        label: str = "production",
    ) -> AgentGuidanceVersion | None:
        for target_org_id in ([org_id, None] if org_id else [None]):
            condition = (
                AgentGuidance.organization_id == target_org_id
                if target_org_id
                else AgentGuidance.organization_id.is_(None)
            )
            result = await db.execute(
                select(AgentGuidanceLabel)
                .join(AgentGuidance, AgentGuidanceLabel.guidance_id == AgentGuidance.id)
                .where(
                    AgentGuidance.slug == slug,
                    AgentGuidance.is_active.is_(True),
                    AgentGuidance.is_orphaned.is_(False),
                    AgentGuidanceLabel.label == label,
                    AgentGuidanceLabel.is_active.is_(True),
                    condition,
                )
                .options(selectinload(AgentGuidanceLabel.version))
            )
            rows = result.scalars().all()
            if not rows:
                continue
            chosen = _weighted_choice(rows)
            if chosen is not None:
                return chosen.version
        return None

    # -------------------------------------------------------------------
    # Version management
    # -------------------------------------------------------------------

    async def create_version(
        self,
        db: AsyncSession,
        guidance_id: uuid.UUID,
        content: str,
        *,
        authorship: str = "cruvai-authored",
        derived_from_version_id: uuid.UUID | None = None,
        rewrite_summary: str | None = None,
        change_notes: str | None = None,
        sections: dict | None = None,
        frontmatter: dict | None = None,
        user_id: uuid.UUID | None = None,
    ) -> AgentGuidanceVersion:
        """Create a new immutable version. Does not auto-promote labels."""

        result = await db.execute(
            select(func.coalesce(func.max(AgentGuidanceVersion.version_number), 0))
            .where(AgentGuidanceVersion.guidance_id == guidance_id)
        )
        max_version = result.scalar() or 0
        version = AgentGuidanceVersion(
            guidance_id=guidance_id,
            version_number=max_version + 1,
            content=content,
            content_hash=_content_hash(content),
            frontmatter=frontmatter,
            sections=sections,
            authorship=authorship,
            derived_from_version_id=derived_from_version_id,
            rewrite_summary=rewrite_summary,
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
        guidance_id: uuid.UUID,
        version_id: uuid.UUID,
        label: str,
        *,
        traffic_weight: int = 100,
        user_id: uuid.UUID | None = None,
        audit_org_id: uuid.UUID | None = None,
    ) -> AgentGuidanceLabel:
        """Point a deployment label at a version.

        Governance guard: if `guidance.requires_rewrite` is True and the
        target label is `production`, the version must be `cruvai-authored`
        (or `org-authored`) — otherwise raises `PromotionBlocked`.
        """

        guidance = (
            await db.execute(select(AgentGuidance).where(AgentGuidance.id == guidance_id))
        ).scalar_one_or_none()
        if guidance is None:
            raise ValueError(f"AgentGuidance {guidance_id} not found")

        version = (
            await db.execute(
                select(AgentGuidanceVersion).where(AgentGuidanceVersion.id == version_id)
            )
        ).scalar_one_or_none()
        if version is None:
            raise ValueError(f"AgentGuidanceVersion {version_id} not found")
        if version.guidance_id != guidance_id:
            raise ValueError("Version does not belong to guidance")

        if label == "production" and guidance.requires_rewrite:
            if version.authorship not in {"cruvai-authored", "org-authored"}:
                # Audit the blocked attempt for compliance reporting
                if audit_org_id is not None:
                    from app.services.audit_service import audit_service

                    await audit_service.record(
                        db,
                        organization_id=audit_org_id,
                        action="guidance.label.promotion_blocked",
                        resource_type="agent_guidance",
                        resource_id=guidance_id,
                        user_id=user_id,
                        details={
                            "attempted_label": label,
                            "version_authorship": version.authorship,
                            "reason": "requires_cruvai_authored",
                        },
                    )
                raise PromotionBlocked(
                    "Licensed content requires a Cruvai-authored version "
                    "before production promotion."
                )

        existing = (
            await db.execute(
                select(AgentGuidanceLabel).where(
                    AgentGuidanceLabel.guidance_id == guidance_id,
                    AgentGuidanceLabel.label == label,
                )
            )
        ).scalar_one_or_none()

        now = datetime.now(timezone.utc)
        if existing is not None:
            existing.version_id = version_id
            existing.traffic_weight = traffic_weight
            existing.activated_by_id = user_id
            existing.activated_at = now
            existing.is_active = True
            await db.flush()
            return existing

        row = AgentGuidanceLabel(
            guidance_id=guidance_id,
            version_id=version_id,
            label=label,
            traffic_weight=traffic_weight,
            is_active=True,
            activated_by_id=user_id,
            activated_at=now,
        )
        db.add(row)
        await db.flush()
        await db.refresh(row)

        if audit_org_id is not None:
            from app.services.audit_service import audit_service

            await audit_service.record(
                db,
                organization_id=audit_org_id,
                action="guidance.label.promoted",
                resource_type="agent_guidance",
                resource_id=guidance_id,
                user_id=user_id,
                details={
                    "label": label,
                    "version_id": str(version_id),
                    "version_number": version.version_number,
                    "authorship": version.authorship,
                    "traffic_weight": traffic_weight,
                },
            )
        return row


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _weighted_choice(rows: list[AgentGuidanceLabel]) -> AgentGuidanceLabel | None:
    if not rows:
        return None
    if len(rows) == 1:
        return rows[0]
    weights = [max(0, int(r.traffic_weight or 0)) for r in rows]
    total = sum(weights)
    if total <= 0:
        return rows[0]
    pick = random.uniform(0, total)
    acc = 0.0
    for row, w in zip(rows, weights):
        acc += w
        if pick <= acc:
            return row
    return rows[-1]


# Singleton
guidance_service = GuidanceService()
