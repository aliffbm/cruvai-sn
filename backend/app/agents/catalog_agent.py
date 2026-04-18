"""
Catalog Agent — Builds ServiceNow catalog items, variables, flows,
business rules, and client scripts from user stories.
"""

import json
import logging
import uuid
from pathlib import Path

from app.config import settings
from app.connectors.table_api import TableAPIConnector
from app.models.instance import ServiceNowInstance, InstanceCredential
from app.utils.encryption import decrypt_value
from app.workers.agent_tasks import publish_log

logger = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"


def _load_prompt(name: str) -> str:
    """Fallback: load from .md file if DB prompt not available."""
    return (PROMPTS_DIR / name).read_text(encoding="utf-8")


async def run_catalog_agent(job_id: str, job, story, db) -> dict:
    """
    Execute the Catalog Agent workflow:
    1. Analyze story -> 2. Plan artifacts -> 3. Create update set ->
    4. Build catalog item + variables -> 5. Build scripts -> 6. Validate -> 7. Summarize
    """
    from anthropic import AsyncAnthropic

    # Load SN connector
    instance = db.query(ServiceNowInstance).filter(
        ServiceNowInstance.id == job.instance_id
    ).first()
    if not instance:
        raise ValueError("ServiceNow instance not found")

    cred = db.query(InstanceCredential).filter(
        InstanceCredential.instance_id == instance.id,
        InstanceCredential.is_active.is_(True),
    ).first()
    if not cred:
        raise ValueError("No credentials for instance")

    connector = TableAPIConnector(
        instance_url=instance.instance_url,
        username=decrypt_value(cred.username_encrypted) if cred.username_encrypted else None,
        password=decrypt_value(cred.password_encrypted) if cred.password_encrypted else None,
    )

    # Load prompts from AI Control Plane (DB-backed, versioned)
    from app.services.prompt_service import prompt_service
    system_prompt = prompt_service.render_agent_system_prompt_sync(
        db, job.organization_id, "catalog"
    )
    if not system_prompt:
        # Fallback to .md files during migration
        publish_log(job_id, "info", "Using fallback .md prompts (DB prompts not found)")
        system_prompt = f"{_load_prompt('shared_context.md')}\n\n{_load_prompt('catalog_agent.md')}"
    else:
        publish_log(job_id, "info", "Loaded prompts from AI Control Plane")

    # Toolkit enrichment — delegation + applicable guidance
    try:
        from app.agents.base_agent import build_enriched_system_prompt

        triggers: list[str] = []
        if story and getattr(story, "title", None):
            triggers.extend(t for t in story.title.lower().split() if len(t) > 3)
        if story and getattr(story, "description", None):
            triggers.extend(
                t for t in story.description.lower().split()[:40] if len(t) > 3
            )
        system_prompt = build_enriched_system_prompt(
            db,
            agent_slug="catalog-agent",
            base_system_prompt=system_prompt,
            org_id=job.organization_id,
            triggers=triggers,
            label="production",
            max_guidance=5,
        )
    except Exception as exc:  # noqa: BLE001 - never block agent dispatch
        logger.warning("Catalog prompt enrichment failed: %s", exc)

    # Build story context
    story_text = ""
    if story:
        story_text = f"""
## User Story
**Title:** {story.title}
**Description:** {story.description or 'N/A'}
**Acceptance Criteria:** {story.acceptance_criteria or 'N/A'}
**Priority:** {story.priority}
"""

    # Step 1: Analyze story with Claude
    publish_log(job_id, "agent", "Analyzing user story...")

    from app.services.llm_service import get_api_key
    try:
        api_key = get_api_key(db, job.organization_id, "anthropic")
    except ValueError as e:
        raise ValueError(str(e))
    client = AsyncAnthropic(api_key=api_key)
    analysis_response = await client.messages.create(
        model=settings.default_model,
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"""Analyze this user story and produce a JSON plan of what ServiceNow artifacts to create.

{story_text}

Respond with ONLY valid JSON in this format:
{{
    "catalog_item": {{
        "name": "...",
        "short_description": "...",
        "description": "..."
    }},
    "variables": [
        {{
            "name": "variable_name",
            "question_text": "Label for user",
            "type": "6",
            "mandatory": true,
            "choices": [{{"text": "...", "value": "..."}}]
        }}
    ],
    "business_rules": [
        {{
            "name": "...",
            "table": "sc_req_item",
            "when": "after",
            "insert": true,
            "description": "..."
        }}
    ],
    "client_scripts": [
        {{
            "name": "...",
            "table": "sc_cat_item",
            "type": "onChange",
            "field_name": "...",
            "description": "..."
        }}
    ]
}}""",
            },
        ],
    )

    plan_text = analysis_response.content[0].text
    publish_log(job_id, "agent", "Story analyzed. Building artifact plan.")

    # Parse the plan
    try:
        # Extract JSON from response (handle markdown code blocks)
        json_str = plan_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        plan = json.loads(json_str.strip())
    except json.JSONDecodeError as e:
        publish_log(job_id, "error", f"Failed to parse plan: {e}")
        raise ValueError(f"Agent produced invalid plan JSON: {e}")

    artifacts_created = []

    # Step 2: Create update set
    publish_log(job_id, "info", "Creating update set on ServiceNow...")
    story_ref = story.title[:50] if story else "Agent-generated"
    update_set = await connector.create_update_set(
        name=f"Cruvai - {story_ref}",
        description=f"Auto-generated by Cruvai Catalog Agent for job {job_id}",
    )
    update_set_sys_id = update_set.get("sys_id", "")
    publish_log(job_id, "info", f"Update set created: {update_set.get('name')} ({update_set_sys_id})")

    # Step 3: Create catalog item
    cat_item_plan = plan.get("catalog_item", {})
    publish_log(job_id, "info", f"Creating catalog item: {cat_item_plan.get('name', 'Unknown')}")
    cat_item = await connector.create_catalog_item(
        name=cat_item_plan.get("name", story.title if story else "New Item"),
        short_description=cat_item_plan.get("short_description", ""),
        description=cat_item_plan.get("description", ""),
    )
    cat_item_sys_id = cat_item.get("sys_id", "")
    artifacts_created.append({
        "type": "catalog_item",
        "name": cat_item_plan.get("name"),
        "sn_table": "sc_cat_item",
        "sn_sys_id": cat_item_sys_id,
    })
    publish_log(job_id, "info", f"Catalog item created: {cat_item_sys_id}")

    # Step 4: Create variables
    for i, var_plan in enumerate(plan.get("variables", [])):
        publish_log(job_id, "info", f"Creating variable: {var_plan.get('name', f'var_{i}')}")
        var_record = await connector.create_catalog_variable(
            cat_item_sys_id=cat_item_sys_id,
            name=var_plan.get("name", f"variable_{i}"),
            question_text=var_plan.get("question_text", var_plan.get("name", "")),
            variable_type=str(var_plan.get("type", "6")),
            mandatory=var_plan.get("mandatory", False),
            order=(i + 1) * 100,
        )
        artifacts_created.append({
            "type": "catalog_variable",
            "name": var_plan.get("name"),
            "sn_table": "item_option_new",
            "sn_sys_id": var_record.get("sys_id", ""),
        })

    # Step 5: Create business rules (with AI-generated scripts)
    for br_plan in plan.get("business_rules", []):
        publish_log(job_id, "info", f"Generating business rule: {br_plan.get('name', 'Unknown')}")

        # Ask Claude to generate the script
        script_response = await client.messages.create(
            model=settings.default_model,
            max_tokens=2048,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"""Generate a ServiceNow business rule script for:
Name: {br_plan.get('name')}
Table: {br_plan.get('table', 'sc_req_item')}
When: {br_plan.get('when', 'after')}
Description: {br_plan.get('description', '')}

Context: This is for a catalog item named "{cat_item_plan.get('name')}".

IMPORTANT:
- Use getValue()/setValue() not dot notation
- Return ONLY the script content, no markdown or explanation""",
                },
            ],
        )
        script = script_response.content[0].text.strip()
        if script.startswith("```"):
            script = script.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        br_record = await connector.create_business_rule(
            name=br_plan.get("name", "Auto-generated rule"),
            table=br_plan.get("table", "sc_req_item"),
            script=script,
            when=br_plan.get("when", "after"),
            insert=br_plan.get("insert", False),
            update=br_plan.get("update", False),
        )
        artifacts_created.append({
            "type": "business_rule",
            "name": br_plan.get("name"),
            "sn_table": "sys_script",
            "sn_sys_id": br_record.get("sys_id", ""),
            "script_content": script,
        })

    # Step 6: Create client scripts
    for cs_plan in plan.get("client_scripts", []):
        publish_log(job_id, "info", f"Generating client script: {cs_plan.get('name', 'Unknown')}")

        script_response = await client.messages.create(
            model=settings.default_model,
            max_tokens=2048,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"""Generate a ServiceNow client script for:
Name: {cs_plan.get('name')}
Table: {cs_plan.get('table', 'sc_cat_item')}
Type: {cs_plan.get('type', 'onChange')}
Field: {cs_plan.get('field_name', '')}
Description: {cs_plan.get('description', '')}

Return ONLY the script content, no markdown or explanation.""",
                },
            ],
        )
        script = script_response.content[0].text.strip()
        if script.startswith("```"):
            script = script.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        cs_record = await connector.create_client_script(
            name=cs_plan.get("name", "Auto-generated script"),
            table=cs_plan.get("table", "sc_cat_item"),
            script=script,
            script_type=cs_plan.get("type", "onChange"),
        )
        artifacts_created.append({
            "type": "client_script",
            "name": cs_plan.get("name"),
            "sn_table": "sys_script_client",
            "sn_sys_id": cs_record.get("sys_id", ""),
            "script_content": script,
        })

    # Step 7: Save artifacts to database
    publish_log(job_id, "info", "Saving artifacts to database...")
    from app.models.artifact import Artifact

    for art in artifacts_created:
        db_artifact = Artifact(
            organization_id=job.organization_id,
            project_id=job.project_id,
            job_id=job.id,
            story_id=job.story_id,
            instance_id=job.instance_id,
            sn_table=art["sn_table"],
            sn_sys_id=art["sn_sys_id"],
            name=art.get("name", ""),
            artifact_type=art["type"],
            content_snapshot=art,
            script_content=art.get("script_content"),
            status="deployed",
            deployed_to_update_set_id=None,
        )
        db.add(db_artifact)
    db.commit()

    summary = f"Created {len(artifacts_created)} artifacts: " + ", ".join(
        f"{a['type']}({a.get('name', '')})" for a in artifacts_created
    )
    publish_log(job_id, "info", summary)

    await connector.close()

    return {
        "status": "completed",
        "summary": summary,
        "artifacts": artifacts_created,
        "update_set_sys_id": update_set_sys_id,
    }
