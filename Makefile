.PHONY: up down build logs migrate seed test clean

# Start all services
up:
	docker compose up -d

# Stop all services
down:
	docker compose down

# Build images
build:
	docker compose build

# View logs
logs:
	docker compose logs -f

# Backend logs only
logs-backend:
	docker compose logs -f backend worker

# Run database migrations
migrate:
	docker compose exec backend alembic upgrade head

# Generate a new migration
migration:
	docker compose exec backend alembic revision --autogenerate -m "$(msg)"

# Seed database with initial data
seed:
	docker compose exec backend python -m app.seed

# Run backend tests
test:
	docker compose exec backend pytest -v

# Run frontend dev server locally (outside Docker)
dev-frontend:
	cd frontend && npm run dev

# Run backend dev server locally (outside Docker)
dev-backend:
	cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Install frontend dependencies
install-frontend:
	cd frontend && npm install

# Install backend dependencies
install-backend:
	cd backend && pip install -e ".[dev]"

# Clean up volumes and containers
clean:
	docker compose down -v --remove-orphans

# -----------------------------------------------------------------------------
# Bootstrap — cold-start a brand-new environment to the canonical state
# -----------------------------------------------------------------------------
# Runs: schema → core seed → toolkit sync → toolkit ingest → capability seed.
# Idempotent: safe to re-run; only writes new content.
#
# Requires: Docker, the AI Knowledge Repository toolkit installed at ~/.claude
# (see ~/.claude/GLOBAL_MANIFEST.md or https://github.com/aliffbm/AI-Knowledge-Repository).
# -----------------------------------------------------------------------------
bootstrap: up
	@echo "==> Waiting for backend to be healthy..."
	@sleep 3
	@echo "==> Applying Alembic migrations..."
	docker compose exec -T backend alembic upgrade head
	@echo "==> Seeding roles, agent definitions, OOB prompts, OOB skills..."
	docker compose exec -T backend python -m app.seed
	@echo "==> Syncing toolkit from $$HOME/.claude into backend container..."
	$(MAKE) toolkit-sync
	@echo "==> Ingesting toolkit (31 skills + 32 agents + 2 playbooks + assets)..."
	docker compose exec -T backend python -m app.ingestion.toolkit_ingest --root /toolkit
	@echo "==> Seeding default delegation graph (AgentCapability rows)..."
	docker compose exec -T backend python -m app.ingestion.toolkit_ingest.seed_capabilities
	@echo ""
	@echo "==> Bootstrap complete."
	@echo "    UI:  http://localhost:3001"
	@echo "    API: http://localhost:8001/docs"

# Copy the host's ~/.claude toolkit into the backend container at /toolkit.
# Ephemeral (lost on container rebuild) — re-run `make toolkit-sync` after
# a rebuild, or `make bootstrap` for a full refresh.
toolkit-sync:
	docker cp $$HOME/.claude cruvai-servicenow-backend-1:/toolkit

# Re-run the toolkit ingest without the full bootstrap (e.g. after a local
# tweak to ~/.claude). Idempotent: only creates new versions on changed content.
toolkit-reingest: toolkit-sync
	docker compose exec -T backend python -m app.ingestion.toolkit_ingest --root /toolkit

# Refresh the capability graph after agents change.
capabilities-reseed:
	docker compose exec -T backend python -m app.ingestion.toolkit_ingest.seed_capabilities

# Generate encryption key
gen-key:
	python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
