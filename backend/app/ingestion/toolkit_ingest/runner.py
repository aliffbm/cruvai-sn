"""Top-level ingestion runner — orchestrates walker → parsers → writers."""

from __future__ import annotations

import logging
import traceback
import uuid
from pathlib import Path

from sqlalchemy.orm import Session

from app.ingestion.toolkit_ingest import parsers, walker, writers
from app.services.storage.base import StorageBackend

logger = logging.getLogger(__name__)


def run_ingestion(
    db: Session,
    *,
    toolkit_root: Path,
    storage: StorageBackend,
    organization_id: uuid.UUID | None = None,
    triggered_by_id: uuid.UUID | None = None,
    dry_run: bool = False,
) -> writers.IngestionStats:
    """Run the full ingestion pipeline.

    Phases:
      1. Walk the filesystem.
      2. Parse agents first (so playbook routes can resolve agent slugs).
      3. Parse + write guidance (skills).
      4. Parse + write playbooks (needs agents).
      5. Mark orphans and finalize the ingestion run.
    """

    stats = writers.IngestionStats()
    run = None
    if not dry_run:
        run = writers.start_run(
            db,
            source_root=str(toolkit_root),
            triggered_by_id=triggered_by_id,
        )

    seen_guidance_uris: set[str] = set()
    seen_playbook_uris: set[str] = set()

    try:
        paths = walker.discover(toolkit_root)
        logger.info(
            "Toolkit discovery: %d skills, %d agents, %d playbooks",
            len(paths.skill_md_paths), len(paths.agent_md_paths), len(paths.playbook_md_paths),
        )

        # Phase 1: agents (no dependencies)
        for agent_path in paths.agent_md_paths:
            try:
                parsed_agent = parsers.parse_agent(agent_path, toolkit_root)
                writers.upsert_agent(db, parsed_agent, stats=stats, dry_run=dry_run)
            except Exception as exc:  # noqa: BLE001 - capture, continue
                stats.errors.append(f"agent {agent_path.name}: {exc}")
                logger.exception("Failed to ingest agent %s", agent_path)

        if not dry_run:
            db.flush()

        # Phase 2: guidance (skills)
        for skill_md in paths.skill_md_paths:
            try:
                parsed_skill = parsers.parse_skill(skill_md, toolkit_root)
                seen_guidance_uris.add(parsed_skill.source_uri)
                writers.upsert_guidance(
                    db,
                    parsed_skill,
                    storage=storage,
                    toolkit_root=toolkit_root,
                    organization_id=organization_id,
                    stats=stats,
                    dry_run=dry_run,
                )
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"skill {skill_md.parent.name}: {exc}")
                logger.exception("Failed to ingest skill %s", skill_md)

        if not dry_run:
            db.flush()

        # Phase 3: playbooks (needs agents + guidance)
        for playbook_path in paths.playbook_md_paths:
            try:
                parsed_pb = parsers.parse_playbook(playbook_path, toolkit_root)
                seen_playbook_uris.add(parsed_pb.source_uri)
                writers.upsert_playbook(
                    db,
                    parsed_pb,
                    organization_id=organization_id,
                    stats=stats,
                    dry_run=dry_run,
                )
            except Exception as exc:  # noqa: BLE001
                stats.errors.append(f"playbook {playbook_path.name}: {exc}")
                logger.exception("Failed to ingest playbook %s", playbook_path)

        if not dry_run:
            writers.mark_orphans(
                db,
                seen_guidance_uris=seen_guidance_uris,
                seen_playbook_uris=seen_playbook_uris,
                stats=stats,
                dry_run=dry_run,
            )

        if not dry_run and run is not None:
            status = "succeeded" if not stats.errors else "partial"
            writers.finish_run(db, run, status=status, stats=stats)
            db.commit()

    except Exception as exc:  # noqa: BLE001 - catastrophic failure
        if not dry_run and run is not None:
            writers.finish_run(
                db,
                run,
                status="failed",
                stats=stats,
                error_log=f"{exc}\n{traceback.format_exc()}",
            )
            db.commit()
        raise

    return stats
