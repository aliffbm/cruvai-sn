import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_org_id, get_current_user, get_db
from app.models.org_settings import OrgApiKey
from app.utils.encryption import encrypt_value

router = APIRouter()


def _mask_key(key: str) -> str:
    """Show first 7 and last 4 chars: sk-ant-...xQ2m"""
    if len(key) <= 12:
        return "***"
    return f"{key[:7]}...{key[-4:]}"


class ApiKeyCreate(BaseModel):
    provider: str  # anthropic, openai
    label: str = "Default"
    api_key: str  # the raw key — only sent on create, never returned
    notes: str | None = None


class ApiKeyResponse(BaseModel):
    id: uuid.UUID
    provider: str
    label: str
    key_preview: str
    is_active: bool
    notes: str | None

    model_config = {"from_attributes": True}


class ApiKeyUpdate(BaseModel):
    label: str | None = None
    api_key: str | None = None  # if provided, re-encrypts
    is_active: bool | None = None
    notes: str | None = None


@router.get("/api-keys", response_model=list[ApiKeyResponse])
async def list_api_keys(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(OrgApiKey).where(
            OrgApiKey.organization_id == org_id,
            OrgApiKey.deleted_at.is_(None),
        )
    )
    return result.scalars().all()


@router.post("/api-keys", response_model=ApiKeyResponse, status_code=201)
async def create_api_key(
    req: ApiKeyCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    if req.provider not in ("anthropic", "openai"):
        raise HTTPException(status_code=400, detail="Provider must be 'anthropic' or 'openai'")

    key = OrgApiKey(
        organization_id=current_user.organization_id,
        provider=req.provider,
        label=req.label,
        key_encrypted=encrypt_value(req.api_key),
        key_preview=_mask_key(req.api_key),
        notes=req.notes,
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    return key


@router.patch("/api-keys/{key_id}", response_model=ApiKeyResponse)
async def update_api_key(
    key_id: uuid.UUID,
    req: ApiKeyUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(OrgApiKey).where(OrgApiKey.id == key_id, OrgApiKey.organization_id == org_id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")

    if req.label is not None:
        key.label = req.label
    if req.is_active is not None:
        key.is_active = req.is_active
    if req.notes is not None:
        key.notes = req.notes
    if req.api_key is not None:
        key.key_encrypted = encrypt_value(req.api_key)
        key.key_preview = _mask_key(req.api_key)

    await db.commit()
    await db.refresh(key)
    return key


@router.delete("/api-keys/{key_id}")
async def delete_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(OrgApiKey).where(OrgApiKey.id == key_id, OrgApiKey.organization_id == org_id)
    )
    key = result.scalar_one_or_none()
    if not key:
        raise HTTPException(status_code=404, detail="API key not found")
    from datetime import datetime, timezone
    key.deleted_at = datetime.now(timezone.utc)
    await db.commit()
    return {"detail": "Deleted"}
