"""Explicit recovery of a companion proof bundle for stripped artifacts."""

from __future__ import annotations

import os
import shutil
import tempfile
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from .registry import LocalRegistry, RegistryEntry

MAX_RECOVERY_BYTES = 2 * 1024 * 1024 * 1024


@dataclass(frozen=True)
class RecoveryResult:
    stripped_path: Path
    recovered_path: Path
    figure_id: str
    evidence_root: str
    confidence: str


def recover_companion(
    stripped_path: str | os.PathLike[str],
    registry: LocalRegistry,
    output_path: str | os.PathLike[str],
    *,
    trust_store: str | os.PathLike[str] | object,
    overwrite: bool = False,
) -> RecoveryResult:
    resolved = registry.resolve(stripped_path, trust_store=trust_store)
    if resolved is None:
        raise LookupError("no trusted identity-registry entry matches the artifact")
    entry, confidence = resolved
    if not entry.recovery_locations:
        raise LookupError("matching registry entry has no recovery location")
    target = Path(output_path)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
    )
    os.close(descriptor)
    candidate = Path(temporary_name)
    location = entry.recovery_locations[0]
    parsed = urlparse(location)
    try:
        if parsed.scheme == "https":
            with urllib.request.urlopen(location, timeout=20) as response:
                data = response.read(MAX_RECOVERY_BYTES + 1)
            if len(data) > MAX_RECOVERY_BYTES:
                raise ValueError("recovered companion exceeds ReproFig size limit")
            candidate.write_bytes(data)
        elif parsed.scheme:
            raise ValueError(f"unsupported recovery URI scheme {parsed.scheme!r}")
        else:
            base = registry.source_path.parent if registry.source_path else Path.cwd()
            source = (base / location).resolve(strict=True)
            if base.resolve() not in source.parents:
                raise ValueError("relative recovery location escapes the registry folder")
            if source.stat().st_size > MAX_RECOVERY_BYTES:
                raise ValueError("recovered companion exceeds ReproFig size limit")
            shutil.copyfile(source, candidate, follow_symlinks=False)

        from .artifacts import extract_records, validate_artifact
        from .evidence import graph_from_record

        validation = validate_artifact(candidate)
        if not validation.valid:
            raise ValueError("recovered companion failed carrier-integrity validation")
        matching = [
            record
            for record in extract_records(candidate)
            if record.figure_id == entry.figure_id
            and graph_from_record(record).root_sha256 == entry.evidence_root
        ]
        if not matching:
            raise ValueError("recovered companion does not match the trusted registry identity")
        os.replace(candidate, target)
    finally:
        try:
            candidate.unlink()
        except OSError:
            pass
    return RecoveryResult(
        Path(stripped_path), target, entry.figure_id, entry.evidence_root, confidence
    )


__all__ = ["RecoveryResult", "recover_companion"]
