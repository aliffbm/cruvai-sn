"""
Portal Agent — Builds ServiceNow Service Portal solutions including
portals, pages, widgets, themes, and CSS includes from user stories.
"""

import json
import logging
import uuid

from app.config import settings
from app.connectors.table_api import TableAPIConnector
from app.models.instance import ServiceNowInstance, InstanceCredential
from app.services.prompt_service import PromptService
from app.utils.encryption import decrypt_value
from app.workers.agent_tasks import publish_log

logger = logging.getLogger(__name__)

prompt_service = PromptService()

FALLBACK_PORTAL_PROMPT = '''
# Portal Builder Agent

You are an expert ServiceNow Service Portal developer. You build complete
portal solutions from user stories, following ServiceNow best practices.

## Service Portal Architecture
- **sp_portal**: Top-level portal record with URL suffix, theme, and default pages
- **sp_page**: Container pages that hold widget instances and define URL routes
- **sp_widget**: Reusable UI components with HTML template, CSS, client script, and server script
- **sp_instance**: Binding record that places a widget on a page at a specific column/order
- **sp_theme**: Portal-wide styling with CSS variables, header/footer widget references
- **sp_css**: Reusable CSS includes linked to themes or portals
- **sp_header_footer**: Configures header and footer widgets for a portal

## Widget Development Conventions
- **HTML Template**: Use Angular 1.x directives (ng-repeat, ng-if, ng-click, ng-model)
- **Client Script**: Angular 1.x controller function — receives `$scope`, `spUtil`, `$location`, `$http`
- **Server Script**: Runs in Rhino engine with GlideRecord access — populate `data` object for the client
- **CSS**: SCSS supported — scope styles to the widget using the widget class wrapper
- Always use `data.*` to pass values between server script and client template
- Use `c.data` or `data` in templates to reference server-provided values
- Use `c.server.update()` to push client changes back to the server script

## Responsive Design
- Use Bootstrap 3 grid classes (col-xs-*, col-sm-*, col-md-*, col-lg-*)
- Widgets should be mobile-friendly by default
- Use sp-page layout columns (1, 2, or 3 column layouts)

## Best Practices
- Keep widgets focused and single-purpose
- Use widget options (sp_instance_option) for configuration rather than hardcoding
- Follow ServiceNow naming conventions: prefix custom widgets with a namespace
- Use $sp API methods: $sp.getRecord(), $sp.getStream(), $sp.getWidget()
- Handle errors gracefully with try/catch in server scripts
- Use GlideRecord best practices: addQuery, addEncodedQuery, setLimit, chooseWindow
- Sanitize user input via GlideSPScriptable or server-side validation
'''


async def run_portal_agent(job_id: str, job, story, db) -> dict:
    """
    Execute the Portal Agent workflow:
    1. Load connector + prompts -> 2. Analyze story -> 3. Plan portal artifacts ->
    4. Create update set -> 5. Build theme -> portal -> widgets -> pages -> instances ->
    6. Generate widget code via Claude -> 7. Save artifacts -> 8. Return summary
    """
    from anthropic import AsyncAnthropic

    # ── Load SN connector ──────────────────────────────────────────────
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

    # ── Resolve system prompt ──────────────────────────────────────────
    story_text = ""
    if story:
        story_text = f"""
## User Story
**Title:** {story.title}
**Description:** {story.description or 'N/A'}
**Acceptance Criteria:** {story.acceptance_criteria or 'N/A'}
**Priority:** {story.priority}
"""

    # ── Optional: fetch Figma design if the story links to one ─────────
    figma_context = ""
    if story and getattr(story, "figma_file_url", None):
        try:
            from app.models.project import Project
            from app.services.figma_service import figma_service
            from sqlalchemy.ext.asyncio import AsyncSession  # noqa: F401

            project_id = getattr(job, "project_id", None)
            project = None
            if project_id:
                project = db.query(Project).filter(Project.id == project_id).first()

            if project is None or project.figma_connector_id is None:
                publish_log(
                    job_id,
                    "warn",
                    "Story has figma_file_url but project has no figma_connector_id — skipping design fetch",
                )
            else:
                publish_log(job_id, "agent", f"Fetching Figma design: {story.figma_file_url}")
                # figma_service is async-capable; run via asyncio loop (this fn is async)
                design = await figma_service.extract_design(
                    connector_id=project.figma_connector_id,
                    figma_url=story.figma_file_url,
                    db=db,
                )
                page_lines = []
                for page in design.pages[:5]:
                    frames = ", ".join(f.name for f in page.frames[:8])
                    page_lines.append(f"- **{page.name}**: frames = [{frames}]")
                color_names = [c.get("name", "") for c in design.colors[:12] if c.get("name")]
                font_names = [f for f in design.fonts[:8] if f]
                figma_context = f"""
## Figma Design Context
**File:** {design.file_name} ({design.file_key})
**Pages ({len(design.pages)}):**
{chr(10).join(page_lines) if page_lines else '(none parsed)'}
**Style palette:** colors=[{', '.join(color_names) if color_names else 'n/a'}]; fonts=[{', '.join(font_names) if font_names else 'n/a'}]

Use the page/frame names as candidate portal pages. Use the color palette to seed the
theme's CSS variables. Map Figma frame hierarchy to widget composition where obvious.
"""
                publish_log(
                    job_id,
                    "info",
                    f"Figma design parsed: {len(design.pages)} pages, "
                    f"{sum(len(p.frames) for p in design.pages)} frames",
                    metadata={
                        "file_key": design.file_key,
                        "pages": [p.name for p in design.pages[:10]],
                    },
                )
        except Exception as exc:  # noqa: BLE001 - never block the job on Figma failure
            publish_log(
                job_id, "warn",
                f"Figma fetch failed: {exc} — proceeding without design context",
            )

    if figma_context:
        story_text = story_text + "\n" + figma_context

    variables = {"story": story_text}
    system_prompt = prompt_service.render_agent_system_prompt_sync(
        db, job.organization_id, "portal", variables
    )
    if not system_prompt:
        logger.info("No DB prompts found for portal agent, using fallback")
        system_prompt = FALLBACK_PORTAL_PROMPT

    # Toolkit enrichment — append Available Specialists + Applicable Guidance
    # blocks based on AgentCapability graph and trigger-keyword ranking.
    try:
        from app.agents.base_agent import build_enriched_system_prompt

        triggers: list[str] = []
        if story and story.title:
            triggers.extend(t for t in story.title.lower().split() if len(t) > 3)
        if story and story.description:
            triggers.extend(
                t for t in story.description.lower().split()[:40] if len(t) > 3
            )
        system_prompt = build_enriched_system_prompt(
            db,
            agent_slug="portal-agent",
            base_system_prompt=system_prompt,
            org_id=job.organization_id,
            triggers=triggers,
            label="production",
            max_guidance=5,
        )
    except Exception as exc:  # noqa: BLE001 - never block the agent on enrichment
        logger.warning("Portal prompt enrichment failed: %s", exc)

    # ── Init Claude client ─────────────────────────────────────────────
    from app.services.llm_service import get_api_key

    try:
        api_key = get_api_key(db, job.organization_id, "anthropic")
    except ValueError as e:
        raise ValueError(str(e))

    client = AsyncAnthropic(api_key=api_key)

    # ── Step 1: Analyze story and produce portal plan ──────────────────
    publish_log(job_id, "agent", "Analyzing user story for portal requirements...")

    analysis_response = await client.messages.create(
        model=settings.default_model,
        max_tokens=4096,
        system=system_prompt,
        messages=[
            {
                "role": "user",
                "content": f"""Analyze this user story and produce a JSON plan for the Service Portal solution.

{story_text}

Respond with ONLY valid JSON in this format:
{{
    "portal": {{
        "name": "Portal Display Name",
        "url_suffix": "portal_url",
        "theme": {{
            "name": "Theme Name",
            "css_variables": {{"--primary-color": "#1a73e8", "--bg-color": "#ffffff"}},
            "navbar_fixed": true
        }}
    }},
    "pages": [
        {{
            "title": "Page Title",
            "id": "page_url_id",
            "widgets": [
                {{
                    "widget_ref": "custom_widget_id_or_ootb_name",
                    "column": 0,
                    "order": 0,
                    "parameters": {{}}
                }}
            ]
        }}
    ],
    "custom_widgets": [
        {{
            "name": "Widget Name",
            "id": "widget-unique-id",
            "description": "What this widget does",
            "data_table": "optional_table_name"
        }}
    ]
}}""",
            },
        ],
    )

    plan_text = analysis_response.content[0].text
    publish_log(job_id, "agent", "Story analyzed. Building portal plan.")

    # Parse the plan
    try:
        json_str = plan_text
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]
        plan = json.loads(json_str.strip())
    except json.JSONDecodeError as e:
        publish_log(job_id, "error", f"Failed to parse portal plan: {e}")
        raise ValueError(f"Agent produced invalid plan JSON: {e}")

    artifacts_created = []

    # ── Step 2: Create update set ──────────────────────────────────────
    publish_log(job_id, "info", "Creating update set on ServiceNow...")
    story_ref = story.title[:50] if story else "Agent-generated"
    update_set = await connector.create_update_set(
        name=f"Cruvai Portal - {story_ref}",
        description=f"Auto-generated by Cruvai Portal Agent for job {job_id}",
    )
    update_set_sys_id = update_set.get("sys_id", "")
    publish_log(job_id, "info", f"Update set created: {update_set.get('name')} ({update_set_sys_id})")

    # ── Step 3: Create theme ───────────────────────────────────────────
    theme_plan = plan.get("portal", {}).get("theme", {})
    theme_sys_id = None
    if theme_plan:
        publish_log(job_id, "info", f"Creating theme: {theme_plan.get('name', 'Portal Theme')}")
        css_vars = theme_plan.get("css_variables", {})
        css_vars_string = "\n".join(f"{k}: {v};" for k, v in css_vars.items())

        theme_data = {
            "name": theme_plan.get("name", f"{plan['portal']['name']} Theme"),
            "css_variables": css_vars_string,
            "navbar_fixed": str(theme_plan.get("navbar_fixed", True)).lower(),
        }
        theme_record = await connector.create_record("sp_theme", theme_data)
        theme_sys_id = theme_record.get("sys_id", "")
        artifacts_created.append({
            "type": "theme",
            "name": theme_plan.get("name"),
            "sn_table": "sp_theme",
            "sn_sys_id": theme_sys_id,
        })
        publish_log(job_id, "info", f"Theme created: {theme_sys_id}")

    # ── Step 4: Create or reuse portal ───────────────────────────────────
    portal_plan = plan.get("portal", {})
    portal_url_suffix = portal_plan.get("url_suffix", "custom_portal")
    publish_log(job_id, "info", f"Checking for existing portal: {portal_url_suffix}")

    # Check if portal already exists (idempotent)
    existing_portals = await connector.query_records(
        "sp_portal", f"url_suffix={portal_url_suffix}",
        fields=["sys_id", "title", "url_suffix"], limit=1
    )
    if existing_portals:
        portal_sys_id = existing_portals[0].get("sys_id", "")
        publish_log(job_id, "info", f"Reusing existing portal: {portal_sys_id}")
    else:
        publish_log(job_id, "info", f"Creating portal: {portal_plan.get('name', 'New Portal')}")
        portal_data: dict = {
            "title": portal_plan.get("name", story.title if story else "New Portal"),
            "url_suffix": portal_url_suffix,
        }
        if theme_sys_id:
            portal_data["sp_theme"] = theme_sys_id
        portal_record = await connector.create_record("sp_portal", portal_data)
        portal_sys_id = portal_record.get("sys_id", "")

    artifacts_created.append({
        "type": "portal",
        "name": portal_plan.get("name"),
        "sn_table": "sp_portal",
        "sn_sys_id": portal_sys_id,
    })
    publish_log(job_id, "info", f"Portal ready: {portal_sys_id}")

    # ── Step 5: Create custom widgets (with AI-generated code) ─────────
    widget_id_map = {}  # maps widget plan id -> sys_id
    for w_plan in plan.get("custom_widgets", []):
        widget_name = w_plan.get("name", "Custom Widget")
        widget_id = w_plan.get("id", f"widget-{uuid.uuid4().hex[:8]}")
        publish_log(job_id, "info", f"Generating widget code: {widget_name}")

        # Ask Claude to generate all widget components
        widget_response = await client.messages.create(
            model=settings.default_model,
            max_tokens=4096,
            system=system_prompt,
            messages=[
                {
                    "role": "user",
                    "content": f"""Generate a complete ServiceNow Service Portal widget for:

Name: {widget_name}
ID: {widget_id}
Description: {w_plan.get('description', '')}
Data Table: {w_plan.get('data_table', 'none')}

Portal Context: This widget is part of a portal named "{portal_plan.get('name', '')}".

Respond with ONLY valid JSON (no markdown) in this exact format:
{{
    "template": "<div>...Angular 1.x HTML template...</div>",
    "css": "/* widget CSS */",
    "client_script": "// Angular client controller\\napi.controller = function($scope) {{ ... }};",
    "server_script": "// Server script\\n(function() {{ ... }})();"
}}

IMPORTANT:
- Template must use Angular 1.x directives (ng-repeat, ng-if, ng-click)
- Client script must be a proper Angular controller
- Server script must use GlideRecord with getValue()/setValue()
- CSS should be scoped and responsive
- Return ONLY the JSON, no explanation""",
                },
            ],
        )

        widget_code_text = widget_response.content[0].text.strip()
        if widget_code_text.startswith("```"):
            widget_code_text = widget_code_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

        try:
            widget_code = json.loads(widget_code_text)
        except json.JSONDecodeError as e:
            publish_log(job_id, "error", f"Failed to parse widget code for {widget_name}: {e}")
            # Use empty defaults so the widget record is still created
            widget_code = {
                "template": f"<div class=\"{widget_id}\"><p>Widget placeholder</p></div>",
                "css": "",
                "client_script": "api.controller = function($scope) {};",
                "server_script": "(function() { /* server script */ })();",
            }

        widget_data = {
            "name": widget_name,
            "id": widget_id,
            "template": widget_code.get("template", ""),
            "css": widget_code.get("css", ""),
            "client_script": widget_code.get("client_script", ""),
            "script": widget_code.get("server_script", ""),
        }
        if w_plan.get("description"):
            widget_data["short_description"] = w_plan["description"]
        if w_plan.get("data_table"):
            widget_data["data_table"] = w_plan["data_table"]

        # Check if widget already exists (idempotent)
        existing_widgets = await connector.query_records(
            "sp_widget", f"id={widget_id}", fields=["sys_id"], limit=1
        )
        if existing_widgets:
            widget_sys_id = existing_widgets[0].get("sys_id", "")
            publish_log(job_id, "info", f"Reusing existing widget: {widget_name} ({widget_sys_id})")
        else:
            try:
                widget_record = await connector.create_record("sp_widget", widget_data)
                widget_sys_id = widget_record.get("sys_id", "")
                publish_log(job_id, "info", f"Widget created: {widget_name} ({widget_sys_id})")
            except Exception as e:
                publish_log(job_id, "warn", f"Failed to create widget {widget_name}: {e} — skipping")
                continue

        widget_id_map[widget_id] = widget_sys_id
        artifacts_created.append({
            "type": "widget",
            "name": widget_name,
            "sn_table": "sp_widget",
            "sn_sys_id": widget_sys_id,
            "script_content": json.dumps(widget_code, indent=2),
        })

    # ── Step 6: Create pages with full layout hierarchy ─────────────────
    # ServiceNow layout: sp_page -> sp_container -> sp_row -> sp_column -> sp_instance
    portal_suffix = plan.get("portal", {}).get("url_suffix", "portal").strip("/")
    first_page_sys_id = None

    for page_plan in plan.get("pages", []):
        page_title = page_plan.get("title", "New Page")
        raw_page_id = page_plan.get("id", f"page_{uuid.uuid4().hex[:8]}")
        # Prefix page IDs with portal suffix to avoid OOB conflicts
        reserved_ids = ("index", "home", "landing", "search", "form", "ticket", "kb", "sc")
        page_id = f"{portal_suffix}_{raw_page_id}" if raw_page_id in reserved_ids else raw_page_id
        publish_log(job_id, "info", f"Creating page: {page_title} (id={page_id})")

        # Check if page already exists (idempotent)
        existing_pages = await connector.query_records(
            "sp_page", f"id={page_id}", fields=["sys_id"], limit=1
        )
        if existing_pages:
            page_sys_id = existing_pages[0].get("sys_id", "")
            publish_log(job_id, "info", f"Reusing existing page: {page_title} ({page_sys_id})")
        else:
            try:
                page_record = await connector.create_record("sp_page", {"title": page_title, "id": page_id})
                page_sys_id = page_record.get("sys_id", "")
                publish_log(job_id, "info", f"Page created: {page_title} ({page_sys_id})")
            except Exception as e:
                publish_log(job_id, "warn", f"Failed to create page {page_title}: {e} -- skipping")
                continue

        if first_page_sys_id is None:
            first_page_sys_id = page_sys_id

        artifacts_created.append({
            "type": "page",
            "name": page_title,
            "sn_table": "sp_page",
            "sn_sys_id": page_sys_id,
        })

        # Resolve widgets for this page
        page_widgets = page_plan.get("widgets", [])
        if not page_widgets:
            continue

        # Create a container for this page's widgets
        try:
            container_record = await connector.create_record("sp_container", {
                "sp_page": page_sys_id,
                "order": "100",
                "width": "fixed",
            })
            container_sys_id = container_record.get("sys_id", "")
            publish_log(job_id, "info", f"Container created for {page_title}")
        except Exception as e:
            publish_log(job_id, "warn", f"Failed to create container for {page_title}: {e} -- skipping widgets")
            continue

        # Create a row inside the container
        try:
            row_record = await connector.create_record("sp_row", {
                "sp_container": container_sys_id,
                "order": "100",
            })
            row_sys_id = row_record.get("sys_id", "")
        except Exception as e:
            publish_log(job_id, "warn", f"Failed to create row: {e} -- skipping widgets")
            continue

        # Create a full-width column (size 12) inside the row
        try:
            column_record = await connector.create_record("sp_column", {
                "sp_row": row_sys_id,
                "order": "100",
                "size": "12",
            })
            column_sys_id = column_record.get("sys_id", "")
        except Exception as e:
            publish_log(job_id, "warn", f"Failed to create column: {e} -- skipping widgets")
            continue

        # Place widget instances in the column
        for wi_idx, wi in enumerate(page_widgets):
            widget_ref = wi.get("widget_ref", wi.get("widget_name", ""))
            resolved_widget_sys_id = widget_id_map.get(widget_ref)

            if not resolved_widget_sys_id:
                # Look up OOTB widget by ID
                try:
                    lookup = await connector.query_records(
                        "sp_widget", f"id={widget_ref}", fields=["sys_id"], limit=1
                    )
                    if lookup:
                        resolved_widget_sys_id = lookup[0].get("sys_id")
                except Exception:
                    pass

            if not resolved_widget_sys_id:
                publish_log(job_id, "warn", f"Could not resolve widget '{widget_ref}' -- skipping")
                continue

            instance_data: dict = {
                "sp_column": column_sys_id,
                "sp_widget": resolved_widget_sys_id,
                "order": str(wi.get("order", (wi_idx + 1) * 100)),
            }
            params = wi.get("parameters")
            if params:
                instance_data["widget_parameters"] = json.dumps(params)

            try:
                instance_record = await connector.create_record("sp_instance", instance_data)
                publish_log(job_id, "info", f"Widget instance placed: {widget_ref} on {page_title}")
            except Exception as e:
                publish_log(job_id, "warn", f"Failed to place widget instance: {e} -- skipping")
                continue

            artifacts_created.append({
                "type": "widget_instance",
                "name": f"{widget_ref} on {page_title}",
                "sn_table": "sp_instance",
                "sn_sys_id": instance_record.get("sys_id", ""),
            })

    # Try to set homepage on portal (may fail due to ACL restrictions on PDIs)
    if first_page_sys_id and portal_sys_id:
        try:
            await connector.update_record("sp_portal", portal_sys_id, {"homepage": first_page_sys_id})
            publish_log(job_id, "info", f"Portal homepage set to first page")
        except Exception:
            publish_log(job_id, "warn", "Could not set portal homepage (ACL restriction) -- set manually")

    # ── Step 7: Save artifacts to database ─────────────────────────────
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

    # ── Step 8: Return summary ─────────────────────────────────────────
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
        "portal_sys_id": portal_sys_id,
        "portal_url_suffix": portal_plan.get("url_suffix", ""),
    }
