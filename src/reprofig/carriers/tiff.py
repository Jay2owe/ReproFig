"""TIFF private-tag carrier preserving encoded strips and tiles."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord
from .base import CarrierCapabilities, CarrierError, CarrierFormatError, MissingDependencyError
from .manifest import CarrierManifest
from .payload import decode_bytes, encode_bytes

TAG = 700
NS = b"https://reprofig.org/ns/carrier/1"
_DESCRIPTION = re.compile(
    br"<rdf:Description\b[^>]*xmlns:reprofig=[\"']https://reprofig\.org/ns/carrier/1[\"'][^>]*>.*?</rdf:Description\s*>",
    flags=re.DOTALL,
)
_PAYLOAD = re.compile(br"<reprofig:payload>([A-Za-z0-9+/=\s]+)</reprofig:payload>")


def _tifftools():
    try:
        import tifftools
    except ImportError as exc:
        raise MissingDependencyError("TIFF support requires 'pip install reprofig[tiff]'") from exc
    return tifftools


class TiffAdapter:
    capabilities = CarrierCapabilities(
        format="tiff",
        extensions=(".tif", ".tiff"),
        mime_types=("image/tiff",),
        optional_dependency="tifftools",
        notes="Uses standard XMP TIFF tag 700 and preserves encoded strips/tiles.",
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        return prefix.startswith((b"II*\x00", b"MM\x00*", b"II+\x00", b"MM\x00+"))

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
        tifftools = _tifftools()
        try:
            info = tifftools.read_tiff(source)
        except Exception as exc:
            raise CarrierFormatError("TIFF structure is invalid") from exc
        if not info.get("ifds"):
            raise CarrierFormatError("TIFF has no image file directories")
        payload = encode_bytes(manifest.to_json().encode("utf-8")).encode("ascii")
        description = (
            b'<rdf:Description rdf:about="" xmlns:reprofig="https://reprofig.org/ns/carrier/1">'
            b"<reprofig:payload>" + payload + b"</reprofig:payload></rdf:Description>"
        )
        existing_tag = info["ifds"][0]["tags"].get(TAG)
        if existing_tag:
            existing_data = existing_tag.get("data")
            if isinstance(existing_data, list):
                existing_xmp = bytes(existing_data).rstrip(b"\0")
            elif isinstance(existing_data, str):
                existing_xmp = existing_data.encode("utf-8")
            else:
                existing_xmp = bytes(existing_data or b"").rstrip(b"\0")
            cleaned = _DESCRIPTION.sub(b"", existing_xmp)
            closing = cleaned.rfind(b"</rdf:RDF>")
            if closing < 0:
                raise CarrierError("existing TIFF XMP cannot be safely extended")
            value = cleaned[:closing] + description + cleaned[closing:]
        else:
            value = (
                b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
                b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
                + description
                + b"</rdf:RDF></x:xmpmeta>"
            )
        info["ifds"][0]["tags"][TAG] = {
            "datatype": int(tifftools.Datatype.BYTE),
            "count": len(value),
            "data": list(value),
        }
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.", suffix=".tif"
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        temporary.unlink()
        try:
            tifftools.write_tiff(info, temporary)
            os.replace(temporary, target)
        finally:
            try:
                temporary.unlink()
            except OSError:
                pass
        return target

    def extract(
        self,
        source: Path,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> tuple[list[FigureRecord], CarrierManifest]:
        tifftools = _tifftools()
        try:
            info = tifftools.read_tiff(source)
            tag = info["ifds"][0]["tags"][TAG]
        except KeyError as exc:
            raise CarrierError("TIFF has no embedded ReproFig tag") from exc
        except Exception as exc:
            raise CarrierFormatError("TIFF structure is invalid") from exc
        value = tag.get("data")
        if isinstance(value, list):
            value = bytes(value).rstrip(b"\0")
        elif isinstance(value, str):
            value = value.encode("utf-8")
        else:
            value = bytes(value or b"").rstrip(b"\0")
        match = _PAYLOAD.search(value)
        if not match or NS not in value:
            raise CarrierError("TIFF XMP has no embedded ReproFig payload")
        manifest = CarrierManifest.from_json(
            decode_bytes(
                match.group(1).decode("ascii"),
                max_compressed=max_compressed,
                max_decompressed=max_decompressed,
            )
        )
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest
