"""JPEG Adobe Extended XMP carrier that preserves all encoded image scans."""

from __future__ import annotations

import hashlib
import re
import struct
from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord
from .base import CarrierCapabilities, CarrierError, CarrierFormatError, atomic_write_bytes
from .manifest import CarrierManifest
from .payload import decode_bytes, encode_bytes

SOI = b"\xff\xd8"
XMP = b"http://ns.adobe.com/xap/1.0/\x00"
EXT = b"http://ns.adobe.com/xmp/extension/\x00"
NS = b"https://reprofig.org/ns/carrier/1"
_PAYLOAD = re.compile(br"<reprofig:payload>([A-Za-z0-9+/=\s]+)</reprofig:payload>")


def _segments(data: bytes) -> tuple[list[tuple[int, bytes, bytes]], bytes]:
    if not data.startswith(SOI):
        raise CarrierFormatError("file is not JPEG")
    segments: list[tuple[int, bytes, bytes]] = []
    offset = 2
    while offset < len(data):
        if data[offset] != 0xFF:
            raise CarrierFormatError("invalid JPEG marker stream")
        start = offset
        while offset < len(data) and data[offset] == 0xFF:
            offset += 1
        if offset >= len(data):
            raise CarrierFormatError("truncated JPEG marker")
        marker = data[offset]
        offset += 1
        if marker in (0xD9, 0xDA):
            return segments, data[start:]
        if marker == 0x01 or 0xD0 <= marker <= 0xD7:
            segments.append((marker, b"", data[start:offset]))
            continue
        if offset + 2 > len(data):
            raise CarrierFormatError("truncated JPEG segment")
        length = struct.unpack(">H", data[offset : offset + 2])[0]
        if length < 2 or offset + length > len(data):
            raise CarrierFormatError("invalid JPEG segment length")
        payload = data[offset + 2 : offset + length]
        raw = data[start : offset + length]
        segments.append((marker, payload, raw))
        offset += length
    raise CarrierFormatError("JPEG has no scan or end marker")


def _app1(payload: bytes) -> bytes:
    if len(payload) > 65533:
        raise CarrierError("JPEG APP1 segment is too large")
    return b"\xff\xe1" + struct.pack(">H", len(payload) + 2) + payload


def _packets(manifest: CarrierManifest) -> tuple[bytes, list[bytes]]:
    encoded = encode_bytes(manifest.to_json().encode("utf-8"))
    packet = (
        b'<?xpacket begin="\xef\xbb\xbf"?>'
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="" xmlns:reprofig="https://reprofig.org/ns/carrier/1">'
        b"<reprofig:payload>" + encoded.encode("ascii") + b"</reprofig:payload>"
        b"</rdf:Description></rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>"
    )
    guid = hashlib.md5(packet).hexdigest().upper().encode("ascii")
    primary = (
        XMP
        + b'<?xpacket begin="\xef\xbb\xbf"?><x:xmpmeta xmlns:x="adobe:ns:meta/">'
        + b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        + b'<rdf:Description rdf:about="" xmlns:xmpNote="http://ns.adobe.com/xmp/note/" '
        + b'xmlns:reprofig="https://reprofig.org/ns/carrier/1" '
        + b'xmpNote:HasExtendedXMP="' + guid + b'" reprofig:schema="reprofig-carrier/1"/>'
        + b"</rdf:RDF></x:xmpmeta><?xpacket end=\"w\"?>"
    )
    overhead = len(EXT) + 32 + 4 + 4
    chunk_size = 65533 - overhead
    extended = [
        EXT + guid + struct.pack(">II", len(packet), offset) + packet[offset : offset + chunk_size]
        for offset in range(0, len(packet), chunk_size)
    ]
    return primary, extended


def _existing_guid(segments: list[tuple[int, bytes, bytes]]) -> bytes | None:
    found: bytes | None = None
    count = 0
    for marker, payload, _raw in segments:
        if marker == 0xE1 and payload.startswith(XMP) and NS in payload:
            match = re.search(br"HasExtendedXMP=\"([0-9A-Fa-f]{32})\"", payload)
            candidate = match.group(1).upper() if match else None
            count += 1
            if count > 1:
                raise CarrierError("JPEG contains duplicate ReproFig XMP locators")
            found = candidate
    return found


class JpegAdapter:
    capabilities = CarrierCapabilities(
        format="jpeg",
        extensions=(".jpg", ".jpeg", ".jpe"),
        mime_types=("image/jpeg",),
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        return prefix.startswith(SOI)

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
        segments, tail = _segments(source.read_bytes())
        old_guid = _existing_guid(segments)
        primary, extended = _packets(manifest)
        output = bytearray(SOI)
        inserted = False
        for marker, payload, raw in segments:
            is_ours = marker == 0xE1 and payload.startswith(XMP) and NS in payload
            is_old_extension = (
                marker == 0xE1
                and old_guid is not None
                and payload.startswith(EXT + old_guid)
            )
            if is_ours or is_old_extension:
                continue
            output.extend(raw)
            if not inserted and marker in (0xE0, 0xE1):
                output.extend(_app1(primary))
                for part in extended:
                    output.extend(_app1(part))
                inserted = True
        if not inserted:
            output.extend(_app1(primary))
            for part in extended:
                output.extend(_app1(part))
        output.extend(tail)
        atomic_write_bytes(target, bytes(output))
        return target

    def extract(
        self,
        source: Path,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> tuple[list[FigureRecord], CarrierManifest]:
        segments, _tail = _segments(source.read_bytes())
        guid = _existing_guid(segments)
        if guid is None:
            raise CarrierError("JPEG has no embedded ReproFig XMP")
        parts: dict[int, bytes] = {}
        total: int | None = None
        for marker, payload, _raw in segments:
            prefix = EXT + guid
            if marker != 0xE1 or not payload.startswith(prefix):
                continue
            header = len(prefix)
            if len(payload) < header + 8:
                raise CarrierError("truncated ReproFig Extended XMP chunk")
            declared, offset = struct.unpack(">II", payload[header : header + 8])
            if total is not None and declared != total:
                raise CarrierError("Extended XMP length declarations disagree")
            total = declared
            parts[offset] = payload[header + 8 :]
        if total is None:
            raise CarrierError("JPEG ReproFig Extended XMP is missing")
        packet = bytearray()
        for offset in sorted(parts):
            if offset != len(packet):
                raise CarrierError("JPEG ReproFig Extended XMP has a gap")
            packet.extend(parts[offset])
        if len(packet) != total or hashlib.md5(packet).hexdigest().upper().encode("ascii") != guid:
            raise CarrierError("JPEG ReproFig Extended XMP failed integrity validation")
        match = _PAYLOAD.search(bytes(packet))
        if not match:
            raise CarrierError("JPEG ReproFig XMP payload is missing")
        raw = decode_bytes(
            match.group(1).decode("ascii"),
            max_compressed=max_compressed,
            max_decompressed=max_decompressed,
        )
        manifest = CarrierManifest.from_json(raw)
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest
