"""WebP Resource Interchange File Format XMP carrier."""

from __future__ import annotations

import re
import struct
from pathlib import Path
from typing import Any, Iterator, Sequence

from ..schema import FigureRecord
from .base import CarrierCapabilities, CarrierError, CarrierFormatError, atomic_write_bytes
from .manifest import CarrierManifest
from .payload import decode_bytes, encode_bytes

_PAYLOAD = re.compile(br"<reprofig:payload>([A-Za-z0-9+/=\s]+)</reprofig:payload>")
NS = b"https://reprofig.org/ns/carrier/1"


def _chunks(data: bytes) -> Iterator[tuple[bytes, bytes]]:
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        raise CarrierFormatError("file is not WebP")
    declared = struct.unpack("<I", data[4:8])[0] + 8
    if declared != len(data):
        raise CarrierFormatError("WebP RIFF size is invalid")
    offset = 12
    while offset < len(data):
        if offset + 8 > len(data):
            raise CarrierFormatError("truncated WebP chunk")
        kind = data[offset : offset + 4]
        length = struct.unpack("<I", data[offset + 4 : offset + 8])[0]
        end = offset + 8 + length
        padded = end + (length & 1)
        if padded > len(data):
            raise CarrierFormatError("truncated WebP chunk data")
        yield kind, data[offset + 8 : end]
        offset = padded


def _chunk(kind: bytes, payload: bytes) -> bytes:
    padding = b"\0" if len(payload) & 1 else b""
    return kind + struct.pack("<I", len(payload)) + payload + padding


def _xmp(manifest: CarrierManifest) -> bytes:
    encoded = encode_bytes(manifest.to_json().encode("utf-8")).encode("ascii")
    return (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="" xmlns:reprofig="https://reprofig.org/ns/carrier/1">'
        b"<reprofig:payload>" + encoded + b"</reprofig:payload>"
        b"</rdf:Description></rdf:RDF></x:xmpmeta>"
    )


def _canvas(source: Path) -> tuple[int, int, bool]:
    try:
        from PIL import Image
    except ImportError as exc:
        raise CarrierError("Pillow is required to read a simple WebP canvas") from exc
    with Image.open(source) as image:
        return image.width, image.height, "A" in image.getbands()


class WebpAdapter:
    capabilities = CarrierCapabilities(
        format="webp",
        extensions=(".webp",),
        mime_types=("image/webp",),
        optional_dependency="Pillow (only for simple WebP files without VP8X)",
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        return len(prefix) >= 12 and prefix[:4] == b"RIFF" and prefix[8:12] == b"WEBP"

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
        chunks = list(_chunks(source.read_bytes()))
        has_vp8x = any(kind == b"VP8X" for kind, _payload in chunks)
        if not has_vp8x:
            width, height, alpha = _canvas(source)
            kinds = {kind for kind, _payload in chunks}
            flags = 0x04
            flags |= 0x20 if b"ICCP" in kinds else 0
            flags |= 0x10 if alpha or b"ALPH" in kinds else 0
            flags |= 0x08 if b"EXIF" in kinds else 0
            flags |= 0x02 if b"ANIM" in kinds else 0
            vp8x = bytes([flags, 0, 0, 0]) + (width - 1).to_bytes(3, "little") + (height - 1).to_bytes(3, "little")
            chunks.insert(0, (b"VP8X", vp8x))
        output_chunks = bytearray()
        for kind, payload in chunks:
            if kind == b"XMP " and NS in payload:
                continue
            if kind == b"VP8X":
                if len(payload) != 10:
                    raise CarrierFormatError("WebP VP8X chunk length is invalid")
                payload = bytes([payload[0] | 0x04]) + payload[1:]
            output_chunks.extend(_chunk(kind, payload))
        output_chunks.extend(_chunk(b"XMP ", _xmp(manifest)))
        output = b"RIFF" + struct.pack("<I", len(output_chunks) + 4) + b"WEBP" + output_chunks
        atomic_write_bytes(target, output)
        return target

    def extract(
        self,
        source: Path,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> tuple[list[FigureRecord], CarrierManifest]:
        manifest: CarrierManifest | None = None
        for kind, payload in _chunks(source.read_bytes()):
            if kind != b"XMP " or NS not in payload:
                continue
            if manifest is not None:
                raise CarrierError("WebP contains duplicate ReproFig XMP chunks")
            match = _PAYLOAD.search(payload)
            if not match:
                raise CarrierError("WebP ReproFig XMP payload is missing")
            manifest = CarrierManifest.from_json(
                decode_bytes(
                    match.group(1).decode("ascii"),
                    max_compressed=max_compressed,
                    max_decompressed=max_decompressed,
                )
            )
        if manifest is None:
            raise CarrierError("WebP has no embedded ReproFig XMP")
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest
