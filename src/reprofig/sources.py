"""Source fingerprints, relative references, and change detection."""

from __future__ import annotations

import hashlib
import os
from datetime import datetime
from pathlib import Path
from threading import RLock
from typing import Any

from .schema import SourceReference

_CACHE: dict[tuple[str, int, int, int], str] = {}
_CACHE_LOCK = RLock()


def file_sha256(path: str | os.PathLike[str]) -> str:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    key = (
        str(resolved),
        int(stat.st_size),
        int(stat.st_mtime_ns),
        int(stat.st_ctime_ns),
    )
    with _CACHE_LOCK:
        cached = _CACHE.get(key)
    if cached:
        return cached
    digest = hashlib.sha256()
    with resolved.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    value = digest.hexdigest()
    with _CACHE_LOCK:
        _CACHE[key] = value
    return value


def source_reference(
    path: str | os.PathLike[str],
    *,
    role: str = "source",
    project_root: str | os.PathLike[str] | None = None,
    uri: str | None = None,
    source_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> SourceReference:
    resolved = Path(path).resolve()
    stat = resolved.stat()
    relative: str | None = None
    if project_root is not None:
        try:
            relative = resolved.relative_to(Path(project_root).resolve()).as_posix()
        except ValueError:
            relative = resolved.name
    else:
        relative = resolved.name
    return SourceReference(
        role=role,
        relative_path=relative,
        uri=uri,
        sha256=file_sha256(resolved),
        size_bytes=int(stat.st_size),
        modified_at=datetime.fromtimestamp(stat.st_mtime).astimezone().isoformat(timespec="seconds"),
        source_id=source_id,
        metadata=dict(metadata or {}),
    )


def source_status(
    source: SourceReference,
    *,
    project_root: str | os.PathLike[str] | None = None,
) -> str:
    if not source.relative_path:
        return "unresolved"
    candidate = Path(source.relative_path)
    if project_root is not None:
        candidate = Path(project_root) / candidate
    if not candidate.exists():
        return "missing"
    if not source.sha256:
        return "present_unverified"
    try:
        return "unchanged" if file_sha256(candidate) == source.sha256 else "changed"
    except OSError:
        return "unreadable"


def clear_fingerprint_cache() -> None:
    with _CACHE_LOCK:
        _CACHE.clear()
