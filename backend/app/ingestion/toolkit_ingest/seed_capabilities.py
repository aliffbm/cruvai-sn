"""Seed default delegation graph for primary SN agents → toolkit specialists.

Run after a live toolkit ingest has populated the 32 specialist
AgentDefinitions. Idempotent: skips pairs that already exist.

Usage:
    python -m app.ingestion.toolkit_ingest.seed_capabilities
"""

from __future__ import annotations

import logging
import sys
from dataclasses import dataclass

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.config import settings
from app.models.agent import AgentDefinition
from app.models.control_plane import AgentCapability

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class DelegationDefault:
    primary_slug: str
    specialist_slug: str
    context: str
    keywords: tuple[str, ...]
    priority: int = 100


# Primary agents in Cruvai today: catalog, portal, atf, integration,
# documentation, cmdb, code_review, update_set.
# Specialists below ship in ~/.claude/agents/ and are ingested as
# AgentDefinition(agent_type='specialist', direct_invokable=True).
DEFAULTS: list[DelegationDefault] = [
    # Portal agent — frontend-heavy work
    DelegationDefault(
        "portal", "react-specialist",
        "Advanced React/widget UX work, state management, performance optimization.",
        ("widget", "react", "spa", "state"),
        priority=100,
    ),
    DelegationDefault(
        "portal", "ui-designer",
        "Visual design, layout, accessibility, design-system alignment.",
        ("ui", "design", "layout", "accessibility", "figma"),
        priority=110,
    ),
    DelegationDefault(
        "portal", "frontend-developer",
        "General frontend implementation across React/Angular/Vue.",
        ("frontend", "angular", "form", "component"),
        priority=120,
    ),
    DelegationDefault(
        "portal", "security-auditor",
        "Security review before exposing portal pages publicly.",
        ("public", "anonymous", "external", "auth"),
        priority=130,
    ),
    DelegationDefault(
        "portal", "ux-researcher",
        "Usability concerns, information architecture, user-journey mapping.",
        ("usability", "journey", "research"),
        priority=140,
    ),

    # Catalog agent — backend + API-heavy work
    DelegationDefault(
        "catalog", "backend-developer",
        "Server-side logic, business rules, workflow integration.",
        ("backend", "api", "business rule"),
        priority=100,
    ),
    DelegationDefault(
        "catalog", "api-designer",
        "REST/SOAP endpoint design, variable contract, integration contracts.",
        ("api", "rest", "endpoint", "contract"),
        priority=110,
    ),
    DelegationDefault(
        "catalog", "database-optimizer",
        "Table design, query performance, indexing.",
        ("table", "query", "index", "performance"),
        priority=120,
    ),
    DelegationDefault(
        "catalog", "security-auditor",
        "Access control, ACL review, sensitive variable handling.",
        ("acl", "security", "permission", "credential"),
        priority=130,
    ),

    # ATF (Automated Test Framework)
    DelegationDefault(
        "atf", "qa-expert",
        "Test strategy, coverage matrix, quality metrics.",
        ("test", "coverage", "quality", "regression"),
        priority=100,
    ),
    DelegationDefault(
        "atf", "test-automator",
        "Authoring automated test scripts, CI integration.",
        ("automation", "test script", "ci"),
        priority=110,
    ),

    # CMDB
    DelegationDefault(
        "cmdb", "database-optimizer",
        "CI class design, relationship tables, reconciliation performance.",
        ("ci", "relationship", "class", "reconciliation"),
        priority=100,
    ),
    DelegationDefault(
        "cmdb", "postgres-pro",
        "Deep database internals when Cruvai's own side tables need tuning.",
        ("postgres", "index", "explain"),
        priority=110,
    ),

    # Integration
    DelegationDefault(
        "integration", "api-designer",
        "External API integration contracts, payload shapes, auth flows.",
        ("integration", "api", "webhook", "oauth"),
        priority=100,
    ),
    DelegationDefault(
        "integration", "backend-developer",
        "Implementation of the server-side integration.",
        ("implementation", "server"),
        priority=110,
    ),
    DelegationDefault(
        "integration", "security-auditor",
        "Review credential handling and data exposure across the integration.",
        ("credential", "secret", "oauth", "token"),
        priority=120,
    ),

    # Documentation
    DelegationDefault(
        "documentation", "technical-writer",
        "User-facing docs, API references, SDK guides.",
        ("docs", "documentation", "guide", "reference"),
        priority=100,
    ),

    # Code review
    DelegationDefault(
        "code_review", "code-reviewer",
        "Deep code review pass following repository conventions.",
        ("review", "refactor", "style"),
        priority=100,
    ),
    DelegationDefault(
        "code_review", "security-auditor",
        "Security-focused review layer.",
        ("security", "vulnerability", "owasp"),
        priority=110,
    ),
    DelegationDefault(
        "code_review", "qa-expert",
        "Testability and coverage review layer.",
        ("test", "coverage"),
        priority=120,
    ),

    # Update set
    DelegationDefault(
        "update_set", "devops-engineer",
        "Deployment pipelines, promotion strategy, release gates.",
        ("deploy", "pipeline", "promote"),
        priority=100,
    ),
]


def seed(db: Session, *, dry_run: bool = False) -> dict[str, int]:
    """Insert missing default AgentCapability rows. Returns stats."""

    # Resolve primaries by agent_type (Cruvai convention: agent_type=portal
    # → slug=portal-agent). Specialists are looked up by slug.
    primary_id_by_type: dict[str, object] = {}
    for agent_type in {d.primary_slug for d in DEFAULTS}:
        row = db.execute(
            select(AgentDefinition.id).where(
                AgentDefinition.agent_type == agent_type,
                AgentDefinition.is_active.is_(True),
            )
        ).scalar_one_or_none()
        if row is not None:
            primary_id_by_type[agent_type] = row

    specialist_id_by_slug: dict[str, object] = {}
    for slug in {d.specialist_slug for d in DEFAULTS}:
        row = db.execute(
            select(AgentDefinition.id).where(AgentDefinition.slug == slug)
        ).scalar_one_or_none()
        if row is not None:
            specialist_id_by_slug[slug] = row

    created = 0
    skipped_existing = 0
    skipped_missing_agent = 0

    for default in DEFAULTS:
        p_id = primary_id_by_type.get(default.primary_slug)
        s_id = specialist_id_by_slug.get(default.specialist_slug)
        if p_id is None or s_id is None:
            skipped_missing_agent += 1
            logger.info(
                "skip %s->%s: agent not in DB yet",
                default.primary_slug, default.specialist_slug,
            )
            continue

        existing = db.execute(
            select(AgentCapability.id).where(
                AgentCapability.primary_agent_id == p_id,
                AgentCapability.specialist_agent_id == s_id,
            )
        ).scalar_one_or_none()
        if existing is not None:
            skipped_existing += 1
            continue

        if not dry_run:
            db.add(AgentCapability(
                primary_agent_id=p_id,
                specialist_agent_id=s_id,
                delegation_context=default.context,
                trigger_keywords=list(default.keywords),
                invocation_mode="sub_agent",
                priority=default.priority,
                requires_approval=False,
                is_active=True,
            ))
        created += 1

    if not dry_run:
        db.commit()

    stats = {
        "created": created,
        "skipped_existing": skipped_existing,
        "skipped_missing_agent": skipped_missing_agent,
        "dry_run": 1 if dry_run else 0,
    }
    logger.info("Capability seed: %s", stats)
    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    dry_run = "--dry-run" in sys.argv
    engine = create_engine(settings.database_url_sync, future=True)
    with Session(engine, expire_on_commit=False) as db:
        stats = seed(db, dry_run=dry_run)
    print(stats)
    return 0


if __name__ == "__main__":
    sys.exit(main())
