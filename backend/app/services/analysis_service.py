"""Analysis Service — persist, approve, and diff StoryAnalysis records.

Works from both sync (worker) and async (API) contexts. Writes audit notes
via NoteService on create/approve/reject.
"""

from __future__ import annotations

import difflib
import hashlib
import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.story_analysis import StoryAnalysis, StoryNote
from app.services.note_service import note_service

logger = logging.getLogger(__name__)


def _hash_analysis(payload: dict[str, Any]) -> str:
    """Deterministic SHA-256 of the analysis content for idempotency checks."""
    canonical = json.dumps(payload, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class AnalysisService:

    # ------------------------------------------------------------------
    # Sync path (worker / analyzer agent runner)
    # ------------------------------------------------------------------

    def create_from_agent_sync(
        self,
        db: Session,
        *,
        story_id: uuid.UUID,
        organization_id: uuid.UUID,
        payload: dict[str, Any],
        authored_by_agent_slug: str,
        authored_by_job_id: uuid.UUID | None,
        authored_by_model: str | None,
    ) -> StoryAnalysis:
        """Persist a new analysis version produced by the analyzer agent.

        Mark any prior approved version as `superseded` and writes a
        `analysis_update` StoryNote. The new row is `draft`; a human still
        has to approve it before the governance gate opens.
        """

        # Next version number
        max_version = db.execute(
            select(func.coalesce(func.max(StoryAnalysis.version_number), 0))
            .where(StoryAnalysis.story_id == story_id)
        ).scalar() or 0

        content_hash = _hash_analysis(payload)

        row = StoryAnalysis(
            story_id=story_id,
            organization_id=organization_id,
            version_number=max_version + 1,
            status="draft",
            content_hash=content_hash,
            summary=payload.get("summary"),
            design_rationale=payload.get("design_rationale"),
            oob_reuse=payload.get("oob_reuse") or [],
            design_patterns_applied=payload.get("design_patterns_applied") or [],
            proposed_artifacts=payload.get("proposed_artifacts") or [],
            acceptance_criteria_mapping=payload.get("acceptance_criteria_mapping") or [],
            specialist_consults=payload.get("specialist_consults") or [],
            applicable_guidance=payload.get("applicable_guidance") or [],
            risks=payload.get("risks") or [],
            dependencies_on_other_stories=payload.get("dependencies_on_other_stories") or [],
            estimated_story_points=payload.get("estimated_story_points"),
            authored_by_agent_slug=authored_by_agent_slug,
            authored_by_job_id=authored_by_job_id,
            authored_by_model=authored_by_model,
        )
        db.add(row)
        db.flush()

        # Supersede any previously-approved versions for this story
        db.execute(
            StoryAnalysis.__table__.update()
            .where(
                StoryAnalysis.story_id == story_id,
                StoryAnalysis.status == "approved",
                StoryAnalysis.id != row.id,
            )
            .values(status="outdated")
        )

        note_service.write_sync(
            db,
            story_id=story_id,
            organization_id=organization_id,
            note_type="analysis_update",
            content=(
                f"New analysis v{row.version_number} produced by "
                f"{authored_by_agent_slug} ({authored_by_model or 'unknown model'}). "
                f"Status: draft — awaiting human approval."
            ),
            related_id=row.id,
            author_agent_slug=authored_by_agent_slug,
            author_job_id=authored_by_job_id,
        )
        return row

    # ------------------------------------------------------------------
    # Async path (API)
    # ------------------------------------------------------------------

    async def list_for_story(
        self, db: AsyncSession, story_id: uuid.UUID
    ) -> list[StoryAnalysis]:
        rows = (
            await db.execute(
                select(StoryAnalysis)
                .where(StoryAnalysis.story_id == story_id)
                .order_by(StoryAnalysis.version_number.desc())
            )
        ).scalars().all()
        return list(rows)

    async def get_latest_for_story(
        self, db: AsyncSession, story_id: uuid.UUID
    ) -> StoryAnalysis | None:
        result = await db.execute(
            select(StoryAnalysis)
            .where(StoryAnalysis.story_id == story_id)
            .order_by(StoryAnalysis.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_approved_for_story(
        self, db: AsyncSession, story_id: uuid.UUID
    ) -> StoryAnalysis | None:
        result = await db.execute(
            select(StoryAnalysis)
            .where(
                StoryAnalysis.story_id == story_id,
                StoryAnalysis.status == "approved",
            )
            .order_by(StoryAnalysis.version_number.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def approve(
        self,
        db: AsyncSession,
        analysis_id: uuid.UUID,
        *,
        reviewer_user_id: uuid.UUID,
    ) -> StoryAnalysis:
        analysis = (
            await db.execute(
                select(StoryAnalysis).where(StoryAnalysis.id == analysis_id)
            )
        ).scalar_one_or_none()
        if analysis is None:
            raise ValueError("Analysis not found")
        if analysis.status == "approved":
            return analysis

        # Demote previously-approved versions for this story to outdated
        await db.execute(
            StoryAnalysis.__table__.update()
            .where(
                StoryAnalysis.story_id == analysis.story_id,
                StoryAnalysis.status == "approved",
                StoryAnalysis.id != analysis.id,
            )
            .values(status="outdated")
        )

        analysis.status = "approved"
        analysis.reviewed_by_id = reviewer_user_id
        analysis.approved_at = datetime.now(timezone.utc)
        await db.flush()

        await note_service.write(
            db,
            story_id=analysis.story_id,
            organization_id=analysis.organization_id,
            note_type="approval",
            content=f"Analysis v{analysis.version_number} approved. Agent launch is now unblocked.",
            related_id=analysis.id,
            author_user_id=reviewer_user_id,
        )
        return analysis

    async def reject(
        self,
        db: AsyncSession,
        analysis_id: uuid.UUID,
        *,
        reviewer_user_id: uuid.UUID,
        reason: str,
    ) -> StoryAnalysis:
        analysis = (
            await db.execute(
                select(StoryAnalysis).where(StoryAnalysis.id == analysis_id)
            )
        ).scalar_one_or_none()
        if analysis is None:
            raise ValueError("Analysis not found")
        analysis.status = "outdated"
        analysis.rejection_reason = reason
        analysis.reviewed_by_id = reviewer_user_id
        await db.flush()
        await note_service.write(
            db,
            story_id=analysis.story_id,
            organization_id=analysis.organization_id,
            note_type="analysis_update",
            content=f"Analysis v{analysis.version_number} rejected: {reason}",
            related_id=analysis.id,
            author_user_id=reviewer_user_id,
        )
        return analysis

    async def diff(
        self,
        db: AsyncSession,
        analysis_id: uuid.UUID,
        against_id: uuid.UUID | None = None,
    ) -> dict[str, Any]:
        a = (
            await db.execute(
                select(StoryAnalysis).where(StoryAnalysis.id == analysis_id)
            )
        ).scalar_one_or_none()
        if a is None:
            raise ValueError("Analysis not found")
        if against_id is None:
            b = (
                await db.execute(
                    select(StoryAnalysis)
                    .where(
                        StoryAnalysis.story_id == a.story_id,
                        StoryAnalysis.version_number < a.version_number,
                    )
                    .order_by(StoryAnalysis.version_number.desc())
                    .limit(1)
                )
            ).scalar_one_or_none()
        else:
            b = (
                await db.execute(
                    select(StoryAnalysis).where(StoryAnalysis.id == against_id)
                )
            ).scalar_one_or_none()
        if b is None:
            return {"a_version": a.version_number, "b_version": None, "diff": ""}

        def flat(an: StoryAnalysis) -> str:
            return json.dumps(
                {
                    "summary": an.summary,
                    "design_rationale": an.design_rationale,
                    "oob_reuse": an.oob_reuse,
                    "design_patterns_applied": an.design_patterns_applied,
                    "proposed_artifacts": an.proposed_artifacts,
                    "acceptance_criteria_mapping": an.acceptance_criteria_mapping,
                    "specialist_consults": an.specialist_consults,
                    "applicable_guidance": an.applicable_guidance,
                    "risks": an.risks,
                },
                indent=2, default=str, sort_keys=True,
            )

        diff_lines = list(
            difflib.unified_diff(
                flat(b).splitlines(),
                flat(a).splitlines(),
                fromfile=f"v{b.version_number}",
                tofile=f"v{a.version_number}",
                lineterm="",
            )
        )
        return {
            "a_version": a.version_number,
            "b_version": b.version_number,
            "diff": "\n".join(diff_lines),
        }


analysis_service = AnalysisService()
