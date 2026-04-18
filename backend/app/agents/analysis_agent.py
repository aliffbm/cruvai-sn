"""Analyzer Agent runner — produces a StoryAnalysis record for a user story.

Deployed as a first-class agent (AgentDefinition slug='analyzer-agent'),
dispatched via the standard run_agent_job Celery path. Benefits from toolkit
enrichment (delegation + guidance) like the other primary agents.
"""

from __future__ import annotations

import json
import logging
import uuid
from pathlib import Path
from typing import Any

from sqlalchemy.orm import Session

from app.config import settings
from app.services.analysis_service import analysis_service
from app.services.llm_service import get_api_key

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_fallback_prompt() -> str:
    path = PROMPTS_DIR / "analyzer_agent.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return ""


async def run_analysis_agent(job_id: str, job, story, db: Session) -> dict:
    """Execute the Analyzer Agent workflow:

    1. Load toolkit-enriched system prompt (delegation + guidance)
    2. Assemble context (story, epic, figma design, existing OOB on SN instance)
    3. Call Claude with JSON-only response contract
    4. Persist StoryAnalysis via AnalysisService
    5. Log attribution and return summary
    """

    from anthropic import AsyncAnthropic
    from app.agents.base_agent import build_enriched_system_prompt
    from app.services.prompt_service import prompt_service
    from app.workers.agent_tasks import publish_log

    if story is None:
        raise ValueError("Analyzer agent requires a story")

    org_id = job.organization_id

    publish_log(job_id, "agent", "Analyzer starting — assembling context...")

    # --- Base system prompt (from control plane, fallback to .md) ----------
    base_prompt = prompt_service.render_agent_system_prompt_sync(
        db, org_id, "analyzer"
    ) or _load_fallback_prompt()
    if not base_prompt:
        raise RuntimeError(
            "Analyzer prompt missing. Run seed or set analyzer-agent-system prompt."
        )

    # --- Toolkit enrichment (delegation + guidance) -----------------------
    triggers: list[str] = []
    for src in (story.title, getattr(story, "description", "")):
        if src:
            triggers.extend(t for t in src.lower().split() if len(t) > 3)
    try:
        system_prompt = build_enriched_system_prompt(
            db,
            agent_slug="analyzer-agent",
            base_system_prompt=base_prompt,
            org_id=org_id,
            triggers=triggers,
            label="production",
            max_guidance=5,
        )
    except Exception as exc:  # noqa: BLE001 - never block analysis on enrichment
        logger.warning("Analyzer prompt enrichment failed: %s", exc)
        system_prompt = base_prompt

    # --- Story context ---------------------------------------------------
    ac = story.acceptance_criteria or ""
    story_block = (
        f"## Story\n"
        f"- Title: {story.title}\n"
        f"- Priority: {story.priority}\n"
        f"- Description: {story.description or '(none)'}\n"
        f"- Acceptance Criteria:\n{ac}\n"
    )

    # --- Epic context (if this story has a parent) -----------------------
    epic_block = ""
    if story.parent_story_id:
        from app.models.story import UserStory

        epic = db.query(UserStory).filter(UserStory.id == story.parent_story_id).first()
        if epic is not None:
            epic_block = (
                f"\n## Parent Epic\n"
                f"- Title: {epic.title}\n"
                f"- Description: {epic.description or '(none)'}\n"
            )

    # --- Figma context --------------------------------------------------
    figma_block = ""
    if story.figma_file_url:
        try:
            from app.models.project import Project
            from app.services.figma_service import figma_service

            project = db.query(Project).filter(Project.id == job.project_id).first()
            if project and project.figma_connector_id:
                publish_log(job_id, "info", f"Fetching Figma context: {story.figma_file_url}")
                design = await figma_service.extract_design(
                    connector_id=project.figma_connector_id,
                    figma_url=story.figma_file_url,
                    db=db,
                )
                pages = []
                for p in design.pages[:8]:
                    frames = ", ".join(f.name for f in p.frames[:6])
                    pages.append(f"- **{p.name}**: {frames}")
                colors = [c.get("name", "") for c in design.colors[:10] if c.get("name")]
                fonts = [f for f in design.fonts[:6] if f]
                figma_block = (
                    f"\n## Figma Design Context\n"
                    f"**File:** {design.file_name} ({design.file_key})\n"
                    f"**Pages ({len(design.pages)}):**\n{chr(10).join(pages)}\n"
                    f"**Palette:** colors=[{', '.join(colors) or 'n/a'}]; "
                    f"fonts=[{', '.join(fonts) or 'n/a'}]\n"
                    f"**Target node:** {story.figma_node_id or '(whole file)'}\n"
                )
        except Exception as exc:  # noqa: BLE001 - degrade without figma
            publish_log(job_id, "warn", f"Figma fetch skipped: {exc}")

    # --- OOB survey on target SN instance --------------------------------
    oob_block = ""
    try:
        oob_block = await _oob_survey(job_id, job, story, db)
    except Exception as exc:  # noqa: BLE001 - best effort
        publish_log(job_id, "warn", f"OOB survey skipped: {exc}")

    user_message = (
        f"{story_block}{epic_block}{figma_block}{oob_block}\n"
        f"Produce the JSON analysis per the system contract. Strict JSON only."
    )

    publish_log(job_id, "agent", "Calling Claude for analysis...")
    api_key = get_api_key(db, org_id, "anthropic")
    client = AsyncAnthropic(api_key=api_key)
    model = settings.default_model
    response = await client.messages.create(
        model=model,
        max_tokens=4096,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    response_text = response.content[0].text.strip()
    json_text = _extract_json(response_text)
    try:
        payload = json.loads(json_text)
    except json.JSONDecodeError as exc:
        publish_log(job_id, "error", f"Analyzer produced invalid JSON: {exc}")
        raise ValueError(f"Analyzer produced invalid JSON: {exc}") from exc

    # --- Persist ---------------------------------------------------------
    analysis = analysis_service.create_from_agent_sync(
        db,
        story_id=story.id,
        organization_id=org_id,
        payload=payload,
        authored_by_agent_slug="analyzer-agent",
        authored_by_job_id=job.id,
        authored_by_model=model,
    )
    db.commit()

    summary_line = (
        f"Analysis v{analysis.version_number} produced. "
        f"{len(analysis.proposed_artifacts or [])} proposed artifacts, "
        f"{len(analysis.oob_reuse or [])} OOB reuse candidates, "
        f"{len(analysis.risks or [])} risks, "
        f"{len(analysis.acceptance_criteria_mapping or [])} AC items mapped."
    )
    publish_log(job_id, "info", summary_line)

    return {
        "status": "completed",
        "summary": summary_line,
        "analysis_id": str(analysis.id),
        "version_number": analysis.version_number,
    }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _oob_survey(job_id: str, job, story, db: Session) -> str:
    """Query the target SN instance for existing widgets/pages that match the
    story keywords — candidates for OOB reuse. Returns a markdown block.
    """

    from app.connectors.table_api import TableAPIConnector
    from app.models.instance import ServiceNowInstance, InstanceCredential
    from app.utils.encryption import decrypt_value
    from app.workers.agent_tasks import publish_log

    instance_id = getattr(job, "instance_id", None)
    if not instance_id:
        return ""

    instance = db.query(ServiceNowInstance).filter(
        ServiceNowInstance.id == instance_id
    ).first()
    if not instance:
        return ""
    cred = db.query(InstanceCredential).filter(
        InstanceCredential.instance_id == instance.id,
        InstanceCredential.is_active.is_(True),
    ).first()
    if not cred:
        return ""

    connector = TableAPIConnector(
        instance_url=instance.instance_url,
        username=decrypt_value(cred.username_encrypted) if cred.username_encrypted else None,
        password=decrypt_value(cred.password_encrypted) if cred.password_encrypted else None,
    )

    # Build keyword set from story title
    keywords = [w for w in (story.title or "").lower().split() if len(w) > 3][:5]
    if not keywords:
        await connector.close()
        return ""

    publish_log(
        job_id, "info",
        f"OOB survey on {instance.instance_url}: keywords={keywords}",
    )

    results: list[dict[str, Any]] = []
    try:
        for kw in keywords:
            # sp_widget — OOB widgets matching keyword in name or id
            widgets = await connector.query_records(
                "sp_widget",
                f"nameLIKE{kw}^ORidLIKE{kw}",
                fields=["sys_id", "name", "id", "short_description"],
                limit=5,
            )
            for w in widgets:
                results.append({"table": "sp_widget", **w})
            # sp_portal
            portals = await connector.query_records(
                "sp_portal",
                f"titleLIKE{kw}^ORurl_suffixLIKE{kw}",
                fields=["sys_id", "title", "url_suffix"],
                limit=3,
            )
            for p in portals:
                results.append({"table": "sp_portal", **p})
    finally:
        await connector.close()

    if not results:
        return ""

    # Deduplicate by sys_id
    seen: set[str] = set()
    unique: list[dict[str, Any]] = []
    for r in results:
        sid = r.get("sys_id", "")
        if sid and sid not in seen:
            seen.add(sid)
            unique.append(r)

    lines = ["\n## OOB Survey (reusable candidates on target instance)"]
    for r in unique[:20]:
        tbl = r.get("table")
        name = r.get("name") or r.get("title") or r.get("id") or r.get("sys_id")
        desc = r.get("short_description") or r.get("url_suffix") or ""
        lines.append(f"- `{tbl}` · {name} · sys_id={r.get('sys_id', '')} · {desc}")
    return "\n".join(lines) + "\n"


def _extract_json(text: str) -> str:
    """Strip markdown fences if the model wrapped the JSON despite the contract."""
    stripped = text.strip()
    if stripped.startswith("```"):
        # e.g. ```json\n...\n```
        if "\n" in stripped:
            stripped = stripped.split("\n", 1)[1]
        if stripped.endswith("```"):
            stripped = stripped[: -3]
    return stripped.strip()
