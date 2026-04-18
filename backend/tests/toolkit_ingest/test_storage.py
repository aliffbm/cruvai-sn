"""Tests for the storage backend abstraction."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.services.storage.base import content_addressed_key, sha256_bytes
from app.services.storage.filesystem import FilesystemBackend


def test_content_addressed_key_splits_prefix():
    sha = "abc123def4567890" + "0" * 48  # 64 chars
    key = content_addressed_key(sha, original_path="icon.png")
    assert key.startswith("ab/")
    assert key.endswith(".png")
    assert sha[2:] in key


def test_content_addressed_key_rejects_short():
    with pytest.raises(ValueError):
        content_addressed_key("abc")


def test_sha256_deterministic():
    assert sha256_bytes(b"hello") == sha256_bytes(b"hello")
    assert sha256_bytes(b"hello") != sha256_bytes(b"world")


def test_filesystem_roundtrip(tmp_path: Path):
    backend = FilesystemBackend(tmp_path)
    data = b"toolkit test payload"
    sha = sha256_bytes(data)
    key = content_addressed_key(sha, original_path="foo.txt")

    # Idempotent put
    backend.put(key, data, content_type="text/plain")
    backend.put(key, data, content_type="text/plain")  # should not raise or corrupt

    assert backend.exists(key)
    assert backend.get(key) == data

    stat = backend.stat(key)
    assert stat.size_bytes == len(data)
    assert stat.sha256 == sha
    assert stat.content_type == "text/plain"


def test_filesystem_rejects_escape(tmp_path: Path):
    backend = FilesystemBackend(tmp_path)
    with pytest.raises(ValueError):
        backend.put("../evil.txt", b"x")
