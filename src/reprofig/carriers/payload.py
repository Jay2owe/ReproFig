"""Deterministic and size-bounded record payload encoding."""

from __future__ import annotations

import base64
import gzip
import io
import json
from typing import Any

from ..schema import FigureRecord, deterministic_json
from .base import CarrierError, CarrierLimitError

DEFAULT_MAX_COMPRESSED = 64 * 1024 * 1024
DEFAULT_MAX_DECOMPRESSED = 512 * 1024 * 1024


def gzip_bytes(value: bytes) -> bytes:
    return gzip.compress(value, compresslevel=9, mtime=0)


def gunzip_bytes(
    value: bytes,
    *,
    max_compressed: int = DEFAULT_MAX_COMPRESSED,
    max_decompressed: int = DEFAULT_MAX_DECOMPRESSED,
) -> bytes:
    if len(value) > max_compressed:
        raise CarrierLimitError("embedded payload exceeds compressed-size limit")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(value), mode="rb") as stream:
            raw = stream.read(max_decompressed + 1)
    except (OSError, EOFError) as exc:
        raise CarrierError("embedded payload is not valid gzip data") from exc
    if len(raw) > max_decompressed:
        raise CarrierLimitError("embedded payload exceeds decompressed-size limit")
    return raw


def encode_bytes(value: bytes) -> str:
    return base64.b64encode(gzip_bytes(value)).decode("ascii")


def decode_bytes(
    value: str,
    *,
    max_compressed: int = DEFAULT_MAX_COMPRESSED,
    max_decompressed: int = DEFAULT_MAX_DECOMPRESSED,
) -> bytes:
    compact = "".join(value.split())
    if len(compact) > ((max_compressed + 2) // 3) * 4 + 8:
        raise CarrierLimitError("embedded payload exceeds compressed-size limit")
    try:
        compressed = base64.b64decode(compact, validate=True)
    except Exception as exc:
        raise CarrierError("embedded payload is not valid Base64") from exc
    return gunzip_bytes(
        compressed,
        max_compressed=max_compressed,
        max_decompressed=max_decompressed,
    )


def encode_record(record: FigureRecord) -> str:
    return encode_bytes(record.to_json().encode("utf-8"))


def decode_record(
    value: str,
    *,
    max_compressed: int = DEFAULT_MAX_COMPRESSED,
    max_decompressed: int = DEFAULT_MAX_DECOMPRESSED,
) -> FigureRecord:
    try:
        return FigureRecord.from_json(
            decode_bytes(
                value,
                max_compressed=max_compressed,
                max_decompressed=max_decompressed,
            )
        )
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        if isinstance(exc, CarrierError):
            raise
        raise CarrierError("embedded ReproFig record is invalid") from exc


def encode_json(value: Any) -> bytes:
    return deterministic_json(value).encode("utf-8")
