"""LLM service — resolves API keys from the database per organization."""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.org_settings import OrgApiKey
from app.utils.encryption import decrypt_value


def get_api_key(db: Session, organization_id: uuid.UUID, provider: str = "anthropic") -> str:
    """Get the active API key for a provider from the org's stored keys.

    Falls back to environment variable if no DB key found.
    """
    result = db.execute(
        select(OrgApiKey).where(
            OrgApiKey.organization_id == organization_id,
            OrgApiKey.provider == provider,
            OrgApiKey.is_active.is_(True),
            OrgApiKey.deleted_at.is_(None),
        ).order_by(OrgApiKey.created_at.desc())
    )
    key_record = result.scalar_one_or_none()

    if key_record:
        return decrypt_value(key_record.key_encrypted)

    # Fallback to env var (for backwards compat / self-hosted)
    from app.config import settings
    if provider == "anthropic" and settings.anthropic_api_key:
        return settings.anthropic_api_key
    if provider == "openai" and settings.openai_api_key:
        return settings.openai_api_key

    raise ValueError(
        f"No active {provider} API key found. "
        f"Add one in Settings → LLM API Keys."
    )
