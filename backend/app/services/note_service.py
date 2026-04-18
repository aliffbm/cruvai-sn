"""Story Note service — append-only audit trail writers.

Used by API route handlers (PATCH /stories), agent runners (build_outcome),
and the Analysis Service (analysis_update).
"""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.models.story_analysis import StoryNote


TRACKED_STORY_FIELDS = (
    "title",
    "description",
    "acceptance_criteria",
    "priority",
    "status",
    "figma_file_url",
    "figma_node_id",
    "tags",
)


def compute_story_diff(before: Any, after: Any) -> dict[str, dict[str, Any]]:
    """Return a {field: {before, after}} dict for tracked fields that changed."""
    diff: dict[str, dict[str, Any]] = {}
    for field in TRACKED_STORY_FIELDS:
        b = getattr(before, field, None)
        a = getattr(after, field, None)
        if b != a:
            diff[field] = {"before": b, "after": a}
    return diff


def summarize_diff(diff: dict[str, dict[str, Any]]) -> str:
    """Human-readable one-line summary of a field diff."""
    if not diff:
        return "No tracked fields changed"
    parts = []
    for field, change in diff.items():
        parts.append(f"{field} updated")
    return "; ".join(parts)


class NoteService:
    """Centralizes note writes so auto-writers and manual writes go through one path."""

    # ------------------------------------------------------------------
    # Sync writers (for Celery worker code path)
    # ------------------------------------------------------------------

    def write_sync(
        self,
        db: Session,
        *,
        story_id: uuid.UUID,
        organization_id: uuid.UUID,
        note_type: str,
        content: str,
        diff: dict | None = None,
        related_id: uuid.UUID | None = None,
        author_user_id: uuid.UUID | None = None,
        author_agent_slug: str | None = None,
        author_job_id: uuid.UUID | None = None,
    ) -> StoryNote:
        row = StoryNote(
            story_id=story_id,
            organization_id=organization_id,
            note_type=note_type,
            content=content,
            diff=diff,
            related_id=related_id,
            author_user_id=author_user_id,
            author_agent_slug=author_agent_slug,
            author_job_id=author_job_id,
        )
        db.add(row)
        db.flush()
        return row

    # ------------------------------------------------------------------
    # Async writers (for API routes)
    # ------------------------------------------------------------------

    async def write(
        self,
        db: AsyncSession,
        *,
        story_id: uuid.UUID,
        organization_id: uuid.UUID,
        note_type: str,
        content: str,
        diff: dict | None = None,
        related_id: uuid.UUID | None = None,
        author_user_id: uuid.UUID | None = None,
        author_agent_slug: str | None = None,
        author_job_id: uuid.UUID | None = None,
    ) -> StoryNote:
        row = StoryNote(
            story_id=story_id,
            organization_id=organization_id,
            note_type=note_type,
            content=content,
            diff=diff,
            related_id=related_id,
            author_user_id=author_user_id,
            author_agent_slug=author_agent_slug,
            author_job_id=author_job_id,
        )
        db.add(row)
        await db.flush()
        return row

    async def list_for_story(
        self, db: AsyncSession, story_id: uuid.UUID, limit: int = 200
    ) -> list[StoryNote]:
        result = await db.execute(
            select(StoryNote)
            .where(StoryNote.story_id == story_id)
            .order_by(StoryNote.created_at.desc())
            .limit(limit)
        )
        return list(result.scalars().all())


note_service = NoteService()
