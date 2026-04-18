"""Storage backend protocol and shared helpers."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class StorageStat:
    """Metadata about a stored object."""

    key: str
    size_bytes: int
    content_type: str | None
    sha256: str | None
    etag: str | None = None


@runtime_checkable
class StorageBackend(Protocol):
    """Pluggable storage backend contract.

    Implementations must be safe to use from both sync and async contexts;
    if an implementation is inherently async it should provide sync wrappers
    (the ingestion pipeline runs sync today).
    """

    backend_name: str  # e.g. "filesystem", "minio", "s3"

    def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        """Write `data` under `key`. Returns the resolved storage key."""

    def get(self, key: str) -> bytes:
        """Read the full content at `key`. Raises FileNotFoundError if absent."""

    def exists(self, key: str) -> bool:
        """Return True iff `key` resolves to a stored object."""

    def delete(self, key: str) -> None:
        """Remove the object at `key`. No-op if absent."""

    def stat(self, key: str) -> StorageStat:
        """Return metadata for `key`. Raises FileNotFoundError if absent."""

    def presigned_url(self, key: str, ttl_seconds: int = 300) -> str:
        """Return a time-limited URL for downloading `key`.

        Filesystem backends may return a local file:// URL or a dev proxy URL.
        """


def content_addressed_key(sha256_hex: str, original_path: str | None = None) -> str:
    """Build a content-addressed key like `a3/b7c9...ext`.

    Original extension is preserved when available for content-type inference.
    """

    if len(sha256_hex) < 4:
        raise ValueError("sha256 must be hex string")
    prefix = sha256_hex[:2]
    rest = sha256_hex[2:]
    ext = ""
    if original_path:
        dot = original_path.rfind(".")
        if dot >= 0:
            ext = original_path[dot:].lower()
            # Guard against path traversal inside the extension
            if any(c in ext for c in "/\\"):
                ext = ""
    return f"{prefix}/{rest}{ext}"


def sha256_bytes(data: bytes) -> str:
    """Return hex-encoded SHA-256 of `data`."""

    return hashlib.sha256(data).hexdigest()
