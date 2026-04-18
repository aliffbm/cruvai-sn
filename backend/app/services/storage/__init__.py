"""Storage backend abstraction for guidance assets.

Provides a pluggable protocol with filesystem (dev) and MinIO (prod)
implementations. Content-addressed keys enable automatic dedup across
guidance versions.
"""

from app.services.storage.base import StorageBackend, StorageStat
from app.services.storage.factory import get_storage_backend

__all__ = ["StorageBackend", "StorageStat", "get_storage_backend"]
