# Setup — Cruvai ServiceNow Developer Platform

Cold-start guide to get a new environment to the canonical state (schema +
governance config + toolkit + capabilities) in under 5 minutes.

## Prerequisites

- **Docker + Docker Compose**
- **AI Knowledge Repository toolkit** installed at `~/.claude/`.
  If missing:
  ```bash
  git clone https://github.com/aliffbm/AI-Knowledge-Repository.git "$HOME/AI-Knowledge-Repository"
  bash "$HOME/AI-Knowledge-Repository/install-global.sh"
  ```
  This populates `~/.claude/skills/` (31 skills), `~/.claude/agents/` (32
  specialist agents), and `~/.claude/playbooks/` (2 ServiceNow archetypes).
- **`.env`** in the repo root. Copy from `.env.example` and fill in:
  - `CRUVAI_ENCRYPTION_KEY` — Fernet key for credential encryption. Generate: `make gen-key`
  - `SECRET_KEY` — JWT signing key. Use any 64-char random string.
  - `ANTHROPIC_API_KEY` — required for agent LLM calls.

## One-shot bootstrap

```bash
make bootstrap
```

This runs:

| Step | What | Produces |
|---|---|---|
| 1 | `make up` | All 5 services (postgres, redis, backend, worker, frontend) |
| 2 | `alembic upgrade head` | Schema: ~30 tables incl. control plane, toolkit, story analysis |
| 3 | `python -m app.seed` | 8 primary agents, OOB prompts (5), OOB skills (2) |
| 4 | `make toolkit-sync` | `docker cp ~/.claude → /toolkit` in backend container |
| 5 | `python -m app.ingestion.toolkit_ingest` | 31 AgentGuidance + 32 specialist AgentDefinitions + 2 Playbooks + 361 GuidanceAssets |
| 6 | `python -m app.ingestion.toolkit_ingest.seed_capabilities` | 21 delegation edges (primary → specialists) |

Expected end state:

```sql
 table                    | rows
-------------------------+------
 agent_definitions       |   40   -- 8 primary + 32 specialists
 agent_capabilities      |   21   -- delegation graph
 agent_prompts           |    5   -- OOB governed prompts
 agent_guidance          |   31   -- toolkit skills
 agent_guidance_versions |   31   -- v1 of each, all staging
 agent_playbooks         |    2   -- platform-product, scoped-app
 agent_playbook_routes   |   30
 guidance_assets         |  361   -- content-addressed aux files
```

## Post-bootstrap

After bootstrap, open http://localhost:3001:

1. **Register an account** (first user auto-becomes org admin)
2. **Add connectors** under `/connectors`:
   - ServiceNow (basic auth: username + password)
   - Anthropic (API key — required for agents)
   - Figma (PAT — required for design imports)
3. **Create a project** → in the project's **Settings** page, attach:
   - ServiceNow instance
   - Figma connector
   - Active playbook (e.g. `servicenow-platform-product`)
4. **Import stories from Figma** or create them manually.
5. **Run the AI Agent Analyzer** on a story → approve the analysis → launch the build agent.

## Day-2 operations

| Task | Command |
|---|---|
| Re-ingest after editing `~/.claude/` content | `make toolkit-reingest` |
| Re-seed the capability graph after agent changes | `make capabilities-reseed` |
| Generate a new Alembic migration | `make migration msg="description"` |
| Apply pending migrations | `make migrate` |
| View backend + worker logs | `make logs-backend` |
| Run pytest | `make test` |
| Tear down + wipe volumes | `make clean` |

## Verifying a clean bootstrap

```bash
docker compose exec -T postgres psql -U cruvai -d cruvai_sn -c \
  "SELECT 'agent_definitions' t, COUNT(*) FROM agent_definitions
   UNION ALL SELECT 'agent_capabilities', COUNT(*) FROM agent_capabilities
   UNION ALL SELECT 'agent_guidance', COUNT(*) FROM agent_guidance
   UNION ALL SELECT 'agent_playbooks', COUNT(*) FROM agent_playbooks
   UNION ALL SELECT 'guidance_assets', COUNT(*) FROM guidance_assets;"
```

Expected counts (approximate; may vary as the toolkit evolves):
- `agent_definitions`: 40
- `agent_capabilities`: 21
- `agent_guidance`: 31
- `agent_playbooks`: 2
- `guidance_assets`: ~361

## Troubleshooting

**`ModuleNotFoundError: No module named 'jinja2'`** — rebuild the backend image so `pyproject.toml` changes land: `docker compose build backend worker && docker compose up -d`.

**Figma 429 for hours** — Org-tier Figma plans have strict per-file API caps. Generate a fresh PAT under Figma → Settings → Security → Personal access tokens, and update the connector credentials.

**Analyzer dispatch fails with `No ServiceNow instance configured`** — open the project Settings and select an instance in the "ServiceNow Instance" dropdown. Required because `AgentJob.instance_id` is non-nullable.

**`direct_invokable` unexpected** — after the toolkit ingest, 32 specialists get `direct_invokable=true`. This is by design; they show up in the story launch dropdown only when `agent_type == 'specialist'` is filtered out client-side.
