"""Audit Service — thin wrapper to emit AuditLog rows from services and APIs.

Event types (action strings) for the toolkit work:
  guidance.version.created
  guidance.label.promoted
  guidance.label.promotion_blocked
  capability.added
  capability.updated
  capability.deleted
  playbook.route.created
  playbook.route.updated
  ingestion.run.completed
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from app.models.audit import AuditLog

logger = logging.getLogger(__name__)


class AuditService:
    async def record(
        self,
        db: AsyncSession,
        *,
        organization_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        row = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(row)
        await db.flush()
        return row

    def record_sync(
        self,
        db: Session,
        *,
        organization_id: uuid.UUID,
        action: str,
        resource_type: str,
        resource_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
        details: dict[str, Any] | None = None,
        ip_address: str | None = None,
    ) -> AuditLog:
        row = AuditLog(
            organization_id=organization_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            details=details,
            ip_address=ip_address,
        )
        db.add(row)
        db.flush()
        return row


audit_service = AuditService()
