"""Filesystem storage backend — dev default."""

from __future__ import annotations

import mimetypes
import os
from pathlib import Path

from app.services.storage.base import StorageBackend, StorageStat, sha256_bytes


class FilesystemBackend:
    """Stores objects under a content-addressed directory tree.

    Root defaults to `${STORAGE_ROOT}` (see config). Keys are interpreted as
    relative paths under the root; `content_addressed_key` generates keys of
    the form `ab/cdef...`.
    """

    backend_name = "filesystem"

    def __init__(self, root: str | os.PathLike[str]):
        self._root = Path(root).expanduser().resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    # ---- internal helpers -----------------------------------------------

    def _resolve(self, key: str) -> Path:
        path = (self._root / key).resolve()
        # Defense in depth: reject path traversal outside root
        try:
            path.relative_to(self._root)
        except ValueError as exc:
            raise ValueError(f"Key escapes storage root: {key}") from exc
        return path

    # ---- protocol implementation ----------------------------------------

    def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        target = self._resolve(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Content-addressed: if already present with same bytes, leave alone
        if target.exists():
            existing = target.read_bytes()
            if existing == data:
                return key
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_bytes(data)
        os.replace(tmp, target)
        return key

    def get(self, key: str) -> bytes:
        target = self._resolve(key)
        if not target.exists():
            raise FileNotFoundError(key)
        return target.read_bytes()

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def delete(self, key: str) -> None:
        target = self._resolve(key)
        if target.exists():
            target.unlink()

    def stat(self, key: str) -> StorageStat:
        target = self._resolve(key)
        if not target.exists():
            raise FileNotFoundError(key)
        size = target.stat().st_size
        ctype, _ = mimetypes.guess_type(str(target))
        # For small files, compute hash; skip for very large to stay fast
        sha = None
        if size <= 50 * 1024 * 1024:
            sha = sha256_bytes(target.read_bytes())
        return StorageStat(
            key=key,
            size_bytes=size,
            content_type=ctype,
            sha256=sha,
        )

    def presigned_url(self, key: str, ttl_seconds: int = 300) -> str:
        # Dev-only — returns a file:// URL. Production should use MinIO.
        return self._resolve(key).as_uri()
