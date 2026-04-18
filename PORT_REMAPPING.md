# Port Remapping — Cruvai ServiceNow Project

## Why This Was Changed (2026-04-06)

This project's Docker services were remapped to **non-default ports** to allow parallel development with the **Cruvai Platform** project (`C:\Users\david\AI Agent Partner\autonomous-agent\autonomous-agent`), which uses the default ports.

Both projects were conflicting on ports 5432, 6379, 8000, and 3000 — causing one project to fail when the other was running.

## Port Mapping

| Service | Default Port | **This Project (ServiceNow)** | Cruvai Platform |
|---------|-------------|-------------------------------|-----------------|
| PostgreSQL | 5432 | **5433** | 5432 (default) |
| Redis | 6379 | **6380** | 6379 (default) |
| FastAPI Backend | 8000 | **8001** | 8000 (default) |
| Next.js Frontend | 3000 | **3001** | 3000 (default) |

## What This Means

- **Internal container ports are unchanged** — services still communicate on their standard ports inside Docker (postgres:5432, redis:6379, backend:8000). No application code changes needed.
- **External (host) ports are different** — when accessing from your browser or local tools:
  - ServiceNow API: `http://localhost:8001`
  - ServiceNow Frontend: `http://localhost:3001`
  - ServiceNow Postgres (direct): `localhost:5433`
  - ServiceNow Redis (direct): `localhost:6380`

## Frontend Environment Variable

The `NEXT_PUBLIC_API_URL` was updated from `http://localhost:8000` to `http://localhost:8001` so the frontend calls the correct backend port.

The `API_INTERNAL_URL` remains `http://backend:8000` since internal Docker networking is unaffected.

## Running Both Projects Simultaneously

```bash
# Start Cruvai Platform (uses default ports)
cd "C:\Users\david\AI Agent Partner\autonomous-agent\autonomous-agent"
docker compose up -d

# Start ServiceNow project (uses remapped ports)
cd "C:\Users\david\ServicenowWorkspace\cruvai-servicenow"
docker compose up -d

# Both run side by side — no conflicts
```

## If You Need to Revert

Change the ports back in `docker-compose.yml`:
- `5433:5432` → `5432:5432`
- `6380:6379` → `6379:6379`
- `8001:8000` → `8000:8000`
- `3001:3000` → `3000:3000`
- `NEXT_PUBLIC_API_URL` → `http://localhost:8000`

But then only one project can run at a time.
