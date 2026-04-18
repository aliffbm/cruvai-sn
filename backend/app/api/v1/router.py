from fastapi import APIRouter

from app.api.v1 import (
    agents, artifacts, auth, capabilities, connectors, control_plane, guidance,
    ingestion, instances, jobs, playbooks, projects, settings, stories,
)

api_router = APIRouter()

api_router.include_router(auth.router, prefix="/auth", tags=["auth"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
api_router.include_router(instances.router, prefix="/instances", tags=["instances"])
api_router.include_router(stories.router, prefix="/projects/{project_id}/stories", tags=["stories"])
api_router.include_router(jobs.router, prefix="/projects/{project_id}/jobs", tags=["jobs"])
api_router.include_router(artifacts.router, prefix="/projects/{project_id}/artifacts", tags=["artifacts"])
api_router.include_router(agents.router, prefix="/agents", tags=["agents"])
api_router.include_router(settings.router, prefix="/settings", tags=["settings"])
api_router.include_router(control_plane.router, prefix="/control-plane", tags=["control-plane"])
api_router.include_router(connectors.router, prefix="/connectors", tags=["connectors"])
api_router.include_router(guidance.router, prefix="/guidance", tags=["guidance"])
api_router.include_router(capabilities.router, prefix="/capabilities", tags=["capabilities"])
api_router.include_router(playbooks.router, prefix="/playbooks", tags=["playbooks"])
api_router.include_router(ingestion.router, prefix="/ingestion", tags=["ingestion"])
