"""MinIO / S3-compatible storage backend."""

from __future__ import annotations

import io
import mimetypes
from datetime import timedelta
from typing import TYPE_CHECKING

from app.services.storage.base import StorageBackend, StorageStat

if TYPE_CHECKING:  # pragma: no cover - import only for type checkers
    from minio import Minio


class MinIOBackend:
    """S3-compatible backend backed by MinIO/AWS S3.

    Requires the `minio` package. Bucket must exist or be creatable by the
    configured credentials.
    """

    backend_name = "minio"

    def __init__(
        self,
        endpoint: str,
        access_key: str,
        secret_key: str,
        bucket: str,
        secure: bool = True,
    ):
        # Lazy import so the package is only required when this backend is selected
        from minio import Minio  # type: ignore[import-not-found]

        self._client: "Minio" = Minio(
            endpoint=endpoint,
            access_key=access_key,
            secret_key=secret_key,
            secure=secure,
        )
        self._bucket = bucket
        self._ensure_bucket()

    def _ensure_bucket(self) -> None:
        if not self._client.bucket_exists(self._bucket):
            self._client.make_bucket(self._bucket)

    # ---- protocol implementation ----------------------------------------

    def put(self, key: str, data: bytes, content_type: str | None = None) -> str:
        if content_type is None:
            content_type, _ = mimetypes.guess_type(key)
            content_type = content_type or "application/octet-stream"
        self._client.put_object(
            bucket_name=self._bucket,
            object_name=key,
            data=io.BytesIO(data),
            length=len(data),
            content_type=content_type,
        )
        return key

    def get(self, key: str) -> bytes:
        response = self._client.get_object(self._bucket, key)
        try:
            return response.read()
        finally:
            response.close()
            response.release_conn()

    def exists(self, key: str) -> bool:
        try:
            self._client.stat_object(self._bucket, key)
            return True
        except Exception:  # noqa: BLE001 - MinIO raises several types
            return False

    def delete(self, key: str) -> None:
        self._client.remove_object(self._bucket, key)

    def stat(self, key: str) -> StorageStat:
        obj = self._client.stat_object(self._bucket, key)
        return StorageStat(
            key=key,
            size_bytes=int(obj.size or 0),
            content_type=obj.content_type,
            sha256=None,  # SHA is not a stored attribute; compute at ingest
            etag=obj.etag,
        )

    def presigned_url(self, key: str, ttl_seconds: int = 300) -> str:
        return self._client.presigned_get_object(
            self._bucket, key, expires=timedelta(seconds=ttl_seconds)
        )
