"""Storage backend factory — resolves the configured backend at runtime."""

from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.services.storage.base import StorageBackend


@lru_cache(maxsize=1)
def get_storage_backend() -> StorageBackend:
    """Return the singleton storage backend selected by config.

    Called lazily — importing this module never pays the connection cost.
    """

    backend = settings.storage_backend.lower()

    if backend in ("filesystem", "fs", "local"):
        from app.services.storage.filesystem import FilesystemBackend

        return FilesystemBackend(root=settings.storage_root)

    if backend in ("minio", "s3"):
        from app.services.storage.minio_backend import MinIOBackend

        if not settings.minio_endpoint:
            raise RuntimeError(
                "STORAGE_BACKEND=minio requires MINIO_ENDPOINT to be configured"
            )
        return MinIOBackend(
            endpoint=settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            bucket=settings.minio_bucket,
            secure=settings.minio_secure,
        )

    raise ValueError(f"Unknown STORAGE_BACKEND: {settings.storage_backend}")


def reset_storage_cache() -> None:
    """Reset the cached backend (useful for tests that change config)."""

    get_storage_backend.cache_clear()
