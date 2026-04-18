"""Toolkit ingestion pipeline — loads ~/.claude/ content into the control plane.

Entrypoint:
    python -m app.ingestion.toolkit_ingest --root ~/.claude [--org-id NULL] [--dry-run]

Phases:
    1. Walk  — discover skills/agents/playbooks on disk
    2. Parse — extract frontmatter + body (+ tables for playbooks)
    3. Resolve — map tool names, detect licenses, order by dependency
    4. Write — idempotent upserts with content-hash checks
"""

from app.ingestion.toolkit_ingest.runner import run_ingestion

__all__ = ["run_ingestion"]
