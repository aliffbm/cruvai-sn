import os
import uuid
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_org_id, get_current_user, get_db
from app.models.story import UserStory
from app.models.story_attachment import StoryAttachment

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "uploads")

router = APIRouter()


class StoryCreate(BaseModel):
    title: str
    description: str | None = None
    acceptance_criteria: str | None = None
    priority: int = 3
    story_points: int | None = None
    tags: list[str] | None = None
    parent_story_id: uuid.UUID | None = None
    story_type: str = "story"
    figma_node_id: str | None = None
    figma_file_url: str | None = None


class StoryUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    acceptance_criteria: str | None = None
    priority: int | None = None
    status: str | None = None
    story_points: int | None = None
    tags: list[str] | None = None
    board_position: int | None = None
    figma_file_url: str | None = None
    figma_node_id: str | None = None


class StoryResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    title: str
    description: str | None
    acceptance_criteria: str | None
    priority: int
    status: str
    story_points: int | None
    tags: dict | None
    board_position: int
    external_id: str | None
    story_type: str = "story"
    parent_story_id: uuid.UUID | None = None
    figma_node_id: str | None = None
    figma_file_url: str | None = None

    model_config = {"from_attributes": True}


class FigmaImportRequest(BaseModel):
    figma_url: str
    connector_id: str
    portal_type: str | None = None


@router.get("", response_model=list[StoryResponse])
async def list_stories(
    project_id: uuid.UUID,
    status: str | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    query = select(UserStory).where(
        UserStory.project_id == project_id,
        UserStory.organization_id == org_id,
        UserStory.deleted_at.is_(None),
    )
    if status:
        query = query.where(UserStory.status == status)
    query = query.order_by(UserStory.board_position)
    result = await db.execute(query)
    return result.scalars().all()


@router.post("", response_model=StoryResponse, status_code=201)
async def create_story(
    project_id: uuid.UUID,
    req: StoryCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    story = UserStory(
        organization_id=current_user.organization_id,
        project_id=project_id,
        title=req.title,
        description=req.description,
        acceptance_criteria=req.acceptance_criteria,
        priority=req.priority,
        story_points=req.story_points,
        tags=req.tags,
        parent_story_id=req.parent_story_id,
        story_type=req.story_type,
        figma_node_id=req.figma_node_id,
        figma_file_url=req.figma_file_url,
    )
    db.add(story)
    await db.commit()
    await db.refresh(story)
    return story


@router.get("/{story_id}", response_model=StoryResponse)
async def get_story(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(UserStory).where(
            UserStory.id == story_id,
            UserStory.project_id == project_id,
            UserStory.organization_id == org_id,
        )
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    return story


@router.patch("/{story_id}", response_model=StoryResponse)
async def update_story(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    req: StoryUpdate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    org_id = current_user.organization_id
    result = await db.execute(
        select(UserStory).where(
            UserStory.id == story_id,
            UserStory.project_id == project_id,
            UserStory.organization_id == org_id,
        )
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")

    # Snapshot tracked fields BEFORE mutation for audit diff
    from app.services.note_service import (
        TRACKED_STORY_FIELDS, note_service, summarize_diff,
    )
    snapshot_before = {f: getattr(story, f, None) for f in TRACKED_STORY_FIELDS}

    for field, value in req.model_dump(exclude_unset=True).items():
        setattr(story, field, value)
    await db.flush()

    # Build the diff over the tracked field set
    diff: dict[str, dict[str, Any]] = {}
    for f in TRACKED_STORY_FIELDS:
        new_val = getattr(story, f, None)
        if snapshot_before[f] != new_val:
            diff[f] = {"before": snapshot_before[f], "after": new_val}

    if diff:
        await note_service.write(
            db,
            story_id=story.id,
            organization_id=org_id,
            note_type="requirement_change",
            content=summarize_diff(diff),
            diff=diff,
            author_user_id=current_user.id,
        )

        # If acceptance criteria or description changed, any approved analysis
        # becomes potentially stale — demote to "outdated" so users see they
        # need to re-analyze before launching agents.
        if any(f in diff for f in ("description", "acceptance_criteria", "figma_file_url")):
            from app.models.story_analysis import StoryAnalysis

            await db.execute(
                StoryAnalysis.__table__.update()
                .where(
                    StoryAnalysis.story_id == story.id,
                    StoryAnalysis.status == "approved",
                )
                .values(status="outdated")
            )
            await note_service.write(
                db,
                story_id=story.id,
                organization_id=org_id,
                note_type="analysis_update",
                content=(
                    "Previously-approved analysis marked outdated because "
                    f"{', '.join(sorted(set(diff) & {'description','acceptance_criteria','figma_file_url'}))} "
                    "changed. Re-run the AI Agent Analyzer before building."
                ),
                author_user_id=current_user.id,
            )

    await db.commit()
    await db.refresh(story)
    return story


@router.get("/{story_id}/figma-preview")
async def figma_preview(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Fetch a lightweight preview of the Figma design linked to this story.

    Uses the project's configured Figma connector. Returns top-level frames +
    thumbnails so the UI can render a sanity-check before dispatching a Portal
    job.
    """

    from app.models.project import Project
    from app.services.figma_service import figma_service

    # Load story
    result = await db.execute(
        select(UserStory).where(
            UserStory.id == story_id,
            UserStory.project_id == project_id,
            UserStory.organization_id == org_id,
        )
    )
    story = result.scalar_one_or_none()
    if not story:
        raise HTTPException(status_code=404, detail="Story not found")
    if not story.figma_file_url:
        raise HTTPException(status_code=400, detail="Story has no figma_file_url")

    # Load project → connector reference
    project = (
        await db.execute(select(Project).where(Project.id == project_id))
    ).scalar_one_or_none()
    if project is None or project.figma_connector_id is None:
        raise HTTPException(
            status_code=400,
            detail="Project has no figma_connector_id. Set one in project settings.",
        )

    try:
        design = await figma_service.extract_design(
            connector_id=project.figma_connector_id,
            figma_url=story.figma_file_url,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:  # noqa: BLE001 - surface upstream error
        raise HTTPException(status_code=502, detail=f"Figma fetch failed: {exc}")

    return {
        "file_key": design.file_key,
        "file_name": design.file_name,
        "pages": [
            {
                "name": page.name,
                "node_id": page.node_id,
                "frames": [
                    {
                        "name": f.name,
                        "node_id": f.node_id,
                        "children_count": f.children_count,
                        "component_names": f.component_names[:10],
                    }
                    for f in page.frames[:10]
                ],
            }
            for page in design.pages[:5]
        ],
        "colors": design.colors[:20],
        "fonts": design.fonts[:10],
    }


# === Execution Ordering ===

# Priority order for ServiceNow portal builds.
# Stories are sorted by matching their title against these patterns.
EXECUTION_ORDER_PATTERNS = [
    "foundation",       # Portal record, theme, CSS variables
    "navigation",       # Header/nav widget (shared across pages)
    "homepage",         # Main landing page
    "request",          # Service catalog / request management
    "approval",         # Approval workflows
    "accounting",       # Finance / accounting sections
    "favorite",         # Personalization features
    "survey",           # Feedback / surveys
    "campaign",         # Promotional content
    "content",          # Documentation / knowledge
    "footer",           # Footer and auxiliary
]


def _execution_order_key(story: dict) -> int:
    """Return a sort key based on the story title matching known patterns."""
    title_lower = (story.get("title") or "").lower()
    for i, pattern in enumerate(EXECUTION_ORDER_PATTERNS):
        if pattern in title_lower:
            return i
    return len(EXECUTION_ORDER_PATTERNS)  # Unknown stories go last


@router.get("/epic/{story_id}/execution-plan")
async def get_epic_execution_plan(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Get child stories of an epic in recommended execution order."""
    # Verify the epic exists
    result = await db.execute(
        select(UserStory).where(
            UserStory.id == story_id,
            UserStory.project_id == project_id,
            UserStory.organization_id == org_id,
        )
    )
    epic = result.scalar_one_or_none()
    if not epic:
        raise HTTPException(status_code=404, detail="Epic not found")

    # Get child stories
    children_result = await db.execute(
        select(UserStory).where(
            UserStory.parent_story_id == story_id,
            UserStory.deleted_at.is_(None),
        )
    )
    children = children_result.scalars().all()

    # Sort by execution order
    children_dicts = [
        {
            "id": str(c.id),
            "title": c.title,
            "description": c.description,
            "acceptance_criteria": c.acceptance_criteria,
            "priority": c.priority,
            "status": c.status,
            "story_type": c.story_type,
            "figma_node_id": c.figma_node_id,
        }
        for c in children
    ]
    children_dicts.sort(key=_execution_order_key)

    # Add execution step numbers
    for i, child in enumerate(children_dicts):
        child["execution_step"] = i + 1
        child["can_execute"] = (
            i == 0
            or children_dicts[i - 1]["status"] in ("done", "review", "testing")
        )

    return {
        "epic": {
            "id": str(epic.id),
            "title": epic.title,
            "description": epic.description,
            "status": epic.status,
        },
        "stories": children_dicts,
        "total": len(children_dicts),
        "completed": sum(1 for c in children_dicts if c["status"] == "done"),
    }


# === Attachment Endpoints ===

@router.post("/{story_id}/attachments", status_code=201)
async def upload_attachment(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    file: UploadFile = File(...),
    caption: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Upload an image or file to a story."""
    # Validate file type
    allowed_types = {"image/png", "image/jpeg", "image/gif", "image/webp", "image/svg+xml", "application/pdf"}
    if file.content_type not in allowed_types:
        raise HTTPException(400, f"File type {file.content_type} not allowed. Use: {', '.join(allowed_types)}")

    # Read file
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(400, "File too large. Max 10MB.")

    # Save to disk
    file_id = str(uuid.uuid4())
    ext = os.path.splitext(file.filename or "file")[1] or ".bin"
    save_filename = f"{file_id}{ext}"
    save_path = os.path.join(UPLOAD_DIR, save_filename)
    os.makedirs(UPLOAD_DIR, exist_ok=True)

    with open(save_path, "wb") as f:
        f.write(content)

    # Create DB record
    attachment = StoryAttachment(
        story_id=story_id,
        organization_id=current_user.organization_id,
        filename=file.filename or "unnamed",
        file_path=save_filename,
        mime_type=file.content_type or "application/octet-stream",
        file_size=len(content),
        caption=caption,
    )
    db.add(attachment)
    await db.commit()
    await db.refresh(attachment)

    return {
        "id": str(attachment.id),
        "filename": attachment.filename,
        "mime_type": attachment.mime_type,
        "file_size": attachment.file_size,
        "caption": attachment.caption,
        "url": f"/api/v1/projects/{project_id}/stories/{story_id}/attachments/{attachment.id}/file",
        "created_at": attachment.created_at.isoformat(),
    }


@router.get("/{story_id}/attachments")
async def list_attachments(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """List all attachments for a story."""
    result = await db.execute(
        select(StoryAttachment).where(
            StoryAttachment.story_id == story_id,
            StoryAttachment.organization_id == org_id,
        ).order_by(StoryAttachment.created_at)
    )
    attachments = result.scalars().all()
    return [
        {
            "id": str(a.id),
            "filename": a.filename,
            "mime_type": a.mime_type,
            "file_size": a.file_size,
            "caption": a.caption,
            "url": f"/api/v1/projects/{project_id}/stories/{story_id}/attachments/{a.id}/file",
            "created_at": a.created_at.isoformat(),
        }
        for a in attachments
    ]


@router.get("/{story_id}/attachments/{attachment_id}/file")
async def get_attachment_file(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Serve an attachment file."""
    result = await db.execute(
        select(StoryAttachment).where(
            StoryAttachment.id == attachment_id,
            StoryAttachment.story_id == story_id,
            StoryAttachment.organization_id == org_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(404, "Attachment not found")

    file_path = os.path.join(UPLOAD_DIR, attachment.file_path)
    if not os.path.exists(file_path):
        raise HTTPException(404, "File not found on disk")

    return FileResponse(file_path, media_type=attachment.mime_type, filename=attachment.filename)


@router.delete("/{story_id}/attachments/{attachment_id}", status_code=204)
async def delete_attachment(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    attachment_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Delete an attachment."""
    result = await db.execute(
        select(StoryAttachment).where(
            StoryAttachment.id == attachment_id,
            StoryAttachment.story_id == story_id,
            StoryAttachment.organization_id == org_id,
        )
    )
    attachment = result.scalar_one_or_none()
    if not attachment:
        raise HTTPException(404, "Attachment not found")

    # Delete file from disk
    file_path = os.path.join(UPLOAD_DIR, attachment.file_path)
    if os.path.exists(file_path):
        os.remove(file_path)

    await db.delete(attachment)
    await db.commit()


@router.post("/import-figma")
async def import_figma_stories(
    project_id: uuid.UUID,
    req: FigmaImportRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Import a Figma design as an epic with child stories.

    1. Extracts design structure from Figma API
    2. Uses LLM to generate epic + stories from the design
    3. Creates all stories in the project
    """
    from app.services.figma_service import figma_service

    # Step 1: Extract design from Figma
    design = await figma_service.extract_design(
        uuid.UUID(req.connector_id), req.figma_url, db
    )

    # Step 2: Generate stories via LLM
    prompt_text = figma_service.generate_story_prompt(design, req.portal_type)

    # Try LLM Gateway first, fall back to direct Anthropic call
    import json as json_module
    stories_data = None
    try:
        from app.services.llm_gateway import llm_gateway
        from sqlalchemy.orm import Session as SyncSession
        # The gateway uses sync sessions; we need to handle this
        # For now, use direct Anthropic call
        raise ImportError("Use direct call")
    except (ImportError, Exception):
        pass

    if stories_data is None:
        # Direct Anthropic call
        import anthropic
        from app.services.llm_service import get_api_key
        from app.deps import get_sync_db

        # Get API key
        sync_db = get_sync_db()
        try:
            api_key = get_api_key(sync_db, current_user.organization_id, "anthropic")
        finally:
            sync_db.close()

        client = anthropic.Anthropic(api_key=api_key)

        # Load figma import prompt
        import os
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "..", "agents", "prompts", "figma_import.md"
        )
        system_prompt = ""
        if os.path.exists(prompt_path):
            with open(prompt_path) as f:
                system_prompt = f.read()

        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": prompt_text}],
        )

        response_text = response.content[0].text.strip()
        # Parse JSON from response
        if "```json" in response_text:
            response_text = response_text.split("```json")[1].split("```")[0]
        elif "```" in response_text:
            response_text = response_text.split("```")[1].split("```")[0]

        stories_data = json_module.loads(response_text.strip())

    # Step 3: Create epic (retain source Figma URL for downstream agents)
    epic_data = stories_data.get("epic", {})
    epic = UserStory(
        organization_id=current_user.organization_id,
        project_id=project_id,
        title=epic_data.get("title", f"Build {design.file_name} Portal"),
        description=epic_data.get("description", ""),
        story_type="epic",
        priority=1,
        status="backlog",
        figma_file_url=req.figma_url,
    )
    db.add(epic)
    await db.flush()

    # Step 4: Create child stories — every story inherits the source Figma URL
    # so portal_agent can re-fetch the design when each story is launched.
    created_stories = []
    for i, s_data in enumerate(stories_data.get("stories", [])):
        story = UserStory(
            organization_id=current_user.organization_id,
            project_id=project_id,
            parent_story_id=epic.id,
            title=s_data.get("title", f"Story {i+1}"),
            description=s_data.get("description", ""),
            acceptance_criteria=s_data.get("acceptance_criteria", ""),
            priority=s_data.get("priority", 3),
            story_type="story",
            figma_node_id=s_data.get("figma_node_id"),
            figma_file_url=req.figma_url,
            board_position=i,
            status="backlog",
        )
        db.add(story)
        created_stories.append(story)

    await db.commit()
    await db.refresh(epic)
    for s in created_stories:
        await db.refresh(s)

    return {
        "epic": {
            "id": str(epic.id),
            "title": epic.title,
            "description": epic.description,
        },
        "stories": [
            {
                "id": str(s.id),
                "title": s.title,
                "description": s.description,
                "acceptance_criteria": s.acceptance_criteria,
                "priority": s.priority,
                "figma_node_id": s.figma_node_id,
            }
            for s in created_stories
        ],
        "design_summary": figma_service.design_to_summary(design),
    }


# =============================================================================
# Story Analysis — AI Agent Analyzer outputs
# =============================================================================


class AnalysisResponse(BaseModel):
    id: uuid.UUID
    story_id: uuid.UUID
    version_number: int
    status: str
    summary: str | None
    design_rationale: str | None
    oob_reuse: list | None
    design_patterns_applied: list | None
    proposed_artifacts: list | None
    acceptance_criteria_mapping: list | None
    specialist_consults: list | None
    applicable_guidance: list | None
    risks: list | None
    dependencies_on_other_stories: list | None
    estimated_story_points: int | None
    authored_by_agent_slug: str
    authored_by_job_id: uuid.UUID | None
    authored_by_model: str | None
    created_by_id: uuid.UUID | None
    reviewed_by_id: uuid.UUID | None
    approved_at: datetime | None
    rejection_reason: str | None
    content_hash: str
    created_at: datetime

    model_config = {"from_attributes": True}


class AnalyzeRequest(BaseModel):
    instance_id: uuid.UUID | None = None  # SN connector for OOB survey


class RejectRequest(BaseModel):
    reason: str


@router.post("/{story_id}/analyze")
async def trigger_analysis(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    req: AnalyzeRequest | None = None,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Dispatch the AI Agent Analyzer for this story.

    Creates an AgentJob (agent_type=analyzer), enqueues it via Celery, and
    returns the job id so the UI can stream logs like any other agent run.
    """

    story_res = await db.execute(
        select(UserStory).where(
            UserStory.id == story_id,
            UserStory.project_id == project_id,
            UserStory.organization_id == current_user.organization_id,
        )
    )
    story = story_res.scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")

    from app.models.agent import AgentDefinition
    from app.models.job import AgentJob

    analyzer = (
        await db.execute(
            select(AgentDefinition).where(AgentDefinition.slug == "analyzer-agent")
        )
    ).scalar_one_or_none()
    if analyzer is None:
        raise HTTPException(
            500,
            "AI Agent Analyzer is not seeded. Run `python -m app.seed` in the backend.",
        )

    # If no instance_id provided, reuse the project's default instance so OOB
    # survey can run. AgentJob.instance_id is NOT NULL — if neither is set we
    # fail fast with a clear message instead of a DB error.
    instance_id = req.instance_id if req else None
    if instance_id is None:
        from app.models.project import Project

        project = (
            await db.execute(select(Project).where(Project.id == project_id))
        ).scalar_one_or_none()
        if project is not None and project.instance_id:
            instance_id = project.instance_id
    if instance_id is None:
        raise HTTPException(
            400,
            "No ServiceNow instance configured on the project. "
            "Open the project Settings and attach an instance before running the Analyzer.",
        )

    job = AgentJob(
        organization_id=current_user.organization_id,
        project_id=project_id,
        story_id=story_id,
        agent_id=analyzer.id,
        instance_id=instance_id,
        status="queued",
        initiated_by_id=current_user.id,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    from app.workers.agent_tasks import run_agent_job

    task = run_agent_job.delay(str(job.id))
    job.celery_task_id = task.id
    await db.commit()

    return {
        "job_id": str(job.id),
        "status": job.status,
        "agent_slug": analyzer.slug,
        "message": (
            "Analyzer dispatched. Subscribe to the job log to stream progress."
        ),
    }


@router.get("/{story_id}/analyses", response_model=list[AnalysisResponse])
async def list_analyses(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    # Tenancy check
    story = (await db.execute(select(UserStory).where(
        UserStory.id == story_id,
        UserStory.project_id == project_id,
        UserStory.organization_id == org_id,
    ))).scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")
    from app.services.analysis_service import analysis_service

    rows = await analysis_service.list_for_story(db, story_id)
    return [AnalysisResponse.model_validate(r) for r in rows]


@router.get("/{story_id}/analyses/latest")
async def latest_analysis(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    """Returns the latest StoryAnalysis or `{"analysis": null}` if none exist."""
    story = (await db.execute(select(UserStory).where(
        UserStory.id == story_id,
        UserStory.project_id == project_id,
        UserStory.organization_id == org_id,
    ))).scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")
    from app.services.analysis_service import analysis_service

    row = await analysis_service.get_latest_for_story(db, story_id)
    if row is None:
        return {"analysis": None}
    return {"analysis": AnalysisResponse.model_validate(row).model_dump(mode="json")}


@router.post("/{story_id}/analyses/{analysis_id}/approve", response_model=AnalysisResponse)
async def approve_analysis(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    analysis_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.services.analysis_service import analysis_service

    row = await analysis_service.approve(
        db, analysis_id, reviewer_user_id=current_user.id
    )
    if row.story_id != story_id:
        raise HTTPException(400, "Analysis does not belong to this story")
    await db.commit()
    await db.refresh(row)
    return AnalysisResponse.model_validate(row)


@router.post("/{story_id}/analyses/{analysis_id}/reject", response_model=AnalysisResponse)
async def reject_analysis(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    analysis_id: uuid.UUID,
    req: RejectRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    from app.services.analysis_service import analysis_service

    row = await analysis_service.reject(
        db, analysis_id, reviewer_user_id=current_user.id, reason=req.reason
    )
    if row.story_id != story_id:
        raise HTTPException(400, "Analysis does not belong to this story")
    await db.commit()
    await db.refresh(row)
    return AnalysisResponse.model_validate(row)


@router.get("/{story_id}/analyses/{analysis_id}/diff")
async def analysis_diff(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    analysis_id: uuid.UUID,
    against: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    from app.services.analysis_service import analysis_service

    return await analysis_service.diff(db, analysis_id, against)


# =============================================================================
# Story Notes — append-only audit trail
# =============================================================================


class NoteResponse(BaseModel):
    id: uuid.UUID
    note_type: str
    content: str
    diff: dict | None
    related_id: uuid.UUID | None
    author_user_id: uuid.UUID | None
    author_agent_slug: str | None
    author_job_id: uuid.UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class ManualNoteCreate(BaseModel):
    content: str


@router.get("/{story_id}/notes", response_model=list[NoteResponse])
async def list_notes(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    story = (await db.execute(select(UserStory).where(
        UserStory.id == story_id,
        UserStory.project_id == project_id,
        UserStory.organization_id == org_id,
    ))).scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")
    from app.services.note_service import note_service

    rows = await note_service.list_for_story(db, story_id)
    return [NoteResponse.model_validate(r) for r in rows]


@router.post("/{story_id}/notes", response_model=NoteResponse, status_code=201)
async def create_manual_note(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    req: ManualNoteCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    story = (await db.execute(select(UserStory).where(
        UserStory.id == story_id,
        UserStory.project_id == project_id,
        UserStory.organization_id == current_user.organization_id,
    ))).scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")
    from app.services.note_service import note_service

    row = await note_service.write(
        db,
        story_id=story_id,
        organization_id=current_user.organization_id,
        note_type="manual",
        content=req.content,
        author_user_id=current_user.id,
    )
    await db.commit()
    await db.refresh(row)
    return NoteResponse.model_validate(row)


# =============================================================================
# Figma image capture — download frame renders as StoryAttachments
# =============================================================================


@router.post("/{story_id}/capture-figma-images")
async def capture_figma_images(
    project_id: uuid.UUID,
    story_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Fetch PNG renders of this story's Figma frame(s) and attach them.

    If `figma_node_id` is set, captures just that frame. Otherwise, captures
    the first frame from each page in the linked file (lightweight).
    """

    import httpx as _httpx
    from app.models.project import Project
    from app.services.figma_service import figma_service

    story = (await db.execute(select(UserStory).where(
        UserStory.id == story_id,
        UserStory.project_id == project_id,
        UserStory.organization_id == current_user.organization_id,
    ))).scalar_one_or_none()
    if not story:
        raise HTTPException(404, "Story not found")
    if not story.figma_file_url:
        raise HTTPException(400, "Story has no figma_file_url")

    project = (await db.execute(select(Project).where(Project.id == project_id))).scalar_one_or_none()
    if project is None or project.figma_connector_id is None:
        raise HTTPException(400, "Project has no figma_connector_id")

    # Build list of node_ids to capture
    node_ids: list[str] = []
    frame_names: dict[str, str] = {}
    if story.figma_node_id:
        node_ids = [story.figma_node_id]
        frame_names[story.figma_node_id] = story.title
    else:
        # Capture the top frame on each page as a light preview
        try:
            design = await figma_service.extract_design(
                connector_id=project.figma_connector_id,
                figma_url=story.figma_file_url,
                db=db,
            )
            for page in design.pages[:3]:  # cap at 3 pages to stay within rate limits
                if page.frames:
                    first = page.frames[0]
                    node_ids.append(first.node_id)
                    frame_names[first.node_id] = f"{page.name} — {first.name}"
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(502, f"Could not resolve frames: {exc}")

    if not node_ids:
        return {"captured": 0, "message": "No frames to capture"}

    try:
        image_urls = await figma_service.export_node_images(
            connector_id=project.figma_connector_id,
            figma_url=story.figma_file_url,
            node_ids=node_ids,
            db=db,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(502, f"Figma image export failed: {exc}")

    # Download each PNG and persist as a StoryAttachment
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    saved: list[dict[str, str]] = []
    async with _httpx.AsyncClient(timeout=60) as client:
        for node_id, cdn_url in image_urls.items():
            if not cdn_url:
                continue
            # Skip if we already have a Figma capture for this node
            existing = (await db.execute(
                select(StoryAttachment).where(
                    StoryAttachment.story_id == story_id,
                    StoryAttachment.caption == f"figma-capture:{node_id}",
                )
            )).scalar_one_or_none()
            if existing is not None:
                continue
            img_resp = await client.get(cdn_url)
            if img_resp.status_code != 200:
                continue
            data = img_resp.content
            safe_node = node_id.replace(":", "_").replace("/", "_")
            save_filename = f"figma_{story_id}_{safe_node}.png"
            save_path = os.path.join(UPLOAD_DIR, save_filename)
            with open(save_path, "wb") as f:
                f.write(data)
            row = StoryAttachment(
                story_id=story_id,
                organization_id=current_user.organization_id,
                filename=f"{frame_names.get(node_id, node_id)}.png",
                file_path=save_filename,
                mime_type="image/png",
                file_size=len(data),
                caption=f"figma-capture:{node_id}",
            )
            db.add(row)
            saved.append({
                "node_id": node_id,
                "frame_name": frame_names.get(node_id, ""),
                "size_bytes": len(data),
            })
    await db.commit()

    return {"captured": len(saved), "attachments": saved}


@router.post("/capture-figma-images-bulk")
async def bulk_capture_figma_images(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    """Capture Figma images for every story in the project that has a figma_file_url.

    Skips stories that already have a figma-capture attachment. Good for
    backfilling images after an import.
    """

    stories = (await db.execute(
        select(UserStory).where(
            UserStory.project_id == project_id,
            UserStory.organization_id == current_user.organization_id,
            UserStory.figma_file_url.isnot(None),
            UserStory.deleted_at.is_(None),
        )
    )).scalars().all()

    results = []
    errors = []
    for story in stories:
        try:
            res = await capture_figma_images(
                project_id=project_id,
                story_id=story.id,
                db=db,
                current_user=current_user,
            )
            results.append({"story_id": str(story.id), "title": story.title, **res})
        except HTTPException as exc:
            errors.append({"story_id": str(story.id), "title": story.title, "error": exc.detail})
        except Exception as exc:  # noqa: BLE001
            errors.append({"story_id": str(story.id), "title": story.title, "error": str(exc)})
    return {
        "processed": len(stories),
        "captured_total": sum(r.get("captured", 0) for r in results),
        "results": results,
        "errors": errors,
    }
