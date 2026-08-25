"""Shared adapter contracts and safe file operations."""

from __future__ import annotations

import os
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, Sequence

from ..schema import FigureRecord
from ..tables import safe_filename_token
if TYPE_CHECKING:
    from .manifest import CarrierManifest


class CarrierError(ValueError):
    """Base error for unsupported, corrupt, or unsafe carriers."""


class CarrierFormatError(CarrierError):
    """The file is not the declared carrier format."""


class CarrierLimitError(CarrierError):
    """An embedded payload exceeds a configured safety limit."""


class MissingDependencyError(CarrierError):
    """An optional format dependency is not installed."""


@dataclass(frozen=True)
class CarrierCapabilities:
    format: str
    extensions: tuple[str, ...]
    mime_types: tuple[str, ...]
    multiple_records: bool = True
    metadata_only: bool = True
    preserves_encoded_media: bool = True
    supports_render_metadata: bool = True
    optional_dependency: str | None = None
    notes: str | None = None
    storage: str = "inline"
    size_class: str = "metadata"
    supported_profiles: tuple[str, ...] = ("master", "public", "minimal_public")
    metadata_survival: str = "fragile"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CarrierAdapter(Protocol):
    capabilities: CarrierCapabilities

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool: ...

    def embed(
        self,
        source: Path,
        target: Path,
        records: Sequence[FigureRecord],
        *,
        manifest: "CarrierManifest",
        allow_reencode: bool = False,
        options: dict[str, Any] | None = None,
    ) -> Path: ...

    def extract(
        self,
        source: Path,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> tuple[list[FigureRecord], CarrierManifest]: ...


def atomic_write_bytes(path: Path, contents: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(contents)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def record_path_tokens(records: Sequence[FigureRecord]) -> dict[str, str]:
    """Return collision-checked safe carrier path components by figure ID."""

    result = {record.figure_id: safe_filename_token(record.figure_id) for record in records}
    if len(set(result.values())) != len(result):
        raise CarrierError("figure identifiers collide after carrier path sanitization")
    return result
