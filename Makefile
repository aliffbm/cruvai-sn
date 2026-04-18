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

# Generate encryption key
gen-key:
	python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
