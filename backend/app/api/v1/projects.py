import uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_org_id, get_current_user, get_db
from app.models.project import Project

router = APIRouter()


def _project_to_response(project: Project) -> "ProjectResponse":
    settings = project.settings_json or {}
    return ProjectResponse.model_validate(project).model_copy(
        update={"playbook_slug": settings.get("playbook_slug")}
    )


class ProjectCreate(BaseModel):
    name: str
    description: str | None = None
    instance_id: uuid.UUID | None = None
    figma_connector_id: uuid.UUID | None = None
    playbook_slug: str | None = None


class ProjectUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    status: str | None = None
    instance_id: uuid.UUID | None = None
    figma_connector_id: uuid.UUID | None = None
    playbook_slug: str | None = None


class ProjectResponse(BaseModel):
    id: uuid.UUID
    name: str
    slug: str
    description: str | None
    status: str
    instance_id: uuid.UUID | None
    figma_connector_id: uuid.UUID | None = None
    organization_id: uuid.UUID
    playbook_slug: str | None = None

    model_config = {"from_attributes": True}


@router.get("", response_model=list[ProjectResponse])
async def list_projects(
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Project).where(Project.organization_id == org_id, Project.deleted_at.is_(None))
    )
    return [_project_to_response(p) for p in result.scalars().all()]


@router.post("", response_model=ProjectResponse, status_code=201)
async def create_project(
    req: ProjectCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    slug = req.name.lower().replace(" ", "-")[:100]
    project = Project(
        organization_id=current_user.organization_id,
        name=req.name,
        slug=slug,
        description=req.description,
        instance_id=req.instance_id,
        figma_connector_id=req.figma_connector_id,
    )
    if req.playbook_slug:
        project.settings_json = {**(project.settings_json or {}), "playbook_slug": req.playbook_slug}
    db.add(project)
    await db.commit()
    await db.refresh(project)
    return _project_to_response(project)


@router.get("/{project_id}", response_model=ProjectResponse)
async def get_project(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return _project_to_response(project)


@router.patch("/{project_id}", response_model=ProjectResponse)
async def update_project(
    project_id: uuid.UUID,
    req: ProjectUpdate,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.organization_id == org_id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    payload = req.model_dump(exclude_unset=True)
    if "playbook_slug" in payload:
        project.settings_json = {
            **(project.settings_json or {}),
            "playbook_slug": payload.pop("playbook_slug"),
        }
    for field, value in payload.items():
        setattr(project, field, value)
    await db.commit()
    await db.refresh(project)
    return _project_to_response(project)
