"""One-time script to regenerate ESS widget code via delete+recreate."""

import asyncio
import json
import sys

import httpx
from anthropic import AsyncAnthropic
from app.connectors.base import BaseServiceNowConnector
from app.services.llm_service import get_api_key
from app.workers.agent_tasks import get_sync_db
from app.config import settings

WIDGETS = [
    ("ess-welcome-banner", "Welcome Banner",
     "Display a welcome message with the logged-in user name, current date, and quick stats (open tickets count). Use a gradient background with navy (#1a365d) to dark (#0d1b2a)."),
    ("ess-quick-actions", "Quick Action Buttons",
     "Grid of 4 icon buttons: Report Issue, Request Something, View My Tickets, Search Knowledge Base. Each is a card with a Font Awesome icon and label."),
    ("ess-catalog-search", "Catalog Search",
     "Search bar that queries sc_cat_item table. Shows matching results as cards with name and short_description."),
    ("ess-catalog-categories", "Catalog Categories",
     "Display service catalog categories as clickable cards with name, description, and item count from sc_category table."),
    ("ess-my-tickets", "My Tickets Dashboard",
     "Table showing current user's open incidents (incident table) and requested items (sc_req_item table) with columns: Number, Short Description, State, Priority, Updated."),
    ("ess-kb-search", "Knowledge Base Search",
     "Search bar for knowledge articles (kb_knowledge table) with results showing title, snippet, and view count."),
]


async def main():
    db = get_sync_db()
    from sqlalchemy import select
    from app.models.org_settings import OrgApiKey
    from app.utils.encryption import decrypt_value
    result = db.execute(select(OrgApiKey).where(OrgApiKey.is_active.is_(True)).limit(1))
    key_record = result.scalar_one_or_none()
    if not key_record:
        print("No API key found!")
        sys.exit(1)
    api_key = decrypt_value(key_record.key_encrypted)
    db.close()

    c = BaseServiceNowConnector(
        "https://dev219386.service-now.com", "aliff.macapinlac", "Password123!"
    )
    client = AsyncAnthropic(api_key=api_key)

    # Also build a raw httpx client for delete (handles empty 204 responses)
    raw_client = httpx.AsyncClient(
        base_url="https://dev219386.service-now.com",
        auth=httpx.BasicAuth("aliff.macapinlac", "Password123!"),
        headers={"Accept": "application/json", "Content-Type": "application/json"},
        timeout=30.0,
    )

    for widget_id, name, description in WIDGETS:
        print(f"\n{'='*60}")
        print(f"Processing: {widget_id}")

        # Step 1: Delete existing widget if it exists
        existing = await c.query_records(
            "sp_widget", f"id={widget_id}", fields=["sys_id"], limit=1
        )
        if existing:
            old_sys_id = existing[0]["sys_id"]
            resp = await raw_client.delete(f"/api/now/table/sp_widget/{old_sys_id}")
            print(f"  Deleted old widget (status={resp.status_code})")
        else:
            print(f"  No existing widget to delete")

        # Step 2: Generate code with Claude
        print(f"  Generating code with Claude...")
        prompt = f"""Generate a complete ServiceNow Service Portal widget.

Widget Name: {name}
Widget ID: {widget_id}
Description: {description}

IMPORTANT RULES:
- HTML: AngularJS 1.x. Use c.data to access server data. Bootstrap 3 grid.
- CSS: Scope under .{widget_id} class. Dark theme (#1a365d primary, #e2e8f0 text, #a3e635 accent).
- Client: function($scope) {{ var c = this; }}
- Server: (function() {{ /* GlideRecord, getValue/setValue */ }})();
- Make it look professional and modern

Return ONLY a JSON object with 4 string fields: template, css, client_script, server_script
Do NOT wrap in markdown code blocks. Just raw JSON."""

        resp = await client.messages.create(
            model=settings.default_model,
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )

        code_text = resp.content[0].text.strip()
        if "```json" in code_text:
            code_text = code_text.split("```json")[1].split("```")[0]
        elif "```" in code_text:
            code_text = code_text.split("```")[1].split("```")[0]

        try:
            code = json.loads(code_text.strip())
        except json.JSONDecodeError as e:
            print(f"  JSON PARSE FAILED: {e}")
            continue

        tmpl = code.get("template", "")
        css = code.get("css", "")
        cs = code.get("client_script", "")
        ss = code.get("server_script", "")
        print(f"  Generated: template={len(tmpl)}ch css={len(css)}ch client={len(cs)}ch server={len(ss)}ch")

        # Step 3: Create new widget
        try:
            new_widget = await c.create_record("sp_widget", {
                "name": name,
                "id": widget_id,
                "template": tmpl,
                "css": css,
                "client_script": cs,
                "script": ss,
            })
            print(f"  CREATED: {new_widget.get('sys_id', '')}")
        except Exception as e:
            print(f"  CREATE FAILED: {e}")

    await raw_client.aclose()
    await c.close()
    print(f"\n{'='*60}")
    print("Done!")


if __name__ == "__main__":
    asyncio.run(main())
