# Cruvai ServiceNow Developer

Enterprise-grade AI agent platform for ServiceNow development. Agents
generate catalog items, service portals, flows, business rules, and other
ServiceNow artifacts from user stories — with **toolkit-driven specialist
delegation**, **versioned/governed prompts**, and a **Story Analysis review
workflow** (AI Agent Analyzer) that produces a reviewable technical design
before any build agent runs.

## Architecture at a glance

| Layer | Tech | Port |
|---|---|---|
| Frontend | Next.js 15, React 19, Tailwind CSS, Zustand | 3001 |
| Backend | FastAPI, SQLAlchemy 2.0 async, Alembic | 8001 |
| Worker | Celery + Redis broker | — |
| Database | PostgreSQL 16 + pgvector | 5434 |
| Cache / Queue | Redis 7 | 6380 |
| MCP Server | TypeScript, `@modelcontextprotocol/sdk` | stdio |

See `CLAUDE.md` for the full project map and development conventions.

## Key capabilities

- **Primary agents** — catalog, portal, ATF, CMDB, integration, documentation, code-review, update-set
- **AI Agent Analyzer** (deployed as a first-class agent) — produces a
  reviewable `StoryAnalysis` with OOB reuse candidates, proposed artifacts,
  AC coverage mapping, specialist consults, and risk assessment
- **Specialist delegation graph** — 32 specialist agents (react-specialist,
  security-auditor, postgres-pro, etc.) invokable by the primaries via
  `AgentCapability` rows
- **Governed guidance library** — 31 disciplined workflows (TDD,
  systematic-debugging, verification-before-completion, …) with
  production/staging/canary labels and SHA-256 content hashing
- **ServiceNow archetype playbooks** — `servicenow-platform-product` and
  `servicenow-scoped-app` route stories to primary + supporting agents
- **Append-only audit trail** (`StoryNote`) — requirement changes, analysis
  updates, and build outcomes auto-logged; manual notes supported
- **Figma integration** — import an epic + stories directly from a Figma
  design; capture frame PNGs as story attachments

---

# Getting started — new engineer, local setup

## 1. Install prerequisites

- **Docker Desktop** (or Docker Engine + Compose v2)
- **Git**
- **A terminal** — macOS/Linux, or Git Bash on Windows
- **An Anthropic API key** — https://console.anthropic.com
- *(Optional)* A **Figma Personal Access Token** — needed for design import
- *(Optional)* A **ServiceNow developer instance** (free at https://developer.servicenow.com) — needed to actually build artifacts

## 2. Install the AI Knowledge Repository toolkit

The platform ingests a 31-skill + 32-specialist toolkit from `~/.claude/`.
Install it globally once:

```bash
git clone https://github.com/aliffbm/AI-Knowledge-Repository.git "$HOME/AI-Knowledge-Repository"
bash "$HOME/AI-Knowledge-Repository/install-global.sh"
```

Verify:

```bash
ls ~/.claude/skills ~/.claude/agents ~/.claude/playbooks
```

You should see 31 skill directories, 32 agent `.md` files, and 2–3 playbooks.

## 3. Clone and configure this repo

```bash
git clone https://github.com/aliffbm/cruvai-sn.git
cd cruvai-sn
cp .env.example .env
```

Edit `.env` and fill in at minimum:

```bash
# Required
CRUVAI_ENCRYPTION_KEY=<run `make gen-key` to produce>
SECRET_KEY=<any 64-char random string>
ANTHROPIC_API_KEY=sk-ant-...

# Optional (can add later via the UI's Connectors page)
OPENAI_API_KEY=
```

Generate the encryption key:

```bash
make gen-key
# copy the printed value into CRUVAI_ENCRYPTION_KEY in .env
```

## 4. One-shot bootstrap

```bash
make bootstrap
```

This executes six steps automatically:

1. `docker compose up -d` — postgres, redis, backend, worker, frontend
2. `alembic upgrade head` — applies ~30 migrations (schema for the full control plane)
3. `python -m app.seed` — seeds 8 primary agents + 5 OOB prompts + 2 OOB skills
4. `docker cp ~/.claude → backend:/toolkit` — provisions the toolkit into the container
5. `python -m app.ingestion.toolkit_ingest --root /toolkit` — creates 31 guidance + 32 specialist agents + 2 playbooks + 361 guidance-assets
6. `python -m app.ingestion.toolkit_ingest.seed_capabilities` — wires 21 default delegation edges (Portal → react-specialist + 4 others, Catalog → backend-developer + 3 others, etc.)

**Expected runtime**: ~3–5 minutes (most of it is Docker image pulls on first run).

## 5. Verify the bootstrap

```bash
docker compose exec -T postgres psql -U cruvai -d cruvai_sn -c \
  "SELECT 'agent_definitions' t, COUNT(*) FROM agent_definitions
   UNION ALL SELECT 'agent_capabilities', COUNT(*) FROM agent_capabilities
   UNION ALL SELECT 'agent_guidance', COUNT(*) FROM agent_guidance
   UNION ALL SELECT 'agent_playbooks', COUNT(*) FROM agent_playbooks
   UNION ALL SELECT 'guidance_assets', COUNT(*) FROM guidance_assets;"
```

Expected:
```
 t                   | count
---------------------+-------
 agent_definitions   |    40
 agent_capabilities  |    21
 agent_guidance      |    31
 agent_playbooks     |     2
 guidance_assets     |   361
```

## 6. First-run workflow in the UI

1. Open http://localhost:3001
2. **Register** — first user becomes the org admin
3. **Connectors** (`/connectors`) — add **ServiceNow**, **Anthropic**, **Figma** connectors
4. **Instances** (`/instances`) — add your ServiceNow dev instance (URL + username/password)
5. **Create a project** — `/projects` → New project
6. **Project Settings** — attach ServiceNow instance, Figma connector, and active playbook (`servicenow-platform-product`)
7. **Create a story** — or click **Import from Figma** on the Stories tab and paste a Figma URL
8. **Run AI Agent Analyzer** on the story → approve the analysis
9. **Launch Agent** (portal-agent / catalog-agent / etc.) → watch the streaming job log

See [SETUP.md](SETUP.md) for day-2 operations (re-ingesting the toolkit, re-seeding capabilities, troubleshooting) and [CLAUDE.md](CLAUDE.md) for the full project conventions.

---

## Common commands

```bash
make up              # Start all services
make down            # Stop all services
make logs-backend    # Tail backend + worker logs
make migrate         # Apply pending migrations
make migration msg=  # Generate a new migration
make test            # Run pytest
make clean           # Stop + remove volumes (destructive)
make toolkit-reingest      # Re-ingest ~/.claude after local edits
make capabilities-reseed   # Re-seed the delegation graph
```

## Troubleshooting

- **`ModuleNotFoundError: No module named 'jinja2'`** — rebuild the image: `docker compose build backend worker && docker compose up -d`
- **Figma 429 Too Many Requests** — the per-file API rate limit was exceeded; generate a new Figma PAT and update the connector credentials
- **Analyzer dispatch fails: "No ServiceNow instance configured"** — open project Settings and pick an instance
- **Next.js pages are slow on first click** — Turbopack compiles routes lazily on first visit; subsequent visits are instant

## Development conventions

- **Plan before implementing** — see `~/.claude/skills/writing-plans/`
- **Test-driven changes** — see `~/.claude/skills/test-driven-development/`
- **Delegate to specialists for non-trivial work** — via `agent-organizer` or
  the built-in `CapabilityResolver.delegate_to(slug, task)`
- **Audit trail is append-only** — never `UPDATE story_notes`; write a new row

See `CLAUDE.md` for the complete development playbook and file-by-file conventions.

## License

Proprietary. © Cruvai.
