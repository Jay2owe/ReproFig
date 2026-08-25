"""Embed and recover records without reserializing visible SVG content."""

from __future__ import annotations

import base64
import gzip
import html
import io
import json
import os
import re
import tempfile
import warnings
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from .schema import FigureRecord

NAMESPACE = "https://reprofig.org/ns/figure-record/1"
LEGACY_NAMESPACES = frozenset(
    {
        "https://figure-artifact.org/ns/figure-record/1",
        "https://metafig.org/ns/figure-record/1",
    }
)
ELEMENT = "figure-record"
DEFAULT_MAX_COMPRESSED = 64 * 1024 * 1024
DEFAULT_MAX_DECOMPRESSED = 512 * 1024 * 1024
DEFAULT_WARN_COMPRESSED = 8 * 1024 * 1024
DEFAULT_WARN_UNCOMPRESSED = 64 * 1024 * 1024

_RECORD_NODE = re.compile(
    r"<(?:[A-Za-z_][\w.-]*:)?figure-record\b[^>]*>.*?"
    r"</(?:[A-Za-z_][\w.-]*:)?figure-record\s*>",
    flags=re.DOTALL,
)
_METADATA_CLOSE = re.compile(r"</(?:[A-Za-z_][\w.-]*:)?metadata\s*>", re.IGNORECASE)
_SVG_OPEN = re.compile(r"<(?:[A-Za-z_][\w.-]*:)?svg\b[^>]*>", re.IGNORECASE | re.DOTALL)


class FigureRecordError(ValueError):
    """Raised when an embedded record is absent, corrupt, or unsafe to decode."""


def encode_record(
    record: FigureRecord,
    *,
    warn_compressed: int | None = DEFAULT_WARN_COMPRESSED,
    warn_uncompressed: int | None = DEFAULT_WARN_UNCOMPRESSED,
) -> str:
    raw = record.to_json().encode("utf-8")
    compressed = gzip.compress(raw, compresslevel=9, mtime=0)
    if warn_uncompressed is not None and len(raw) > int(warn_uncompressed):
        warnings.warn(
            f"figure record is {len(raw):,} uncompressed bytes",
            RuntimeWarning,
            stacklevel=2,
        )
    if warn_compressed is not None and len(compressed) > int(warn_compressed):
        warnings.warn(
            f"figure record is {len(compressed):,} compressed bytes",
            RuntimeWarning,
            stacklevel=2,
        )
    return base64.b64encode(compressed).decode("ascii")


def _decode_payload(
    payload: str,
    *,
    max_compressed: int = DEFAULT_MAX_COMPRESSED,
    max_decompressed: int = DEFAULT_MAX_DECOMPRESSED,
) -> FigureRecord:
    compact = "".join(payload.split())
    if len(compact) > ((max_compressed + 2) // 3) * 4 + 8:
        raise FigureRecordError("embedded record exceeds compressed-size limit")
    try:
        compressed = base64.b64decode(compact, validate=True)
    except Exception as exc:
        raise FigureRecordError("embedded record is not valid Base64") from exc
    if len(compressed) > max_compressed:
        raise FigureRecordError("embedded record exceeds compressed-size limit")
    try:
        with gzip.GzipFile(fileobj=io.BytesIO(compressed), mode="rb") as stream:
            raw = stream.read(max_decompressed + 1)
    except (OSError, EOFError) as exc:
        raise FigureRecordError("embedded record is not valid gzip data") from exc
    if len(raw) > max_decompressed:
        raise FigureRecordError("embedded record exceeds decompressed-size limit")
    try:
        return FigureRecord.from_json(raw)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
        raise FigureRecordError("embedded figure record JSON is invalid") from exc


def _record_node(
    record: FigureRecord,
    *,
    warn_compressed: int | None,
    warn_uncompressed: int | None,
) -> str:
    return (
        f'<fig:{ELEMENT} xmlns:fig="{NAMESPACE}" '
        f'schema="{record.schema}" encoding="gzip+base64">'
        f"{encode_record(record, warn_compressed=warn_compressed, warn_uncompressed=warn_uncompressed)}"
        f"</fig:{ELEMENT}>"
    )


def _atomic_write(path: Path, contents: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as stream:
            stream.write(contents)
        os.replace(temporary, path)
    except Exception:
        try:
            os.unlink(temporary)
        except OSError:
            pass
        raise


def embed_record(
    svg_path: str | os.PathLike[str],
    record: FigureRecord,
    *,
    output_path: str | os.PathLike[str] | None = None,
    warn_compressed: int | None = DEFAULT_WARN_COMPRESSED,
    warn_uncompressed: int | None = DEFAULT_WARN_UNCOMPRESSED,
) -> Path:
    """Add or replace one record while preserving all other SVG text verbatim."""

    source = Path(svg_path)
    target = Path(output_path) if output_path is not None else source
    text = source.read_text(encoding="utf-8-sig")
    node = _record_node(
        record,
        warn_compressed=warn_compressed,
        warn_uncompressed=warn_uncompressed,
    )
    match = _RECORD_NODE.search(text)
    if match:
        updated = text[: match.start()] + node + text[match.end() :]
    else:
        metadata_matches = list(_METADATA_CLOSE.finditer(text))
        if metadata_matches:
            close = metadata_matches[0]
            updated = text[: close.start()] + "\n  " + node + "\n" + text[close.start() :]
        else:
            opened = _SVG_OPEN.search(text)
            if not opened:
                raise FigureRecordError("file does not contain an SVG root element")
            metadata = f"\n<metadata>\n  {node}\n</metadata>"
            opened_text = opened.group(0)
            if opened_text.rstrip().endswith("/>"):
                name_match = re.match(r"<\s*([A-Za-z_][\w.:-]*)", opened_text)
                if name_match is None:
                    raise FigureRecordError("SVG root element name is invalid")
                expanded = re.sub(r"/\s*>$", ">", opened_text)
                updated = (
                    text[: opened.start()]
                    + expanded
                    + metadata
                    + f"\n</{name_match.group(1)}>"
                    + text[opened.end() :]
                )
            else:
                updated = text[: opened.end()] + metadata + text[opened.end() :]
    _atomic_write(target, updated)
    return target


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1]


def extract_record(
    svg_path: str | os.PathLike[str],
    *,
    max_compressed: int = DEFAULT_MAX_COMPRESSED,
    max_decompressed: int = DEFAULT_MAX_DECOMPRESSED,
) -> FigureRecord:
    """Extract a complete ReproFig record from anywhere in an SVG."""

    path = Path(svg_path)
    prefix = path.read_bytes()[:4096].upper()
    # Matplotlib emits the standard SVG 1.1 external DOCTYPE. ElementTree does
    # not fetch that external subset, so it is safe to accept; custom entity
    # declarations and internal subsets are rejected.
    if b"<!ENTITY" in prefix or re.search(br"<!DOCTYPE[^>]*\[", prefix):
        raise FigureRecordError("custom DTD entity declarations are not accepted")
    found: FigureRecord | None = None
    try:
        for _event, element in ET.iterparse(path, events=("end",)):
            if _local_name(element.tag) != ELEMENT:
                continue
            if element.tag.startswith("{"):
                namespace = element.tag[1:].split("}", 1)[0]
                if namespace not in {NAMESPACE, *LEGACY_NAMESPACES}:
                    continue
            encoding = element.attrib.get("encoding", "")
            if encoding != "gzip+base64":
                raise FigureRecordError(f"unsupported embedded encoding {encoding!r}")
            record = _decode_payload(
                element.text or "",
                max_compressed=max_compressed,
                max_decompressed=max_decompressed,
            )
            declared = element.attrib.get("schema")
            if declared and declared != record.schema:
                raise FigureRecordError("embedded schema attribute disagrees with payload")
            if found is not None:
                raise FigureRecordError("SVG contains multiple ReproFig records")
            found = record
    except ET.ParseError as exc:
        raise FigureRecordError("SVG XML is not well formed") from exc
    if found is not None:
        return found
    raise FigureRecordError("SVG has no embedded ReproFig record")


def try_extract_record(svg_path: str | os.PathLike[str]) -> FigureRecord | None:
    try:
        return extract_record(svg_path)
    except (OSError, FigureRecordError):
        return None


def legacy_dublin_core_record(svg_path: str | os.PathLike[str]) -> dict[str, Any] | None:
    """Read older JSON stored in a Dublin Core description, if present."""

    try:
        for _event, element in ET.iterparse(svg_path, events=("end",)):
            if _local_name(element.tag) != "description" or not element.text:
                continue
            try:
                value = json.loads(html.unescape(element.text))
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(value, dict):
                return value
    except (OSError, ET.ParseError):
        return None
    return None


def replace_dublin_core_description(svg_path: str | os.PathLike[str], value: dict[str, Any]) -> None:
    """Replace legacy Matplotlib description text without touching the full XML tree."""

    path = Path(svg_path)
    text = path.read_text(encoding="utf-8-sig")
    encoded = html.escape(json.dumps(value, ensure_ascii=False, sort_keys=True), quote=False)
    pattern = re.compile(
        r"(<(?:[A-Za-z_][\w.-]*:)?description\b[^>]*>).*?"
        r"(</(?:[A-Za-z_][\w.-]*:)?description\s*>)",
        re.DOTALL | re.IGNORECASE,
    )
    if pattern.search(text):
        text = pattern.sub(lambda match: match.group(1) + encoded + match.group(2), text, count=1)
        _atomic_write(path, text)
