"""Playbooks API — list playbooks, manage routes, and simulate matches."""

from __future__ import annotations

import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_org_id, get_current_user, get_db
from app.models.control_plane import (
    AgentPlaybook, AgentPlaybookRoute, AgentPlaybookVersion,
)
from app.services.playbook_service import playbook_service

router = APIRouter()


class PlaybookResponse(BaseModel):
    id: uuid.UUID
    slug: str
    name: str
    description: str | None
    source_origin: str
    is_system: bool
    is_active: bool
    is_orphaned: bool

    model_config = {"from_attributes": True}


class RouteResponse(BaseModel):
    id: uuid.UUID
    playbook_id: uuid.UUID
    task_pattern: str
    match_type: str
    primary_agent_id: uuid.UUID | None
    supporting_agent_ids: list[str]
    required_guidance_ids: list[str]
    priority: int
    is_active: bool

    model_config = {"from_attributes": True}


class RouteUpsert(BaseModel):
    task_pattern: str
    match_type: str = "keywords"
    primary_agent_id: uuid.UUID | None = None
    supporting_agent_ids: list[uuid.UUID] = []
    required_guidance_ids: list[uuid.UUID] = []
    priority: int = 100
    is_active: bool = True


class SimulateRequest(BaseModel):
    playbook_slug: str
    story_title: str
    story_description: str | None = None


@router.get("", response_model=list[PlaybookResponse])
async def list_playbooks(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    rows = (
        await db.execute(
            select(AgentPlaybook).where(
                AgentPlaybook.is_active.is_(True),
                (
                    (AgentPlaybook.organization_id == org_id)
                    | AgentPlaybook.organization_id.is_(None)
                ),
            ).order_by(AgentPlaybook.slug)
        )
    ).scalars().all()
    return [PlaybookResponse.model_validate(p) for p in rows]


@router.get("/{playbook_id}/routes", response_model=list[RouteResponse])
async def list_routes(
    playbook_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    rows = (
        await db.execute(
            select(AgentPlaybookRoute)
            .where(AgentPlaybookRoute.playbook_id == playbook_id)
            .order_by(AgentPlaybookRoute.priority.asc())
        )
    ).scalars().all()
    return [
        RouteResponse.model_validate(r).model_copy(
            update={
                "supporting_agent_ids": [str(s) for s in (r.supporting_agent_ids or [])],
                "required_guidance_ids": [str(g) for g in (r.required_guidance_ids or [])],
            }
        )
        for r in rows
    ]


@router.post("/{playbook_id}/routes", response_model=RouteResponse, status_code=201)
async def create_route(
    playbook_id: uuid.UUID,
    body: RouteUpsert,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    pb = (await db.execute(select(AgentPlaybook).where(AgentPlaybook.id == playbook_id))).scalar_one_or_none()
    if pb is None:
        raise HTTPException(404, "Playbook not found")
    row = AgentPlaybookRoute(
        playbook_id=playbook_id,
        task_pattern=body.task_pattern,
        match_type=body.match_type,
        primary_agent_id=body.primary_agent_id,
        supporting_agent_ids=[str(x) for x in body.supporting_agent_ids],
        required_guidance_ids=[str(x) for x in body.required_guidance_ids],
        priority=body.priority,
        is_active=body.is_active,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return RouteResponse.model_validate(row).model_copy(
        update={
            "supporting_agent_ids": [str(s) for s in (row.supporting_agent_ids or [])],
            "required_guidance_ids": [str(g) for g in (row.required_guidance_ids or [])],
        }
    )


@router.patch("/routes/{route_id}", response_model=RouteResponse)
async def update_route(
    route_id: uuid.UUID,
    body: RouteUpsert,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    row = (await db.execute(select(AgentPlaybookRoute).where(AgentPlaybookRoute.id == route_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Route not found")
    row.task_pattern = body.task_pattern
    row.match_type = body.match_type
    row.primary_agent_id = body.primary_agent_id
    row.supporting_agent_ids = [str(x) for x in body.supporting_agent_ids]
    row.required_guidance_ids = [str(x) for x in body.required_guidance_ids]
    row.priority = body.priority
    row.is_active = body.is_active
    await db.commit()
    await db.refresh(row)
    return RouteResponse.model_validate(row).model_copy(
        update={
            "supporting_agent_ids": [str(s) for s in (row.supporting_agent_ids or [])],
            "required_guidance_ids": [str(g) for g in (row.required_guidance_ids or [])],
        }
    )


@router.delete("/routes/{route_id}", status_code=204)
async def delete_route(
    route_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user = Depends(get_current_user),
):
    row = (await db.execute(select(AgentPlaybookRoute).where(AgentPlaybookRoute.id == route_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Route not found")
    await db.delete(row)
    await db.commit()
    return None


@router.post("/simulate")
async def simulate(
    body: SimulateRequest,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Dry-run a story against a playbook — shows which route fires."""

    # Use sync session from the same engine for the sync service
    from app.deps import sync_session_factory

    with sync_session_factory() as sync_db:
        match = playbook_service.resolve_for_story_sync(
            sync_db,
            playbook_slug=body.playbook_slug,
            story_title=body.story_title,
            story_description=body.story_description,
            org_id=org_id,
        )
    if match is None:
        return {"matched": False}
    return {
        "matched": True,
        "playbook_slug": match.playbook_slug,
        "playbook_name": match.playbook_name,
        "matched_pattern": match.matched_pattern,
        "match_type": match.match_type,
        "primary_agent_id": str(match.primary_agent_id) if match.primary_agent_id else None,
        "supporting_agent_ids": [str(x) for x in match.supporting_agent_ids],
        "required_guidance_ids": [str(x) for x in match.required_guidance_ids],
    }
