"""Scalable Vector Graphics adapter preserving the established ReproFig format."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord
from ..svg import embed_record, extract_record
from .base import CarrierCapabilities, CarrierError
from .manifest import CarrierManifest


class SvgAdapter:
    capabilities = CarrierCapabilities(
        format="svg",
        extensions=(".svg",),
        mime_types=("image/svg+xml",),
        multiple_records=False,
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        cleaned = prefix.lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
        return cleaned.startswith(b"<?xml") and b"<svg" in cleaned or cleaned.startswith(b"<svg")

    def embed(
        self,
        source: Path,
        target: Path,
        records: Sequence[FigureRecord],
        *,
        manifest: CarrierManifest,
        allow_reencode: bool = False,
        options: dict[str, Any] | None = None,
    ) -> Path:
        if len(records) != 1:
            raise CarrierError("SVG supports one ReproFig record per file")
        return embed_record(source, records[0], output_path=target)

    def extract(
        self,
        source: Path,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> tuple[list[FigureRecord], CarrierManifest]:
        record = extract_record(
            source,
            max_compressed=max_compressed,
            max_decompressed=max_decompressed,
        )
        manifest = CarrierManifest.for_records(
            "svg", [record], media_type="image/svg+xml"
        )
        return [record], manifest
