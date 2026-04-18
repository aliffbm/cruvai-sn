import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_org_id, get_current_user, get_db
from app.models.instance import InstanceCredential, ServiceNowInstance
from app.utils.encryption import encrypt_value

router = APIRouter()


class InstanceCreate(BaseModel):
    name: str
    instance_url: str
    instance_type: str = "dev"
    auth_method: str = "basic"
    username: str | None = None
    password: str | None = None
    client_id: str | None = None
    client_secret: str | None = None


class InstanceResponse(BaseModel):
    id: uuid.UUID
    name: str
    instance_url: str
    instance_type: str
    auth_method: str
    is_active: bool
    health_status: str
    sn_version: str | None
    organization_id: uuid.UUID

    model_config = {"from_attributes": True}


class TestConnectionResponse(BaseModel):
    success: bool
    sn_version: str | None = None
    message: str = ""


@router.get("", response_model=list[InstanceResponse])
async def list_instances(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(ServiceNowInstance).where(
            ServiceNowInstance.organization_id == org_id,
            ServiceNowInstance.deleted_at.is_(None),
        )
    )
    return result.scalars().all()


@router.post("", response_model=InstanceResponse, status_code=201)
async def create_instance(
    req: InstanceCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    url = req.instance_url.rstrip("/")
    instance = ServiceNowInstance(
        organization_id=current_user.organization_id,
        name=req.name,
        instance_url=url,
        instance_type=req.instance_type,
        auth_method=req.auth_method,
    )
    db.add(instance)
    await db.flush()

    cred = InstanceCredential(
        instance_id=instance.id,
        credential_type=req.auth_method,
        username_encrypted=encrypt_value(req.username) if req.username else None,
        password_encrypted=encrypt_value(req.password) if req.password else None,
        client_id_encrypted=encrypt_value(req.client_id) if req.client_id else None,
        client_secret_encrypted=encrypt_value(req.client_secret) if req.client_secret else None,
    )
    db.add(cred)
    await db.commit()
    await db.refresh(instance)
    return instance


@router.get("/{instance_id}", response_model=InstanceResponse)
async def get_instance(
    instance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(ServiceNowInstance).where(
            ServiceNowInstance.id == instance_id,
            ServiceNowInstance.organization_id == org_id,
        )
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")
    return instance


@router.post("/{instance_id}/test", response_model=TestConnectionResponse)
async def test_connection(
    instance_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(ServiceNowInstance).where(
            ServiceNowInstance.id == instance_id,
            ServiceNowInstance.organization_id == org_id,
        )
    )
    instance = result.scalar_one_or_none()
    if not instance:
        raise HTTPException(status_code=404, detail="Instance not found")

    from app.connectors.base import BaseServiceNowConnector

    try:
        connector = await BaseServiceNowConnector.from_instance(instance, db)
        info = await connector.test_connection()
        instance.health_status = "healthy"
        instance.sn_version = info.get("build_name", info.get("build_tag"))
        instance.last_health_check = datetime.now(timezone.utc)
        await db.commit()
        return TestConnectionResponse(success=True, sn_version=instance.sn_version, message="Connected")
    except Exception as e:
        instance.health_status = "unreachable"
        instance.last_health_check = datetime.now(timezone.utc)
        await db.commit()
        return TestConnectionResponse(success=False, message=str(e))
