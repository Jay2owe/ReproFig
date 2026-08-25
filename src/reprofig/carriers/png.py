"""Portable Network Graphics iTXt carrier."""

from __future__ import annotations

import struct
import zlib
from pathlib import Path
from typing import Any, Iterator, Sequence

from ..schema import FigureRecord
from .base import CarrierCapabilities, CarrierError, CarrierFormatError, atomic_write_bytes
from .manifest import CarrierManifest

SIGNATURE = b"\x89PNG\r\n\x1a\n"
KEYWORD = b"ReproFig"


def _chunks(data: bytes) -> Iterator[tuple[bytes, bytes, bytes]]:
    if not data.startswith(SIGNATURE):
        raise CarrierFormatError("file is not PNG")
    offset = len(SIGNATURE)
    while offset < len(data):
        if offset + 12 > len(data):
            raise CarrierFormatError("truncated PNG chunk")
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        end = offset + 12 + length
        if end > len(data):
            raise CarrierFormatError("truncated PNG chunk data")
        kind = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        raw = data[offset:end]
        expected = struct.unpack(">I", raw[-4:])[0]
        if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected:
            raise CarrierFormatError(f"PNG {kind.decode('latin1')} checksum is invalid")
        yield kind, payload, raw
        offset = end
        if kind == b"IEND":
            if offset != len(data):
                raise CarrierFormatError("PNG has trailing bytes after IEND")
            return
    raise CarrierFormatError("PNG has no IEND chunk")


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return (
        struct.pack(">I", len(payload))
        + kind
        + payload
        + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)
    )


def _itxt_payload(manifest: CarrierManifest) -> bytes:
    compressed = zlib.compress(manifest.to_json().encode("utf-8"), level=9)
    return KEYWORD + b"\0\x01\x00\0\0" + compressed


def _decode_itxt(value: bytes, *, max_decompressed: int = 512 * 1024 * 1024) -> bytes | None:
    keyword, separator, rest = value.partition(b"\0")
    if not separator or keyword != KEYWORD:
        return None
    if len(rest) < 4:
        raise CarrierError("ReproFig PNG iTXt is truncated")
    flag, method = rest[0], rest[1]
    _language, separator, rest = rest[2:].partition(b"\0")
    if not separator:
        raise CarrierError("ReproFig PNG iTXt language field is truncated")
    _translated, separator, text = rest.partition(b"\0")
    if not separator:
        raise CarrierError("ReproFig PNG iTXt translated field is truncated")
    if flag == 1 and method == 0:
        try:
            decompressor = zlib.decompressobj()
            result = decompressor.decompress(text, max_decompressed + 1)
            if len(result) > max_decompressed or decompressor.unconsumed_tail:
                raise CarrierError("ReproFig PNG manifest exceeds size limit")
            result += decompressor.flush(max_decompressed + 1 - len(result))
            if len(result) > max_decompressed:
                raise CarrierError("ReproFig PNG manifest exceeds size limit")
            return result
        except zlib.error as exc:
            raise CarrierError("ReproFig PNG iTXt is corrupt") from exc
    if flag == 0:
        return text
    raise CarrierError("ReproFig PNG iTXt uses an unsupported compression method")


class PngAdapter:
    capabilities = CarrierCapabilities(
        format="png",
        extensions=(".png",),
        mime_types=("image/png",),
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        return prefix.startswith(SIGNATURE)

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
        output = bytearray(SIGNATURE)
        inserted = False
        for kind, payload, raw in _chunks(source.read_bytes()):
            if kind == b"iTXt" and payload.startswith(KEYWORD + b"\0"):
                continue
            if kind == b"IEND" and not inserted:
                output.extend(_chunk(b"iTXt", _itxt_payload(manifest)))
                inserted = True
            output.extend(raw)
        atomic_write_bytes(target, bytes(output))
        return target

    def extract(
        self,
        source: Path,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> tuple[list[FigureRecord], CarrierManifest]:
        found: CarrierManifest | None = None
        for kind, payload, _raw in _chunks(source.read_bytes()):
            if kind != b"iTXt":
                continue
            value = _decode_itxt(payload, max_decompressed=max_decompressed)
            if value is not None:
                if found is not None:
                    raise CarrierError("PNG contains duplicate ReproFig manifests")
                if len(value) > max_decompressed:
                    raise CarrierError("ReproFig PNG manifest exceeds size limit")
                found = CarrierManifest.from_json(value)
        if found is None:
            raise CarrierError("PNG has no embedded ReproFig manifest")
        return found.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), found
