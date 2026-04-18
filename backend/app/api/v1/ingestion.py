"""Ingestion Runs API — list runs, inspect stats, trigger a new ingest."""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.deps import get_current_user, get_db, sync_session_factory
from app.ingestion.toolkit_ingest.runner import run_ingestion
from app.models.control_plane import ToolkitIngestionRun
from app.services.storage.factory import get_storage_backend

router = APIRouter()


class RunResponse(BaseModel):
    id: uuid.UUID
    started_at: datetime
    finished_at: datetime | None
    source_root: str | None
    source_commit: str | None
    status: str
    stats: dict | None
    triggered_by_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class TriggerRequest(BaseModel):
    root: str | None = None
    org_id: uuid.UUID | None = None  # None = system ingest


@router.get("", response_model=list[RunResponse])
async def list_runs(db: AsyncSession = Depends(get_db)):
    rows = (
        await db.execute(
            select(ToolkitIngestionRun).order_by(ToolkitIngestionRun.started_at.desc()).limit(100)
        )
    ).scalars().all()
    return [RunResponse.model_validate(r) for r in rows]


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(run_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    row = (await db.execute(select(ToolkitIngestionRun).where(ToolkitIngestionRun.id == run_id))).scalar_one_or_none()
    if row is None:
        raise HTTPException(404, "Run not found")
    return RunResponse.model_validate(row)


def _run_ingest_sync(root: Path, org_id: uuid.UUID | None, user_id: uuid.UUID) -> None:
    """Background-task wrapper — fresh sync session + backend."""

    storage = get_storage_backend()
    with sync_session_factory() as db:
        run_ingestion(
            db,
            toolkit_root=root,
            storage=storage,
            organization_id=org_id,
            triggered_by_id=user_id,
            dry_run=False,
        )


@router.post("/trigger", status_code=202)
async def trigger(
    body: TriggerRequest,
    background_tasks: BackgroundTasks,
    user = Depends(get_current_user),
):
    """Kick off an ingestion in the background. Returns immediately."""

    # Only org admins may trigger ingests.
    if not getattr(user, "is_org_admin", False):
        raise HTTPException(403, "Only org admins can trigger ingestion")
    root_str = body.root or settings.toolkit_root or "~/.claude"
    root = Path(root_str).expanduser().resolve()
    if not root.is_dir():
        raise HTTPException(400, f"Toolkit root does not exist: {root}")
    background_tasks.add_task(_run_ingest_sync, root, body.org_id, user.id)
    return {"status": "started", "root": str(root)}
