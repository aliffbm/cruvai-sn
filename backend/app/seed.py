"""Database seed script — run with: python -m app.seed"""

import hashlib
import uuid
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models import Base
from app.models.agent import AgentDefinition
from app.models.control_plane import (
    AgentPrompt, AgentPromptVersion, AgentPromptLabel,
    AgentSkill, AgentSkillStep,
)
from app.models.tenant import Role

PROMPTS_DIR = Path(__file__).parent / "agents" / "prompts"


def _content_hash(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _seed_prompt(db, slug, name, content, agent_type=None, category="system", description=None, tags=None):
    """Create an OOB system prompt with version 1 and production label."""
    existing = db.query(AgentPrompt).filter(
        AgentPrompt.slug == slug, AgentPrompt.organization_id.is_(None)
    ).first()
    if existing:
        return existing

    prompt = AgentPrompt(
        organization_id=None,  # System/OOB
        slug=slug,
        name=name,
        description=description or name,
        agent_type=agent_type,
        category=category,
        tags=tags or [],
        is_system=True,
        is_active=True,
    )
    db.add(prompt)
    db.flush()

    version = AgentPromptVersion(
        prompt_id=prompt.id,
        version_number=1,
        content=content,
        content_hash=_content_hash(content),
        change_notes="Initial OOB version",
    )
    db.add(version)
    db.flush()

    label = AgentPromptLabel(
        prompt_id=prompt.id,
        version_id=version.id,
        label="production",
        is_active=True,
    )
    db.add(label)
    db.flush()

    print(f"  Created prompt: {name} (v1 -> production)")
    return prompt


def _seed_skill(db, slug, name, agent_type, description, steps_data, pre_conditions=None, post_conditions=None):
    """Create an OOB system skill with steps."""
    existing = db.query(AgentSkill).filter(
        AgentSkill.slug == slug, AgentSkill.organization_id.is_(None)
    ).first()
    if existing:
        return existing

    skill = AgentSkill(
        organization_id=None,
        slug=slug,
        name=name,
        description=description,
        agent_type=agent_type,
        pre_conditions=pre_conditions,
        post_conditions=post_conditions,
        is_system=True,
        is_active=True,
    )
    db.add(skill)
    db.flush()

    for step_data in steps_data:
        step = AgentSkillStep(skill_id=skill.id, **step_data)
        db.add(step)

    db.flush()
    print(f"  Created skill: {name} ({len(steps_data)} steps)")
    return skill


# === Portal Agent System Prompt ===
PORTAL_AGENT_SYSTEM_PROMPT = """# Portal Builder Agent

You are the Portal Builder Agent — an AI developer that builds ServiceNow Service Portal solutions from user requirements.

## Your Workflow

1. **Analyze** the requirements and determine the portal structure
2. **Plan** pages, widgets, and theme
3. **Create an update set** to track all changes
4. **Build** the theme with CSS variables
5. **Build** the portal record
6. **Build** custom widgets (HTML + CSS + client script + server script)
7. **Build** pages and place widget instances
8. **Configure** header and footer
9. **Summarize** everything created

## Service Portal Architecture

### Portal Record (`sp_portal`)
- Each portal has a unique URL suffix (e.g., `/sp`, `/esc`, `/hrp`)
- Links to a theme, homepage, and optional knowledge base

### Pages (`sp_page`)
- Pages have a URL path identifier (e.g., `index`, `ticket`, `kb_article`)
- Pages contain widget instances arranged in a 12-column Bootstrap grid

### Widgets (`sp_widget`)
- Self-contained UI components with 4 code sections:
  - **HTML Template**: AngularJS 1.x template (use `ng-repeat`, `ng-if`, `ng-click`, `{{variable}}`)
  - **CSS/SCSS**: Scoped styles (prefixed with widget class)
  - **Client Controller**: AngularJS controller (`function($scope, spUtil, $http)`)
  - **Server Script**: GlideRecord-based data loading (`data.items = []; var gr = new GlideRecord('table'); ...`)
- **Link Function**: Optional, runs after DOM render

### Themes (`sp_theme`)
- CSS variables for consistent styling
- Header and footer widget assignments
- Navbar configuration

## Widget Best Practices

### HTML Templates
- Use AngularJS 1.x syntax (NOT Angular 2+)
- Use `ng-repeat` for lists, `ng-if` for conditionals
- Use `{{c.data.field}}` to bind server data (controller-as syntax with `c`)
- Use `sp-widget` directive to embed sub-widgets
- Use Bootstrap 3 grid classes (`col-xs-`, `col-sm-`, `col-md-`, `col-lg-`)

### Client Controllers
```javascript
function($scope, spUtil, $http, snRecordWatcher) {
  var c = this;
  // c.data is populated by server script
  c.doSomething = function() {
    c.server.get({action: 'getData'}).then(function(response) {
      c.data.items = response.data.items;
    });
  };
}
```

### Server Scripts
```javascript
(function() {
  if (input && input.action === 'getData') {
    data.items = [];
    var gr = new GlideRecord('sc_cat_item');
    gr.addActiveQuery();
    gr.query();
    while (gr.next()) {
      data.items.push({
        sys_id: gr.getUniqueValue(),
        name: gr.getValue('name'),
        short_description: gr.getValue('short_description')
      });
    }
  }
})();
```

### CSS
- Scope all styles to avoid leaking to other widgets
- Use the widget's unique class as a prefix
- Use CSS variables from the theme for consistency
- Ensure responsive design (test at mobile, tablet, desktop widths)

## OOB Widgets to Reference
- `widget-cool-clock` — simple widget structure example
- `sc-cat-item-guide` — catalog item display with variables
- `ticket-conversations` — complex widget with server-client communication
- `kb-article-content` — knowledge base article display
- `simple-list` — data table with pagination

## Output Format

Respond with a JSON plan:
```json
{
  "portal": {
    "name": "...",
    "url_suffix": "...",
    "description": "..."
  },
  "theme": {
    "name": "...",
    "css_variables": {"--brand-primary": "#...", "--nav-bg": "#..."},
    "navbar_fixed": true
  },
  "pages": [
    {
      "title": "...",
      "id": "...",
      "widgets": [
        {"widget_name": "...", "column": 1, "order": 1, "is_custom": true},
        {"widget_name": "simple-list", "column": 1, "order": 2, "is_custom": false}
      ]
    }
  ],
  "custom_widgets": [
    {
      "name": "...",
      "id": "...",
      "description": "..."
    }
  ]
}
```
"""

PORTAL_WIDGET_GENERATOR_PROMPT = """# Widget Code Generator

Generate the complete code for a ServiceNow Service Portal widget.

## Context
Portal: {{portal_name}}
Widget: {{widget_name}}
Description: {{widget_description}}
Data Requirements: {{data_requirements}}

## Requirements
Generate ALL four code sections:

1. **HTML Template** — AngularJS 1.x template using Bootstrap 3 grid
2. **CSS** — Scoped styles, responsive, using theme CSS variables
3. **Client Controller** — AngularJS controller with `function($scope, spUtil, $http)`
4. **Server Script** — GlideRecord data loading wrapped in `(function() { ... })();`

## Rules
- Use `c.data` for server-to-client data binding
- Use `c.server.get()` for client-to-server calls
- Use `getValue()`/`setValue()` in server scripts, never dot notation
- All CSS must be scoped (no global selectors)
- HTML must be responsive (use Bootstrap 3 col-xs/sm/md/lg classes)

Respond with ONLY valid JSON:
```json
{
  "template": "<div class=\\"widget-name\\">...</div>",
  "css": ".widget-name { ... }",
  "client_script": "function($scope, spUtil, $http) { var c = this; ... }",
  "server_script": "(function() { ... })();"
}
```
"""


def seed():
    engine = create_engine(settings.database_url_sync)
    Session = sessionmaker(bind=engine)
    db = Session()

    # === Seed Roles ===
    roles = [
        {"name": "admin", "description": "Full access", "permissions": {"all": True}},
        {"name": "developer", "description": "Can create stories, run agents, view artifacts", "permissions": {"projects.write": True, "agents.run": True, "stories.write": True}},
        {"name": "reviewer", "description": "Can review and approve agent output", "permissions": {"reviews.write": True, "jobs.approve": True}},
        {"name": "viewer", "description": "Read-only access", "permissions": {"projects.read": True}},
    ]
    for role_data in roles:
        existing = db.query(Role).filter(Role.name == role_data["name"]).first()
        if not existing:
            db.add(Role(**role_data))
            print(f"  Created role: {role_data['name']}")

    # === Seed Agent Definitions ===
    agents = [
        {
            "name": "Catalog Item & Flow Agent",
            "slug": "catalog-agent",
            "description": "Builds ServiceNow catalog items, record producers, flows, business rules, client scripts, UI policies, and notifications from user stories.",
            "agent_type": "catalog",
            "available_tools": ["sn_query", "sn_get_record", "sn_create_record", "sn_update_record", "sn_get_schema", "sn_build_catalog_item", "sn_build_flow", "sn_build_business_rule", "sn_build_client_script", "sn_build_ui_policy", "sn_create_update_set", "sn_validate_script"],
            "default_model": "claude-sonnet-4-20250514",
            "max_steps": 50,
            "requires_approval": True,
        },
        {
            "name": "Portal Builder Agent",
            "slug": "portal-agent",
            "description": "Builds ServiceNow Service Portal pages, widgets, themes, and configurations from requirements.",
            "agent_type": "portal",
            "available_tools": ["sn_query", "sn_get_record", "sn_create_record", "sn_update_record", "sn_get_schema", "sn_create_update_set", "sn_build_portal", "sn_build_portal_page", "sn_build_widget", "sn_build_widget_instance", "sn_build_theme", "sn_build_css_include", "sn_build_header_footer"],
            "default_model": "claude-sonnet-4-20250514",
            "max_steps": 60,
            "requires_approval": True,
        },
        {
            "name": "ATF Test Agent",
            "slug": "atf-agent",
            "description": "Generates comprehensive ATF test cases from user stories and acceptance criteria.",
            "agent_type": "atf",
            "available_tools": ["sn_query", "sn_get_record", "sn_create_record", "sn_get_schema", "sn_create_test_suite", "sn_create_test", "sn_run_tests"],
            "default_model": "claude-sonnet-4-20250514",
            "max_steps": 30,
            "requires_approval": False,
        },
        {
            "name": "Integration Builder Agent",
            "slug": "integration-agent",
            "description": "Builds custom ServiceNow integrations — IntegrationHub spokes, REST integrations, scripted REST APIs.",
            "agent_type": "integration",
            "available_tools": ["sn_query", "sn_get_record", "sn_create_record", "sn_update_record", "sn_get_schema", "sn_validate_script"],
            "default_model": "claude-sonnet-4-20250514",
            "max_steps": 40,
            "requires_approval": True,
        },
        {
            "name": "Documentation Agent",
            "slug": "documentation-agent",
            "description": "Auto-generates technical documentation, solution designs, and as-built docs.",
            "agent_type": "documentation",
            "available_tools": ["sn_query", "sn_get_record", "sn_get_schema"],
            "default_model": "claude-sonnet-4-20250514",
            "max_steps": 20,
            "requires_approval": False,
        },
        {
            "name": "CMDB Agent",
            "slug": "cmdb-agent",
            "description": "CMDB health checks, CI deduplication, relationship mapping, and data quality monitoring.",
            "agent_type": "cmdb",
            "available_tools": ["sn_query", "sn_get_record", "sn_create_record", "sn_update_record", "sn_get_schema"],
            "default_model": "claude-sonnet-4-20250514",
            "max_steps": 30,
            "requires_approval": True,
        },
        {
            "name": "Code Review Agent",
            "slug": "code-review-agent",
            "description": "Reviews ServiceNow scripts for best practices, security, performance, and naming conventions.",
            "agent_type": "code_review",
            "available_tools": ["sn_query", "sn_get_record", "sn_validate_script"],
            "default_model": "claude-sonnet-4-20250514",
            "max_steps": 20,
            "requires_approval": False,
        },
        {
            "name": "Update Set Manager Agent",
            "slug": "update-set-agent",
            "description": "Manages update sets — creation, tracking, and cross-instance deployment.",
            "agent_type": "update_set",
            "available_tools": ["sn_query", "sn_get_record", "sn_create_update_set", "sn_list_update_sets", "sn_complete_update_set"],
            "default_model": "claude-sonnet-4-20250514",
            "max_steps": 15,
            "requires_approval": False,
        },
        {
            "name": "AI Agent Analyzer",
            "slug": "analyzer-agent",
            "description": "Reviews a user story, consults toolkit specialists and guidance, surveys the target ServiceNow instance for OOB reuse, and produces a reviewable technical design (StoryAnalysis) before any build agent runs.",
            "agent_type": "analyzer",
            "available_tools": ["sn_query", "sn_get_record", "sn_get_schema"],
            "default_model": "claude-sonnet-4-20250514",
            "max_steps": 10,
            "requires_approval": False,
        },
    ]
    for agent_data in agents:
        existing = db.query(AgentDefinition).filter(AgentDefinition.slug == agent_data["slug"]).first()
        if not existing:
            db.add(AgentDefinition(**agent_data))
            print(f"  Created agent: {agent_data['name']}")

    db.commit()

    # === Seed OOB Prompts (AI Control Plane) ===
    print("\nSeeding AI Control Plane prompts...")

    # Load from .md files if they exist, otherwise use inline content
    shared_context_content = ""
    catalog_agent_content = ""
    try:
        shared_context_content = (PROMPTS_DIR / "shared_context.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        shared_context_content = "# ServiceNow Development Best Practices\n\nYou are an expert ServiceNow developer agent."

    try:
        catalog_agent_content = (PROMPTS_DIR / "catalog_agent.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        catalog_agent_content = "# Catalog Item & Flow Agent\n\nYou build ServiceNow catalog items from user stories."

    _seed_prompt(db, "shared-context", "Shared Context — SN Best Practices",
                 shared_context_content,
                 agent_type=None, category="shared_context",
                 description="ServiceNow development best practices shared across all agents",
                 tags=["shared", "best-practices", "servicenow"])

    _seed_prompt(db, "catalog-agent-system", "Catalog Agent System Prompt",
                 catalog_agent_content,
                 agent_type="catalog", category="system",
                 description="System prompt for the Catalog Item & Flow Agent",
                 tags=["catalog", "system-prompt"])

    _seed_prompt(db, "portal-agent-system", "Portal Builder Agent System Prompt",
                 PORTAL_AGENT_SYSTEM_PROMPT,
                 agent_type="portal", category="system",
                 description="System prompt for the Portal Builder Agent — Service Portal pages, widgets, themes",
                 tags=["portal", "system-prompt", "service-portal"])

    _seed_prompt(db, "portal-widget-generator", "Portal Widget Code Generator",
                 PORTAL_WIDGET_GENERATOR_PROMPT,
                 agent_type="portal", category="task",
                 description="Generates widget code (HTML/CSS/client/server) for Service Portal widgets",
                 tags=["portal", "widget", "code-generation"],
                 )

    # Analyzer Agent system prompt
    analyzer_agent_content = ""
    try:
        analyzer_agent_content = (PROMPTS_DIR / "analyzer_agent.md").read_text(encoding="utf-8")
    except FileNotFoundError:
        analyzer_agent_content = (
            "# AI Agent Analyzer\n\nProduce a JSON technical design for the given story."
        )
    _seed_prompt(db, "analyzer-agent-system", "AI Agent Analyzer System Prompt",
                 analyzer_agent_content,
                 agent_type="analyzer", category="system",
                 description="System prompt for the AI Agent Analyzer (design review + OOB reuse + AC mapping)",
                 tags=["analyzer", "system-prompt", "review"])

    db.commit()

    # === Seed OOB Skills ===
    print("\nSeeding AI Control Plane skills...")

    _seed_skill(db, "catalog-build-workflow", "Catalog Build Workflow", "catalog",
                "End-to-end workflow for building catalog items from user stories",
                steps_data=[
                    {"step_number": 1, "name": "Analyze Story", "step_type": "llm_call",
                     "prompt_slug": "catalog-agent-system", "description": "Analyze user story and produce artifact plan"},
                    {"step_number": 2, "name": "Create Update Set", "step_type": "tool_call",
                     "tool_name": "sn_create_update_set", "description": "Create update set to track changes"},
                    {"step_number": 3, "name": "Build Catalog Item", "step_type": "tool_call",
                     "tool_name": "sn_build_catalog_item", "description": "Create catalog item with variables"},
                    {"step_number": 4, "name": "Generate Business Rules", "step_type": "loop",
                     "description": "Generate and create business rules from the plan"},
                    {"step_number": 5, "name": "Generate Client Scripts", "step_type": "loop",
                     "description": "Generate and create client scripts from the plan"},
                    {"step_number": 6, "name": "Validate Scripts", "step_type": "tool_call",
                     "tool_name": "sn_validate_script", "description": "Validate all generated scripts"},
                    {"step_number": 7, "name": "Review Gate", "step_type": "tool_call",
                     "is_approval_gate": True, "description": "Pause for human review before finalization"},
                ],
                pre_conditions={"requires": ["instance_connected", "story_ready"]},
                post_conditions={"produces": ["catalog_item", "variables", "business_rules"]})

    _seed_skill(db, "portal-build-workflow", "Portal Build Workflow", "portal",
                "End-to-end workflow for building Service Portal solutions",
                steps_data=[
                    {"step_number": 1, "name": "Analyze Requirements", "step_type": "llm_call",
                     "prompt_slug": "portal-agent-system", "description": "Analyze requirements and produce portal plan"},
                    {"step_number": 2, "name": "Create Update Set", "step_type": "tool_call",
                     "tool_name": "sn_create_update_set", "description": "Create update set"},
                    {"step_number": 3, "name": "Build Theme", "step_type": "tool_call",
                     "tool_name": "sn_build_theme", "description": "Create portal theme with CSS variables"},
                    {"step_number": 4, "name": "Build Portal", "step_type": "tool_call",
                     "tool_name": "sn_build_portal", "description": "Create portal record"},
                    {"step_number": 5, "name": "Generate Custom Widgets", "step_type": "loop",
                     "prompt_slug": "portal-widget-generator",
                     "description": "Generate code and create each custom widget"},
                    {"step_number": 6, "name": "Build Pages", "step_type": "loop",
                     "tool_name": "sn_build_portal_page", "description": "Create portal pages"},
                    {"step_number": 7, "name": "Place Widget Instances", "step_type": "loop",
                     "tool_name": "sn_build_widget_instance", "description": "Place widgets on pages"},
                    {"step_number": 8, "name": "Configure Header/Footer", "step_type": "tool_call",
                     "tool_name": "sn_build_header_footer", "description": "Set header and footer widgets"},
                    {"step_number": 9, "name": "Review Gate", "step_type": "tool_call",
                     "is_approval_gate": True, "description": "Pause for human review"},
                ],
                pre_conditions={"requires": ["instance_connected", "story_ready"]},
                post_conditions={"produces": ["portal", "pages", "widgets", "theme"]})

    db.commit()
    db.close()
    print("\nSeed complete!")


if __name__ == "__main__":
    seed()
