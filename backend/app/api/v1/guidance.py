"""Guidance Library API — CRUD for AgentGuidance + version/label management.

Supports the Guidance Library UI, Rewrite Queue, and IP Compliance pages.
"""

from __future__ import annotations

import difflib
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_org_id, get_current_user, get_db
from app.models.control_plane import (
    AgentGuidance, AgentGuidanceLabel, AgentGuidanceVersion,
)
from app.services.guidance_service import PromotionBlocked, guidance_service

router = APIRouter()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------


class GuidanceResponse(BaseModel):
    id: uuid.UUID
    organization_id: uuid.UUID | None
    slug: str
    name: str
    description: str | None
    guidance_type: str
    agent_types: list | None
    tags: list | None
    source_uri: str | None
    source_origin: str
    requires_rewrite: bool
    license_type: str | None
    is_system: bool
    is_active: bool
    is_orphaned: bool
    has_cruvai_version: bool = False
    latest_version_number: int | None = None
    labels: list[dict] = []

    model_config = {"from_attributes": True}


class VersionResponse(BaseModel):
    id: uuid.UUID
    guidance_id: uuid.UUID
    version_number: int
    content: str
    content_hash: str
    frontmatter: dict | None
    sections: dict | None
    asset_manifest: list | None
    authorship: str
    derived_from_version_id: uuid.UUID | None
    rewrite_summary: str | None
    change_notes: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class VersionCreate(BaseModel):
    content: str
    change_notes: str | None = None
    rewrite_summary: str | None = None
    derived_from_version_id: uuid.UUID | None = None
    authorship: str = "cruvai-authored"


class LabelPromote(BaseModel):
    version_id: uuid.UUID
    label: str
    traffic_weight: int = 100


# ---------------------------------------------------------------------------
# Guidance CRUD + queries
# ---------------------------------------------------------------------------


@router.get("", response_model=list[GuidanceResponse])
async def list_guidance(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
    requires_rewrite: bool | None = Query(None),
    source_origin: str | None = Query(None),
    guidance_type: str | None = Query(None),
    include_system: bool = Query(True),
):
    """List all guidance visible to the caller's org (own + system)."""

    filters = [AgentGuidance.is_active.is_(True)]
    if include_system:
        filters.append(
            (AgentGuidance.organization_id == org_id)
            | AgentGuidance.organization_id.is_(None)
        )
    else:
        filters.append(AgentGuidance.organization_id == org_id)
    if requires_rewrite is not None:
        filters.append(AgentGuidance.requires_rewrite.is_(requires_rewrite))
    if source_origin:
        filters.append(AgentGuidance.source_origin == source_origin)
    if guidance_type:
        filters.append(AgentGuidance.guidance_type == guidance_type)

    rows = (
        await db.execute(
            select(AgentGuidance).where(and_(*filters)).order_by(AgentGuidance.slug)
        )
    ).scalars().all()

    # Enrich: latest_version_number, has_cruvai_version, labels
    result: list[GuidanceResponse] = []
    for g in rows:
        latest_version_number = (
            await db.execute(
                select(func.max(AgentGuidanceVersion.version_number)).where(
                    AgentGuidanceVersion.guidance_id == g.id
                )
            )
        ).scalar()
        has_cruvai = (
            await db.execute(
                select(func.count(AgentGuidanceVersion.id)).where(
                    AgentGuidanceVersion.guidance_id == g.id,
                    AgentGuidanceVersion.authorship.in_(["cruvai-authored", "org-authored"]),
                )
            )
        ).scalar() or 0
        labels = (
            await db.execute(
                select(AgentGuidanceLabel).where(
                    AgentGuidanceLabel.guidance_id == g.id,
                    AgentGuidanceLabel.is_active.is_(True),
                )
            )
        ).scalars().all()
        result.append(
            GuidanceResponse(
                id=g.id,
                organization_id=g.organization_id,
                slug=g.slug,
                name=g.name,
                description=g.description,
                guidance_type=g.guidance_type,
                agent_types=g.agent_types,
                tags=g.tags,
                source_uri=g.source_uri,
                source_origin=g.source_origin,
                requires_rewrite=g.requires_rewrite,
                license_type=g.license_type,
                is_system=g.is_system,
                is_active=g.is_active,
                is_orphaned=g.is_orphaned,
                has_cruvai_version=has_cruvai > 0,
                latest_version_number=latest_version_number,
                labels=[
                    {
                        "label": lb.label,
                        "version_id": str(lb.version_id),
                        "traffic_weight": lb.traffic_weight,
                    }
                    for lb in labels
                ],
            )
        )
    return result


@router.get("/rewrite-queue", response_model=list[GuidanceResponse])
async def rewrite_queue(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Licensed guidance awaiting a cruvai-authored rewrite."""

    rows = (
        await db.execute(
            select(AgentGuidance).where(
                AgentGuidance.requires_rewrite.is_(True),
                AgentGuidance.is_active.is_(True),
                (
                    (AgentGuidance.organization_id == org_id)
                    | AgentGuidance.organization_id.is_(None)
                ),
            )
        )
    ).scalars().all()
    queue: list[GuidanceResponse] = []
    for g in rows:
        has_cruvai = (
            await db.execute(
                select(func.count(AgentGuidanceVersion.id)).where(
                    AgentGuidanceVersion.guidance_id == g.id,
                    AgentGuidanceVersion.authorship.in_(["cruvai-authored", "org-authored"]),
                )
            )
        ).scalar() or 0
        if has_cruvai > 0:
            continue
        queue.append(
            GuidanceResponse.model_validate(g).model_copy(update={"has_cruvai_version": False})
        )
    return queue


@router.get("/{guidance_id}", response_model=GuidanceResponse)
async def get_guidance(
    guidance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    g = (await db.execute(select(AgentGuidance).where(AgentGuidance.id == guidance_id))).scalar_one_or_none()
    if g is None:
        raise HTTPException(404, "Guidance not found")
    # Tenancy: visible if org-scoped match or system row
    if g.organization_id is not None and g.organization_id != org_id:
        raise HTTPException(404, "Guidance not found")
    return GuidanceResponse.model_validate(g)


# ---------------------------------------------------------------------------
# Versions
# ---------------------------------------------------------------------------


@router.get("/{guidance_id}/versions", response_model=list[VersionResponse])
async def list_versions(
    guidance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    rows = (
        await db.execute(
            select(AgentGuidanceVersion)
            .where(AgentGuidanceVersion.guidance_id == guidance_id)
            .order_by(AgentGuidanceVersion.version_number.desc())
        )
    ).scalars().all()
    return [VersionResponse.model_validate(v) for v in rows]


@router.post("/{guidance_id}/versions", response_model=VersionResponse)
async def create_version(
    guidance_id: uuid.UUID,
    body: VersionCreate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    version = await guidance_service.create_version(
        db,
        guidance_id,
        body.content,
        authorship=body.authorship,
        derived_from_version_id=body.derived_from_version_id,
        rewrite_summary=body.rewrite_summary,
        change_notes=body.change_notes,
        user_id=user.id,
    )
    await db.commit()
    await db.refresh(version)
    return VersionResponse.model_validate(version)


@router.get("/{guidance_id}/versions/{version_id}/diff")
async def version_diff(
    guidance_id: uuid.UUID,
    version_id: uuid.UUID,
    against: uuid.UUID | None = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Unified diff between `version_id` and `against` (or the immediate previous version)."""

    a = (await db.execute(select(AgentGuidanceVersion).where(AgentGuidanceVersion.id == version_id))).scalar_one_or_none()
    if a is None or a.guidance_id != guidance_id:
        raise HTTPException(404, "Version not found")
    if against is not None:
        b = (await db.execute(select(AgentGuidanceVersion).where(AgentGuidanceVersion.id == against))).scalar_one_or_none()
    else:
        b = (
            await db.execute(
                select(AgentGuidanceVersion)
                .where(
                    AgentGuidanceVersion.guidance_id == guidance_id,
                    AgentGuidanceVersion.version_number < a.version_number,
                )
                .order_by(AgentGuidanceVersion.version_number.desc())
                .limit(1)
            )
        ).scalar_one_or_none()
    if b is None:
        return {"diff": "", "a_version": a.version_number, "b_version": None}
    diff_lines = list(
        difflib.unified_diff(
            b.content.splitlines(keepends=False),
            a.content.splitlines(keepends=False),
            fromfile=f"v{b.version_number}",
            tofile=f"v{a.version_number}",
            lineterm="",
        )
    )
    return {"diff": "\n".join(diff_lines), "a_version": a.version_number, "b_version": b.version_number}


# ---------------------------------------------------------------------------
# Labels
# ---------------------------------------------------------------------------


@router.post("/{guidance_id}/labels")
async def promote_label(
    guidance_id: uuid.UUID,
    body: LabelPromote,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    try:
        label = await guidance_service.promote_version(
            db,
            guidance_id,
            body.version_id,
            body.label,
            traffic_weight=body.traffic_weight,
            user_id=user.id,
            audit_org_id=user.organization_id,
        )
    except PromotionBlocked as exc:
        await db.commit()  # persist the audit-log row written inside the guard
        raise HTTPException(409, str(exc))
    await db.commit()
    await db.refresh(label)
    return {
        "id": str(label.id),
        "guidance_id": str(label.guidance_id),
        "version_id": str(label.version_id),
        "label": label.label,
        "traffic_weight": label.traffic_weight,
        "activated_at": label.activated_at.isoformat() if label.activated_at else None,
    }


# ---------------------------------------------------------------------------
# IP Compliance report
# ---------------------------------------------------------------------------


@router.get("/compliance/licensed-guidance")
async def licensed_guidance_report(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Per-org IP compliance: licensed skills + rewrite/production status."""

    rows = (
        await db.execute(
            select(AgentGuidance).where(
                AgentGuidance.requires_rewrite.is_(True),
                AgentGuidance.is_active.is_(True),
                (
                    (AgentGuidance.organization_id == org_id)
                    | AgentGuidance.organization_id.is_(None)
                ),
            )
        )
    ).scalars().all()
    report: list[dict[str, Any]] = []
    for g in rows:
        has_cruvai = (
            await db.execute(
                select(func.count(AgentGuidanceVersion.id)).where(
                    AgentGuidanceVersion.guidance_id == g.id,
                    AgentGuidanceVersion.authorship.in_(["cruvai-authored", "org-authored"]),
                )
            )
        ).scalar() or 0
        prod_label = (
            await db.execute(
                select(AgentGuidanceLabel).where(
                    AgentGuidanceLabel.guidance_id == g.id,
                    AgentGuidanceLabel.label == "production",
                    AgentGuidanceLabel.is_active.is_(True),
                )
            )
        ).scalar_one_or_none()
        prod_authorship = None
        if prod_label:
            ver = (
                await db.execute(
                    select(AgentGuidanceVersion.authorship).where(
                        AgentGuidanceVersion.id == prod_label.version_id
                    )
                )
            ).scalar_one_or_none()
            prod_authorship = ver
        report.append(
            {
                "slug": g.slug,
                "name": g.name,
                "license_type": g.license_type,
                "has_cruvai_version": has_cruvai > 0,
                "production_authorship": prod_authorship,
                "compliant": (prod_label is not None and prod_authorship in {"cruvai-authored", "org-authored"}),
            }
        )
    return report
