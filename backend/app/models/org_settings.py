import uuid

from sqlalchemy import Boolean, ForeignKey, LargeBinary, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class OrgApiKey(TimestampMixin, Base):
    """Encrypted API key storage per organization.

    Each org stores their own LLM provider keys. Keys are Fernet-encrypted
    at rest and never returned in API responses — only a masked preview.
    """
    __tablename__ = "org_api_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    organization_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("organizations.id"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(
        String(50), nullable=False
    )  # anthropic, openai
    label: Mapped[str] = mapped_column(String(100), default="Default")  # user-friendly name
    key_encrypted: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    key_preview: Mapped[str] = mapped_column(String(20), nullable=False)  # "sk-ant-...7xQ2" (masked)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
