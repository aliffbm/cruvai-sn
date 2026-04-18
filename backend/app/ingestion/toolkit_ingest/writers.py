"""Idempotent DB writers for the toolkit ingestion pipeline.

All writers are sync (use sync SQLAlchemy session). The CLI creates a
ToolkitIngestionRun row, runs writers, then finalizes the run row.
"""

from __future__ import annotations

import mimetypes
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.ingestion.toolkit_ingest.parsers import (
    ParsedAgent, ParsedPlaybook, ParsedSkill,
)
from app.models.agent import AgentDefinition
from app.models.control_plane import (
    AgentGuidance, AgentGuidanceLabel, AgentGuidanceVersion,
    AgentPlaybook, AgentPlaybookLabel, AgentPlaybookRoute, AgentPlaybookVersion,
    GuidanceAsset, ToolkitIngestionRun,
)
from app.services.storage.base import (
    StorageBackend, content_addressed_key, sha256_bytes,
)

if TYPE_CHECKING:  # pragma: no cover
    pass


# ---------------------------------------------------------------------------
# Run stats
# ---------------------------------------------------------------------------


@dataclass
class IngestionStats:
    guidance_created: int = 0
    guidance_updated: int = 0
    guidance_unchanged: int = 0
    guidance_new_versions: int = 0
    guidance_orphaned: int = 0
    agents_created: int = 0
    agents_updated: int = 0
    agents_unchanged: int = 0
    playbooks_created: int = 0
    playbooks_updated: int = 0
    playbooks_unchanged: int = 0
    playbooks_new_versions: int = 0
    assets_uploaded: int = 0
    assets_reused: int = 0
    license_rewrites_pending: int = 0
    errors: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "guidance": {
                "created": self.guidance_created,
                "updated": self.guidance_updated,
                "unchanged": self.guidance_unchanged,
                "new_versions": self.guidance_new_versions,
                "orphaned": self.guidance_orphaned,
            },
            "agents": {
                "created": self.agents_created,
                "updated": self.agents_updated,
                "unchanged": self.agents_unchanged,
            },
            "playbooks": {
                "created": self.playbooks_created,
                "updated": self.playbooks_updated,
                "unchanged": self.playbooks_unchanged,
                "new_versions": self.playbooks_new_versions,
            },
            "assets": {
                "uploaded": self.assets_uploaded,
                "reused": self.assets_reused,
            },
            "license_rewrites_pending": self.license_rewrites_pending,
            "errors": self.errors,
        }


# ---------------------------------------------------------------------------
# Guidance writer
# ---------------------------------------------------------------------------


def upsert_guidance(
    db: Session,
    parsed: ParsedSkill,
    *,
    storage: StorageBackend,
    toolkit_root: Path,
    organization_id: uuid.UUID | None,
    stats: IngestionStats,
    dry_run: bool = False,
) -> AgentGuidance | None:
    """Upsert a single ParsedSkill into AgentGuidance + version + assets.

    Returns the AgentGuidance row (or None in dry-run mode).

    Idempotency:
      - If an active guidance with (org_id, slug) exists and latest version's
        content_hash matches, nothing changes.
      - If content differs, a new version is inserted; labels are NOT auto-promoted.
    """

    guidance = db.execute(
        select(AgentGuidance).where(
            AgentGuidance.organization_id.is_(organization_id) if organization_id is None
            else AgentGuidance.organization_id == organization_id,
            AgentGuidance.slug == parsed.slug,
        )
    ).scalar_one_or_none()

    if dry_run:
        return None

    created = False
    if guidance is None:
        guidance = AgentGuidance(
            organization_id=organization_id,
            slug=parsed.slug,
            name=parsed.name,
            description=parsed.description,
            guidance_type="procedural",
            agent_types=None,
            tags=list(parsed.frontmatter.get("tags") or []),
            source_uri=parsed.source_uri,
            source_origin="anthropic-toolkit",
            requires_rewrite=parsed.requires_rewrite,
            license_type=parsed.license_type,
            original_license_text=parsed.license_text,
            is_system=(organization_id is None),
            is_active=True,
            is_orphaned=False,
        )
        db.add(guidance)
        db.flush()
        created = True
        stats.guidance_created += 1
        if parsed.requires_rewrite:
            stats.license_rewrites_pending += 1
    else:
        # Update descriptive fields, but preserve governance decisions already made.
        dirty = False
        if guidance.name != parsed.name:
            guidance.name = parsed.name
            dirty = True
        if guidance.description != parsed.description:
            guidance.description = parsed.description
            dirty = True
        if guidance.source_uri != parsed.source_uri:
            guidance.source_uri = parsed.source_uri
            dirty = True
        # License can appear or change across upstream updates
        if guidance.license_type != parsed.license_type:
            guidance.license_type = parsed.license_type
            guidance.requires_rewrite = parsed.requires_rewrite
            if parsed.requires_rewrite:
                stats.license_rewrites_pending += 1
            dirty = True
        if parsed.license_text and guidance.original_license_text != parsed.license_text:
            guidance.original_license_text = parsed.license_text
            dirty = True
        if guidance.is_orphaned:
            guidance.is_orphaned = False
            dirty = True
        if dirty:
            stats.guidance_updated += 1

    # Find latest version for this guidance
    latest_version = db.execute(
        select(AgentGuidanceVersion)
        .where(AgentGuidanceVersion.guidance_id == guidance.id)
        .order_by(AgentGuidanceVersion.version_number.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest_version is not None and latest_version.content_hash == parsed.content_hash:
        if not created:
            stats.guidance_unchanged += 1
        # Still ensure assets exist for this version; skipping for now — re-upload only on version change
        return guidance

    next_version_number = 1 if latest_version is None else latest_version.version_number + 1
    new_version = AgentGuidanceVersion(
        guidance_id=guidance.id,
        version_number=next_version_number,
        content=parsed.body,
        content_hash=parsed.content_hash,
        frontmatter=parsed.frontmatter or None,
        sections=parsed.sections or None,
        asset_manifest=None,  # filled after asset upload
        authorship="anthropic-toolkit",
        derived_from_version_id=None,
        change_notes=f"Ingested from {parsed.source_uri}",
    )
    db.add(new_version)
    db.flush()
    if not created:
        stats.guidance_new_versions += 1

    # Upload assets and build manifest
    manifest: list[dict[str, object]] = []
    for asset_path in parsed.asset_paths:
        try:
            data = asset_path.read_bytes()
        except OSError as exc:
            stats.errors.append(f"Read asset failed {asset_path}: {exc}")
            continue
        asset_sha = sha256_bytes(data)
        rel = str(asset_path.relative_to(toolkit_root))
        key = content_addressed_key(asset_sha, original_path=str(asset_path))
        ctype, _ = mimetypes.guess_type(str(asset_path))
        try:
            already = storage.exists(key)
        except Exception:  # noqa: BLE001 - backend-specific errors
            already = False
        if not already:
            storage.put(key, data, content_type=ctype)
            stats.assets_uploaded += 1
        else:
            stats.assets_reused += 1
        asset_row = GuidanceAsset(
            guidance_version_id=new_version.id,
            relative_path=rel,
            content_type=ctype,
            size_bytes=len(data),
            sha256=asset_sha,
            storage_backend=storage.backend_name,
            object_key=key,
            is_text=_looks_like_text(ctype),
        )
        db.add(asset_row)
        manifest.append({
            "path": rel,
            "sha256": asset_sha,
            "size": len(data),
            "object_key": key,
            "content_type": ctype,
        })
    new_version.asset_manifest = manifest or None

    # On first version (created), seed a staging label; NEVER auto-promote to production.
    if latest_version is None:
        db.add(AgentGuidanceLabel(
            guidance_id=guidance.id,
            version_id=new_version.id,
            label="staging",
            traffic_weight=100,
            is_active=True,
            activated_at=datetime.now(timezone.utc),
        ))

    return guidance


def _looks_like_text(ctype: str | None) -> bool:
    if not ctype:
        return False
    if ctype.startswith("text/"):
        return True
    return ctype in {"application/json", "application/yaml", "application/xml"}


# ---------------------------------------------------------------------------
# Agent writer
# ---------------------------------------------------------------------------


def upsert_agent(
    db: Session,
    parsed: ParsedAgent,
    *,
    stats: IngestionStats,
    dry_run: bool = False,
) -> AgentDefinition | None:
    """Upsert a specialist agent into AgentDefinition.

    Specialists are global (no org scoping on AgentDefinition).
    Sets `direct_invokable=True` so users can assign them to stories.
    The body prompt itself is NOT stored on AgentDefinition — it becomes
    an AgentPrompt via the prompt-ingestion path (separate concern).
    """

    existing = db.execute(
        select(AgentDefinition).where(AgentDefinition.slug == parsed.slug)
    ).scalar_one_or_none()

    if dry_run:
        return None

    if existing is None:
        row = AgentDefinition(
            name=parsed.name,
            slug=parsed.slug,
            description=parsed.description,
            agent_type="specialist",
            system_prompt_version="1.0.0",
            available_tools=parsed.tools or [],
            default_model=(parsed.model or "claude-sonnet-4-20250514"),
            max_steps=50,
            requires_approval=False,
            is_active=True,
            direct_invokable=True,
        )
        db.add(row)
        db.flush()
        stats.agents_created += 1
        return row

    # Update mutable metadata. Leave system_prompt_version alone to preserve governance.
    dirty = False
    if existing.name != parsed.name:
        existing.name = parsed.name
        dirty = True
    if existing.description != parsed.description:
        existing.description = parsed.description
        dirty = True
    if parsed.tools and existing.available_tools != parsed.tools:
        existing.available_tools = parsed.tools
        dirty = True
    if parsed.model and existing.default_model != parsed.model:
        existing.default_model = parsed.model
        dirty = True
    if dirty:
        stats.agents_updated += 1
    else:
        stats.agents_unchanged += 1
    return existing


# ---------------------------------------------------------------------------
# Playbook writer
# ---------------------------------------------------------------------------


def upsert_playbook(
    db: Session,
    parsed: ParsedPlaybook,
    *,
    organization_id: uuid.UUID | None,
    stats: IngestionStats,
    dry_run: bool = False,
) -> AgentPlaybook | None:
    """Upsert a playbook + its version + routes. Returns the playbook."""

    existing = db.execute(
        select(AgentPlaybook).where(
            AgentPlaybook.organization_id.is_(None) if organization_id is None
            else AgentPlaybook.organization_id == organization_id,
            AgentPlaybook.slug == parsed.slug,
        )
    ).scalar_one_or_none()

    if dry_run:
        return None

    created = False
    if existing is None:
        existing = AgentPlaybook(
            organization_id=organization_id,
            slug=parsed.slug,
            name=parsed.name,
            description=parsed.description,
            source_uri=parsed.source_uri,
            source_origin="anthropic-toolkit",
            is_system=(organization_id is None),
            is_active=True,
            is_orphaned=False,
        )
        db.add(existing)
        db.flush()
        stats.playbooks_created += 1
        created = True
    else:
        dirty = False
        if existing.name != parsed.name:
            existing.name = parsed.name
            dirty = True
        if existing.description != parsed.description:
            existing.description = parsed.description
            dirty = True
        if existing.source_uri != parsed.source_uri:
            existing.source_uri = parsed.source_uri
            dirty = True
        if existing.is_orphaned:
            existing.is_orphaned = False
            dirty = True
        if dirty:
            stats.playbooks_updated += 1

    latest_version = db.execute(
        select(AgentPlaybookVersion)
        .where(AgentPlaybookVersion.playbook_id == existing.id)
        .order_by(AgentPlaybookVersion.version_number.desc())
        .limit(1)
    ).scalar_one_or_none()

    if latest_version is not None and latest_version.content_hash == parsed.content_hash:
        if not created:
            stats.playbooks_unchanged += 1
        return existing

    next_version_number = 1 if latest_version is None else latest_version.version_number + 1
    new_version = AgentPlaybookVersion(
        playbook_id=existing.id,
        version_number=next_version_number,
        content=parsed.body,
        content_hash=parsed.content_hash,
        stack_manifest=parsed.stack_manifest or None,
        load_bearing_skills=parsed.load_bearing_skills or [],
        change_notes=f"Ingested from {parsed.source_uri}",
    )
    db.add(new_version)
    db.flush()
    if not created:
        stats.playbooks_new_versions += 1

    if latest_version is None:
        db.add(AgentPlaybookLabel(
            playbook_id=existing.id,
            version_id=new_version.id,
            label="staging",
            traffic_weight=100,
            is_active=True,
            activated_at=datetime.now(timezone.utc),
        ))

    # Build routes from the routing rows — priority = table order.
    # Wipe and rebuild routes for this playbook on each ingest to keep them in sync.
    # (Routes reference live agent IDs; we re-resolve per-run.)
    db.query(AgentPlaybookRoute).filter(AgentPlaybookRoute.playbook_id == existing.id).delete()
    for idx, row in enumerate(parsed.agent_routing_rows):
        primary_slug = _find_agent_slug_in_row(row, "primary")
        supporting_slugs = _find_agent_slugs_in_row(row, "supporting")
        task_pattern = _find_task_pattern(row)
        primary_id = _resolve_agent_id(db, primary_slug) if primary_slug else None
        supporting_ids = [str(_resolve_agent_id(db, s)) for s in supporting_slugs if _resolve_agent_id(db, s)]
        db.add(AgentPlaybookRoute(
            playbook_id=existing.id,
            task_pattern=task_pattern or "*",
            match_type="keywords",
            primary_agent_id=primary_id,
            supporting_agent_ids=supporting_ids or [],
            required_guidance_ids=[],
            priority=100 + idx,
            is_active=True,
        ))

    return existing


_AGENT_SLUG_BY_ROW_KEY_HINTS = ("primary agent", "primary", "lead agent", "owner")


def _find_task_pattern(row: dict[str, str]) -> str | None:
    for key, value in row.items():
        kl = key.lower().strip()
        if kl in {"task", "task pattern", "trigger", "when", "pattern"}:
            return value
    # Fall back to the first column
    for value in row.values():
        return value
    return None


def _find_agent_slug_in_row(row: dict[str, str], role: str) -> str | None:
    role_l = role.lower()
    for key, value in row.items():
        kl = key.lower().strip()
        if role_l == "primary" and any(h in kl for h in _AGENT_SLUG_BY_ROW_KEY_HINTS):
            return _first_backtick_slug(value) or _slugify(value)
        if role_l == "supporting" and "support" in kl:
            return _first_backtick_slug(value) or _slugify(value)
    return None


def _find_agent_slugs_in_row(row: dict[str, str], role: str) -> list[str]:
    role_l = role.lower()
    for key, value in row.items():
        kl = key.lower().strip()
        if role_l == "supporting" and "support" in kl:
            return _all_backtick_slugs(value)
    return []


def _first_backtick_slug(text: str) -> str | None:
    import re

    m = re.search(r"`([a-z][a-z0-9-]+)`", text or "")
    return m.group(1) if m else None


def _all_backtick_slugs(text: str) -> list[str]:
    import re

    return re.findall(r"`([a-z][a-z0-9-]+)`", text or "")


def _slugify(text: str) -> str | None:
    if not text:
        return None
    cleaned = text.strip().lower().replace(" ", "-")
    # strip trailing punctuation
    return cleaned.strip("-") or None


def _resolve_agent_id(db: Session, slug: str | None) -> uuid.UUID | None:
    if not slug:
        return None
    row = db.execute(
        select(AgentDefinition.id).where(AgentDefinition.slug == slug)
    ).scalar_one_or_none()
    return row


# ---------------------------------------------------------------------------
# Orphan detection
# ---------------------------------------------------------------------------


def mark_orphans(
    db: Session,
    *,
    seen_guidance_uris: set[str],
    seen_playbook_uris: set[str],
    stats: IngestionStats,
    dry_run: bool = False,
) -> None:
    """Flag toolkit-origin rows not encountered this run as orphaned."""

    if dry_run:
        return

    for g in db.execute(
        select(AgentGuidance).where(
            AgentGuidance.source_origin == "anthropic-toolkit",
            AgentGuidance.is_active.is_(True),
            AgentGuidance.is_orphaned.is_(False),
        )
    ).scalars():
        if g.source_uri and g.source_uri not in seen_guidance_uris:
            g.is_orphaned = True
            stats.guidance_orphaned += 1

    for pb in db.execute(
        select(AgentPlaybook).where(
            AgentPlaybook.source_origin == "anthropic-toolkit",
            AgentPlaybook.is_active.is_(True),
            AgentPlaybook.is_orphaned.is_(False),
        )
    ).scalars():
        if pb.source_uri and pb.source_uri not in seen_playbook_uris:
            pb.is_orphaned = True


# ---------------------------------------------------------------------------
# Ingestion run bookkeeping
# ---------------------------------------------------------------------------


def start_run(
    db: Session,
    *,
    source_root: str,
    triggered_by_id: uuid.UUID | None,
) -> ToolkitIngestionRun:
    run = ToolkitIngestionRun(
        source_root=source_root,
        triggered_by_id=triggered_by_id,
        status="running",
    )
    db.add(run)
    db.flush()
    return run


def finish_run(
    db: Session,
    run: ToolkitIngestionRun,
    *,
    status: str,
    stats: IngestionStats,
    error_log: str | None = None,
) -> None:
    run.finished_at = datetime.now(timezone.utc)
    run.status = status
    run.stats = stats.as_dict()
    if error_log:
        run.error_log = error_log
