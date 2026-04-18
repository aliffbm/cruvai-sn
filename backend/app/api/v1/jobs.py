import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import get_current_org_id, get_current_user, get_db
from app.models.job import AgentJob, JobLog, JobStep

router = APIRouter()


class JobCreate(BaseModel):
    agent_id: uuid.UUID
    story_id: uuid.UUID | None = None
    instance_id: uuid.UUID
    config_overrides: dict | None = None


class JobResponse(BaseModel):
    id: uuid.UUID
    project_id: uuid.UUID
    agent_id: uuid.UUID
    story_id: uuid.UUID | None
    instance_id: uuid.UUID
    status: str
    output_summary: str | None
    error_message: str | None
    started_at: datetime | None
    completed_at: datetime | None
    total_tokens_used: int
    total_api_calls: int

    model_config = {"from_attributes": True}


class JobStepResponse(BaseModel):
    id: uuid.UUID
    step_number: int
    step_type: str
    tool_name: str | None
    tool_input: dict | None
    tool_output: dict | None
    reasoning: str | None
    duration_ms: int
    status: str

    model_config = {"from_attributes": True}


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    project_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AgentJob).where(
            AgentJob.project_id == project_id,
            AgentJob.organization_id == org_id,
        ).order_by(AgentJob.created_at.desc())
    )
    return result.scalars().all()


@router.post("", response_model=JobResponse, status_code=201)
async def create_job(
    project_id: uuid.UUID,
    req: JobCreate,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
):
    job = AgentJob(
        organization_id=current_user.organization_id,
        project_id=project_id,
        agent_id=req.agent_id,
        story_id=req.story_id,
        instance_id=req.instance_id,
        initiated_by_id=current_user.id,
        input_params=req.config_overrides,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)

    # Dispatch to Celery worker
    from app.workers.agent_tasks import run_agent_job

    task = run_agent_job.delay(str(job.id))
    job.celery_task_id = task.id
    await db.commit()

    return job


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AgentJob).where(
            AgentJob.id == job_id,
            AgentJob.project_id == project_id,
            AgentJob.organization_id == org_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.get("/{job_id}/steps", response_model=list[JobStepResponse])
async def get_job_steps(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(JobStep).where(JobStep.job_id == job_id).order_by(JobStep.step_number)
    )
    return result.scalars().all()


@router.get("/{job_id}/stream")
async def stream_job_logs(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    import asyncio
    import json

    import redis.asyncio as aioredis

    from app.config import settings

    async def event_generator():
        r = aioredis.from_url(settings.redis_url)
        pubsub = r.pubsub()
        channel = f"job:{job_id}:logs"
        await pubsub.subscribe(channel)

        try:
            async for message in pubsub.listen():
                if message["type"] == "message":
                    data = message["data"]
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    yield f"data: {data}\n\n"
        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(channel)
            await r.aclose()

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@router.post("/{job_id}/approve", response_model=JobResponse)
async def approve_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AgentJob).where(
            AgentJob.id == job_id,
            AgentJob.organization_id == org_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status != "awaiting_approval":
        raise HTTPException(status_code=400, detail="Job is not awaiting approval")
    job.status = "running"
    await db.commit()

    # Resume the agent via Celery
    from app.workers.agent_tasks import resume_agent_job

    resume_agent_job.delay(str(job.id))

    await db.refresh(job)
    return job


@router.post("/{job_id}/reject", response_model=JobResponse)
async def reject_job(
    project_id: uuid.UUID,
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    org_id: uuid.UUID = Depends(get_current_org_id),
):
    result = await db.execute(
        select(AgentJob).where(
            AgentJob.id == job_id,
            AgentJob.organization_id == org_id,
        )
    )
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    job.status = "failed"
    job.error_message = "Rejected by reviewer"
    job.completed_at = datetime.now(timezone.utc)
    await db.commit()
    await db.refresh(job)
    return job
