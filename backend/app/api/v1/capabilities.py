"""Capabilities API — delegation graph management.

Powers the Specialist Catalog's Capabilities tab: who can delegate to whom.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_user, get_db
from app.models.agent import AgentDefinition
from app.models.control_plane import AgentCapability
from app.services.capability_service import capability_resolver

router = APIRouter()


class CapabilityCreate(BaseModel):
    primary_agent_id: uuid.UUID
    specialist_agent_id: uuid.UUID
    delegation_context: str | None = None
    trigger_keywords: list[str] = []
    invocation_mode: str = "sub_agent"
    priority: int = 100
    requires_approval: bool = False


class CapabilityUpdate(BaseModel):
    delegation_context: str | None = None
    trigger_keywords: list[str] | None = None
    invocation_mode: str | None = None
    priority: int | None = None
    requires_approval: bool | None = None
    is_active: bool | None = None


class CapabilityResponse(BaseModel):
    id: uuid.UUID
    primary_agent_id: uuid.UUID
    specialist_agent_id: uuid.UUID
    primary_slug: str | None = None
    specialist_slug: str | None = None
    delegation_context: str | None
    trigger_keywords: list[str]
    invocation_mode: str
    priority: int
    requires_approval: bool
    is_active: bool

    model_config = {"from_attributes": True}


async def _resolve_slugs(db: AsyncSession, row: AgentCapability) -> tuple[str | None, str | None]:
    result = await db.execute(
        select(AgentDefinition.id, AgentDefinition.slug).where(
            AgentDefinition.id.in_([row.primary_agent_id, row.specialist_agent_id])
        )
    )
    mapping = {r[0]: r[1] for r in result.all()}
    return mapping.get(row.primary_agent_id), mapping.get(row.specialist_agent_id)


@router.get("", response_model=list[CapabilityResponse])
async def list_capabilities(
    primary_agent_id: uuid.UUID | None = None,
    specialist_agent_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    stmt = select(AgentCapability)
    if primary_agent_id:
        stmt = stmt.where(AgentCapability.primary_agent_id == primary_agent_id)
    if specialist_agent_id:
        stmt = stmt.where(AgentCapability.specialist_agent_id == specialist_agent_id)
    rows = (await db.execute(stmt.order_by(AgentCapability.priority.asc()))).scalars().all()
    out: list[CapabilityResponse] = []
    for r in rows:
        p_slug, s_slug = await _resolve_slugs(db, r)
        resp = CapabilityResponse.model_validate(r).model_copy(
            update={"primary_slug": p_slug, "specialist_slug": s_slug, "trigger_keywords": list(r.trigger_keywords or [])}
        )
        out.append(resp)
    return out


@router.post("", response_model=CapabilityResponse, status_code=201)
async def create_capability(
    body: CapabilityCreate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    if body.primary_agent_id == body.specialist_agent_id:
        raise HTTPException(400, "primary_agent_id and specialist_agent_id must differ")
    row = AgentCapability(
        primary_agent_id=body.primary_agent_id,
        specialist_agent_id=body.specialist_agent_id,
        delegation_context=body.delegation_context,
        trigger_keywords=body.trigger_keywords or [],
        invocation_mode=body.invocation_mode,
        priority=body.priority,
        requires_approval=body.requires_approval,
        is_active=True,
    )
    db.add(row)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "Capability already exists for this (primary, specialist) pair")
    await db.refresh(row)
    capability_resolver.invalidate()
    p_slug, s_slug = await _resolve_slugs(db, row)
    return CapabilityResponse.model_validate(row).model_copy(
        update={"primary_slug": p_slug, "specialist_slug": s_slug, "trigger_keywords": list(row.trigger_keywords or [])}
    )


@router.patch("/{capability_id}", response_model=CapabilityResponse)
async def update_capability(
    capability_id: uuid.UUID,
    body: CapabilityUpdate,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    row = (await db.execute(select(AgentCapability).where(AgentCapability.id == capability_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Capability not found")
    if body.delegation_context is not None:
        row.delegation_context = body.delegation_context
    if body.trigger_keywords is not None:
        row.trigger_keywords = body.trigger_keywords
    if body.invocation_mode is not None:
        row.invocation_mode = body.invocation_mode
    if body.priority is not None:
        row.priority = body.priority
    if body.requires_approval is not None:
        row.requires_approval = body.requires_approval
    if body.is_active is not None:
        row.is_active = body.is_active
    await db.commit()
    await db.refresh(row)
    capability_resolver.invalidate()
    p_slug, s_slug = await _resolve_slugs(db, row)
    return CapabilityResponse.model_validate(row).model_copy(
        update={"primary_slug": p_slug, "specialist_slug": s_slug, "trigger_keywords": list(row.trigger_keywords or [])}
    )


@router.delete("/{capability_id}", status_code=204)
async def delete_capability(
    capability_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    row = (await db.execute(select(AgentCapability).where(AgentCapability.id == capability_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Capability not found")
    await db.delete(row)
    await db.commit()
    capability_resolver.invalidate()
    return None
