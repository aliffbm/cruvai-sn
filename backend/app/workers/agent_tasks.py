import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

import redis
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def get_sync_db():
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(settings.database_url_sync)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()


def publish_log(job_id: str, level: str, message: str, metadata: dict | None = None):
    """Publish a log entry to Redis PubSub for SSE streaming."""
    r = redis.from_url(settings.redis_url)
    log_entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "level": level,
        "message": message,
        "metadata": metadata,
    }
    r.publish(f"job:{job_id}:logs", json.dumps(log_entry))

    # Also persist to database
    db = get_sync_db()
    try:
        from app.models.job import JobLog

        db_log = JobLog(
            job_id=uuid.UUID(job_id),
            level=level,
            message=message,
            metadata_json=metadata,
        )
        db.add(db_log)
        db.commit()
    finally:
        db.close()


@celery_app.task(name="run_agent_job", bind=True)
def run_agent_job(self, job_id: str):
    """Execute an agent job. This is the main entry point for agent execution."""
    db = get_sync_db()
    try:
        from app.models.job import AgentJob
        from app.models.agent import AgentDefinition
        from app.models.story import UserStory

        job = db.query(AgentJob).filter(AgentJob.id == uuid.UUID(job_id)).first()
        if not job:
            logger.error(f"Job {job_id} not found")
            return

        job.status = "running"
        job.started_at = datetime.now(timezone.utc)
        job.celery_task_id = self.request.id
        db.commit()

        publish_log(job_id, "info", "Agent job started")

        # Load agent definition
        agent_def = db.query(AgentDefinition).filter(AgentDefinition.id == job.agent_id).first()
        if not agent_def:
            job.status = "failed"
            job.error_message = "Agent definition not found"
            db.commit()
            publish_log(job_id, "error", "Agent definition not found")
            return

        # Load story if present
        story = None
        if job.story_id:
            story = db.query(UserStory).filter(UserStory.id == job.story_id).first()

        publish_log(job_id, "info", f"Running {agent_def.name} agent")

        # Run the agent graph asynchronously
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            result = loop.run_until_complete(
                _run_agent(job_id, agent_def, job, story, db)
            )

            if result.get("status") == "awaiting_approval":
                job.status = "awaiting_approval"
                publish_log(job_id, "agent", "Awaiting approval before deployment")
            else:
                job.status = "completed"
                job.output_summary = result.get("summary", "")
                job.completed_at = datetime.now(timezone.utc)
                publish_log(job_id, "info", "Agent job completed successfully")

            _write_build_outcome_note(
                db, job, agent_def, story,
                status=job.status,
                summary=result.get("summary", ""),
                result=result,
            )

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            job.completed_at = datetime.now(timezone.utc)
            publish_log(job_id, "error", f"Agent failed: {e}")
            logger.exception(f"Agent job {job_id} failed")
            _write_build_outcome_note(
                db, job, agent_def, story,
                status="failed",
                summary=f"Agent failed: {e}",
                result={"error": str(e)},
            )

        finally:
            loop.close()

        db.commit()

    finally:
        db.close()


@celery_app.task(name="resume_agent_job")
def resume_agent_job(job_id: str):
    """Resume an agent job after approval."""
    db = get_sync_db()
    try:
        from app.models.job import AgentJob

        job = db.query(AgentJob).filter(AgentJob.id == uuid.UUID(job_id)).first()
        if not job:
            return

        publish_log(job_id, "info", "Job approved — resuming agent")

        # TODO: Resume LangGraph from checkpoint
        job.status = "completed"
        job.completed_at = datetime.now(timezone.utc)
        job.output_summary = "Approved and deployed"
        db.commit()

        publish_log(job_id, "info", "Agent job completed after approval")

    finally:
        db.close()


async def _run_agent(job_id, agent_def, job, story, db):
    """Run the appropriate agent based on agent_def.agent_type."""
    publish_log(job_id, "info", f"Initializing {agent_def.agent_type} agent")

    # Resolve playbook routing + capabilities + applicable guidance before dispatch.
    # These are logged so operators can see what would be injected even before
    # individual agent runners adopt the enrichment helpers.
    try:
        _log_toolkit_context(job_id, agent_def, job, story, db)
    except Exception as exc:  # noqa: BLE001 - never block agent dispatch on telemetry
        logger.exception("Failed to resolve toolkit context for job %s: %s", job_id, exc)

    if agent_def.agent_type == "catalog":
        from app.agents.catalog_agent import run_catalog_agent
        return await run_catalog_agent(job_id, job, story, db)
    elif agent_def.agent_type == "portal":
        from app.agents.portal_agent import run_portal_agent
        return await run_portal_agent(job_id, job, story, db)
    elif agent_def.agent_type == "analyzer":
        from app.agents.analysis_agent import run_analysis_agent
        return await run_analysis_agent(job_id, job, story, db)
    else:
        raise ValueError(f"Unknown agent type: {agent_def.agent_type}")


def _write_build_outcome_note(
    db: Session, job, agent_def, story, *, status: str, summary: str, result: dict | None
) -> None:
    """Append a build_outcome StoryNote when an agent job terminates.

    Safe-guarded: a note failure never propagates. Only fires when the job has
    a story_id attached (analyzer + build agents all set this).
    """
    try:
        story_id = getattr(job, "story_id", None)
        if not story_id:
            return
        from app.services.note_service import note_service

        note_content = (
            f"Agent `{agent_def.slug}` job {job.id} {status}."
            + (f" Summary: {summary}" if summary else "")
        )
        diff = None
        if result:
            diff = {k: result.get(k) for k in ("summary", "analysis_id", "artifacts") if k in result}
        note_service.write_sync(
            db,
            story_id=story_id,
            organization_id=job.organization_id,
            note_type="build_outcome",
            content=note_content,
            diff=diff,
            related_id=job.id,
            author_agent_slug=agent_def.slug,
            author_job_id=job.id,
        )
        db.flush()
    except Exception as exc:  # noqa: BLE001 - never fail the job on a note write
        logger.warning("Build outcome note write failed for job %s: %s", getattr(job, "id", None), exc)


def _log_toolkit_context(job_id: str, agent_def, job, story, db: Session) -> None:
    """Resolve + log playbook route, capabilities, and applicable guidance.

    Observable side-effects only: emits job log entries. The agent runners
    pick these up via build_enriched_system_prompt when they opt in.
    """

    from app.agents.base_agent import build_enriched_system_prompt  # noqa: F401 - ensure importable
    from app.services.capability_service import capability_resolver
    from app.services.guidance_service import guidance_service
    from app.services.playbook_service import playbook_service

    org_id = getattr(job, "organization_id", None)

    # Playbook routing — slug stored on Project.settings_json["playbook_slug"]
    playbook_slug = None
    if getattr(job, "project_id", None):
        from app.models.project import Project

        project = db.query(Project).filter(Project.id == job.project_id).first()
        if project and isinstance(project.settings_json, dict):
            playbook_slug = project.settings_json.get("playbook_slug")

    story_title = getattr(story, "title", "") if story else ""
    story_desc = getattr(story, "description", "") if story else ""

    match = playbook_service.resolve_for_story_sync(
        db,
        playbook_slug=playbook_slug,
        story_title=story_title,
        story_description=story_desc,
        org_id=org_id,
    )
    if match is not None:
        publish_log(
            job_id,
            "info",
            f"Playbook route matched: {match.playbook_slug} — pattern='{match.matched_pattern}'",
            metadata={
                "playbook_slug": match.playbook_slug,
                "primary_agent_id": str(match.primary_agent_id) if match.primary_agent_id else None,
                "supporting_agent_ids": [str(x) for x in match.supporting_agent_ids],
                "required_guidance_ids": [str(x) for x in match.required_guidance_ids],
                "match_type": match.match_type,
            },
        )

    # Capabilities — which specialists this primary can delegate to
    specialists = capability_resolver.get_specialists_for_sync(
        db, primary_agent_slug=agent_def.slug, org_id=org_id
    )
    if specialists:
        publish_log(
            job_id,
            "info",
            f"Delegation available to {len(specialists)} specialists",
            metadata={"specialists": [s.specialist_slug for s in specialists]},
        )

    # Guidance — trigger keywords seeded from story title + description
    triggers: list[str] = []
    if story_title:
        triggers.extend(t for t in story_title.lower().split() if len(t) > 3)
    if story_desc:
        triggers.extend(t for t in story_desc.lower().split()[:40] if len(t) > 3)

    guidance_versions = guidance_service.resolve_guidance_for_agent_sync(
        db,
        org_id=org_id,
        agent_slug=agent_def.slug,
        triggers=triggers,
        label="production",
        top_n=5,
    )
    if guidance_versions:
        publish_log(
            job_id,
            "info",
            f"{len(guidance_versions)} guidance entries applicable at production label",
            metadata={
                "guidance": [
                    {
                        "slug": v.guidance.slug if v.guidance else None,
                        "version": v.version_number,
                        "authorship": v.authorship,
                    }
                    for v in guidance_versions
                ]
            },
        )
