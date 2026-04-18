import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_org_id, get_db
from app.models.artifact import Artifact, ArtifactVersion

router = APIRouter()


class ArtifactResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    job_id: uuid.UUID
    story_id: uuid.UUID | None
    sn_table: str
    sn_sys_id: str
    sn_scope: str
    name: str
    artifact_type: str
    script_content: str | None
    status: str

    model_config = {"from_attributes": True}


class ArtifactVersionResponse(BaseModel):
    id: uuid.UUID
    artifact_id: uuid.UUID
    version_number: int
    change_description: str | None
    script_content: str | None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ArtifactResponse])
async def list_artifacts(
    project_id: uuid.UUID,
    artifact_type: str | None = None,
    job_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    query = select(Artifact).where(
        Artifact.project_id == project_id,
        Artifact.organization_id == org_id,
    )
    if artifact_type:
        query = query.where(Artifact.artifact_type == artifact_type)
    if job_id:
        query = query.where(Artifact.job_id == job_id)
    result = await db.execute(query.order_by(Artifact.created_at.desc()))
    return result.scalars().all()


@router.get("/{artifact_id}", response_model=ArtifactResponse)
async def get_artifact(
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Artifact).where(
            Artifact.id == artifact_id,
            Artifact.project_id == project_id,
            Artifact.organization_id == org_id,
        )
    )
    artifact = result.scalar_one_or_none()
    if not artifact:
        raise HTTPException(status_code=404, detail="Artifact not found")
    return artifact


@router.get("/{artifact_id}/versions", response_model=list[ArtifactVersionResponse])
async def list_artifact_versions(
    project_id: uuid.UUID,
    artifact_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(ArtifactVersion)
        .where(ArtifactVersion.artifact_id == artifact_id)
        .order_by(ArtifactVersion.version_number.desc())
    )
    return result.scalars().all()
