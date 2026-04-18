"""Connector API routes — CRUD, credentials, verification, and action execution."""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.deps import get_current_org_id, get_db
from app.models.connector import Connector, ConnectorAction
from app.services.connector_service import connector_service

router = APIRouter()


# --- Schemas ---

class ConnectorCreate(BaseModel):
    platform: str
    label: str
    description: str | None = None
    icon: str | None = None
    instance_label: str | None = None
    connector_type: str = "api_key"
    base_url: str | None = None
    config: dict | None = None


class ConnectorUpdate(BaseModel):
    label: str | None = None
    description: str | None = None
    icon: str | None = None
    instance_label: str | None = None
    base_url: str | None = None
    config: dict | None = None
    is_active: bool | None = None


class CredentialsPayload(BaseModel):
    credentials: dict


class ActionCreate(BaseModel):
    slug: str
    label: str
    description: str | None = None
    category: str | None = None
    method: str = "GET"
    endpoint_path: str
    base_url: str | None = None
    headers_template: dict | None = None
    parameters_schema: dict | None = None
    response_schema: dict | None = None
    request_body_template: dict | None = None
    requires_confirmation: bool = False
    timeout_seconds: int = 30


class ActionExecutePayload(BaseModel):
    params: dict = {}


# --- Connector CRUD ---

@router.get("")
async def list_connectors(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Connector)
        .where(
            Connector.organization_id == org_id,
            Connector.deleted_at.is_(None),
        )
        .order_by(Connector.platform)
    )
    connectors = result.scalars().all()
    return [_connector_response(c) for c in connectors]


@router.post("", status_code=201)
async def create_connector(
    body: ConnectorCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    connector = Connector(
        organization_id=org_id,
        platform=body.platform,
        label=body.label,
        description=body.description,
        icon=body.icon,
        connector_type=body.connector_type,
        base_url=body.base_url,
        config=body.config or {},
    )
    db.add(connector)
    await db.commit()
    await db.refresh(connector)
    return _connector_response(connector)


@router.get("/{connector_id}")
async def get_connector(
    connector_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    connector = await _get_connector(db, connector_id, org_id)
    return _connector_response(connector)


@router.put("/{connector_id}")
async def update_connector(
    connector_id: uuid.UUID,
    body: ConnectorUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    connector = await _get_connector(db, connector_id, org_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(connector, field, value)
    await db.commit()
    await db.refresh(connector)
    return _connector_response(connector)


@router.delete("/{connector_id}", status_code=204)
async def delete_connector(
    connector_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    connector = await _get_connector(db, connector_id, org_id)
    from datetime import datetime, timezone
    connector.deleted_at = datetime.now(timezone.utc)
    await db.commit()


# --- Credentials ---

@router.post("/{connector_id}/credentials")
async def save_credentials(
    connector_id: uuid.UUID,
    body: CredentialsPayload,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    await _get_connector(db, connector_id, org_id)  # Auth check
    connector = await connector_service.save_credentials(db, connector_id, body.credentials)
    await db.commit()
    return {"status": connector.status, "message": "Credentials saved"}


@router.get("/{connector_id}/credentials")
async def get_credentials(
    connector_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    await _get_connector(db, connector_id, org_id)
    return await connector_service.get_credentials(db, connector_id, masked=True)


@router.post("/{connector_id}/credentials/clear")
async def clear_credentials(
    connector_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    await _get_connector(db, connector_id, org_id)
    await connector_service.clear_credentials(db, connector_id)
    await db.commit()
    return {"status": "disconnected", "message": "Credentials cleared"}


# --- Verification ---

@router.post("/{connector_id}/verify")
async def verify_connector(
    connector_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    await _get_connector(db, connector_id, org_id)
    result = await connector_service.verify_connector(db, connector_id)
    await db.commit()
    return result


# --- Actions ---

@router.get("/{connector_id}/actions")
async def list_actions(
    connector_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    await _get_connector(db, connector_id, org_id)
    result = await db.execute(
        select(ConnectorAction)
        .where(
            ConnectorAction.connector_id == connector_id,
            ConnectorAction.is_active.is_(True),
        )
        .order_by(ConnectorAction.category, ConnectorAction.slug)
    )
    actions = result.scalars().all()
    return [_action_response(a) for a in actions]


@router.post("/{connector_id}/actions", status_code=201)
async def create_action(
    connector_id: uuid.UUID,
    body: ActionCreate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    await _get_connector(db, connector_id, org_id)
    action = ConnectorAction(
        connector_id=connector_id,
        **body.model_dump(),
    )
    db.add(action)
    await db.commit()
    await db.refresh(action)
    return _action_response(action)


@router.post("/{connector_id}/actions/{action_id}/execute")
async def execute_action(
    connector_id: uuid.UUID,
    action_id: uuid.UUID,
    body: ActionExecutePayload,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    await _get_connector(db, connector_id, org_id)
    result = await connector_service.execute_action(db, action_id, body.params)
    return result


@router.delete("/{connector_id}/actions/{action_id}", status_code=204)
async def delete_action(
    connector_id: uuid.UUID,
    action_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    await _get_connector(db, connector_id, org_id)
    result = await db.execute(
        select(ConnectorAction).where(
            ConnectorAction.id == action_id,
            ConnectorAction.connector_id == connector_id,
        )
    )
    action = result.scalar_one_or_none()
    if not action:
        raise HTTPException(404, "Action not found")
    await db.delete(action)
    await db.commit()


# --- Helpers ---

async def _get_connector(
    db: AsyncSession, connector_id: uuid.UUID, org_id: uuid.UUID
) -> Connector:
    result = await db.execute(
        select(Connector).where(
            Connector.id == connector_id,
            Connector.organization_id == org_id,
            Connector.deleted_at.is_(None),
        )
    )
    connector = result.scalar_one_or_none()
    if not connector:
        raise HTTPException(404, "Connector not found")
    return connector


def _connector_response(c: Connector) -> dict:
    return {
        "id": str(c.id),
        "platform": c.platform,
        "label": c.label,
        "description": c.description,
        "icon": c.icon,
        "instance_label": c.instance_label,
        "connector_type": c.connector_type,
        "base_url": c.base_url,
        "config": c.config,
        "status": c.status,
        "status_message": c.status_message,
        "last_verified_at": c.last_verified_at.isoformat() if c.last_verified_at else None,
        "has_credentials": c.credentials_encrypted is not None,
        "is_active": c.is_active,
        "created_at": c.created_at.isoformat(),
        "updated_at": c.updated_at.isoformat(),
    }


def _action_response(a: ConnectorAction) -> dict:
    return {
        "id": str(a.id),
        "slug": a.slug,
        "label": a.label,
        "description": a.description,
        "category": a.category,
        "method": a.method,
        "endpoint_path": a.endpoint_path,
        "base_url": a.base_url,
        "requires_confirmation": a.requires_confirmation,
        "is_active": a.is_active,
    }
