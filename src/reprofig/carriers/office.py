"""Office Open XML package parts for PowerPoint, Word, and Excel."""

from __future__ import annotations

import io
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord
from .base import (
    CarrierCapabilities,
    CarrierError,
    CarrierFormatError,
    atomic_write_bytes,
    record_path_tokens,
)
from .manifest import CarrierManifest

CONTENT_TYPES = "http://schemas.openxmlformats.org/package/2006/content-types"
RELATIONSHIPS = "http://schemas.openxmlformats.org/package/2006/relationships"
REL_TYPE = "https://reprofig.org/relationships/manifest"
MANIFEST_PART = "reprofig/manifest.json"
_OFFICE_MARKERS = {
    "pptx": "ppt/presentation.xml",
    "docx": "word/document.xml",
    "xlsx": "xl/workbook.xml",
}
_MIME = {
    "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
}


def _safe_info(name: str, data: bytes) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    return info


def _update_content_types(
    data: bytes, records: Sequence[FigureRecord], tokens: dict[str, str]
) -> bytes:
    ET.register_namespace("", CONTENT_TYPES)
    root = ET.fromstring(data)
    part_name = "/" + MANIFEST_PART
    for child in root:
        if child.attrib.get("PartName") == part_name:
            child.attrib["ContentType"] = "application/vnd.reprofig+json"
            break
    else:
        ET.SubElement(
            root,
            f"{{{CONTENT_TYPES}}}Override",
            PartName=part_name,
            ContentType="application/vnd.reprofig+json",
        )
    existing_parts = {child.attrib.get("PartName") for child in root}
    for record in records:
        record_part = f"/reprofig/{tokens[record.figure_id]}/record.json"
        if record_part not in existing_parts:
            ET.SubElement(
                root,
                f"{{{CONTENT_TYPES}}}Override",
                PartName=record_part,
                ContentType="application/vnd.reprofig.record+json",
            )
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def _update_relationships(data: bytes | None) -> bytes:
    ET.register_namespace("", RELATIONSHIPS)
    root = (
        ET.fromstring(data)
        if data
        else ET.Element(f"{{{RELATIONSHIPS}}}Relationships")
    )
    used = {child.attrib.get("Id") for child in root}
    existing = None
    for child in root:
        if child.attrib.get("Type") == REL_TYPE:
            existing = child
            break
    if existing is None:
        index = 1
        while f"rIdReproFig{index}" in used:
            index += 1
        existing = ET.SubElement(root, f"{{{RELATIONSHIPS}}}Relationship")
        existing.attrib["Id"] = f"rIdReproFig{index}"
    existing.attrib["Type"] = REL_TYPE
    existing.attrib["Target"] = MANIFEST_PART
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


class OfficeAdapter:
    def __init__(self, format: str) -> None:
        self.format = format
        self.capabilities = CarrierCapabilities(
            format=format,
            extensions=(f".{format}",),
            mime_types=(_MIME[format],),
            notes="Macro-enabled Office variants are deliberately rejected.",
        )

    def detect(self, prefix: bytes, path: Path) -> bool:
        if not prefix.startswith(b"PK"):
            return False
        try:
            with zipfile.ZipFile(path) as archive:
                return _OFFICE_MARKERS[self.format] in archive.namelist()
        except (OSError, zipfile.BadZipFile):
            return False

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
        if source.suffix.lower() in {".pptm", ".docm", ".xlsm"}:
            raise CarrierError("macro-enabled Office files are not modified")
        try:
            with zipfile.ZipFile(source) as archive:
                names = archive.namelist()
                if len(names) != len(set(names)):
                    raise CarrierError("Office package contains duplicate ZIP members")
                if _OFFICE_MARKERS[self.format] not in names:
                    raise CarrierFormatError(f"file is not {self.format.upper()}")
                signed = any(
                    name.lower().startswith("_xmlsignatures/")
                    or name.lower().endswith("origin.sigs")
                    for name in names
                )
                if signed and not bool((options or {}).get("allow_invalidate_signature")):
                    raise CarrierError(
                        "Office package has a digital signature; pass "
                        "options={'allow_invalidate_signature': True} to invalidate it explicitly"
                    )
                tokens = record_path_tokens(records)
                content_types = _update_content_types(
                    archive.read("[Content_Types].xml"), records, tokens
                )
                rels = _update_relationships(
                    archive.read("_rels/.rels") if "_rels/.rels" in names else None
                )
                for entry in manifest.records:
                    entry.record_path = f"reprofig/{tokens[entry.figure_id]}/record.json"
                output = io.BytesIO()
                with zipfile.ZipFile(output, "w") as destination:
                    for info in archive.infolist():
                        if info.filename in {MANIFEST_PART, "[Content_Types].xml", "_rels/.rels"}:
                            continue
                        if info.filename.startswith("reprofig/"):
                            continue
                        destination.writestr(info, archive.read(info.filename))
                    destination.writestr(_safe_info("[Content_Types].xml", content_types), content_types)
                    destination.writestr(_safe_info("_rels/.rels", rels), rels)
                    manifest_bytes = manifest.to_json().encode("utf-8")
                    destination.writestr(_safe_info(MANIFEST_PART, manifest_bytes), manifest_bytes)
                    for record in records:
                        value = record.to_json().encode("utf-8")
                        destination.writestr(
                            _safe_info(
                                f"reprofig/{tokens[record.figure_id]}/record.json", value
                            ),
                            value,
                        )
        except zipfile.BadZipFile as exc:
            raise CarrierFormatError("Office package ZIP is invalid") from exc
        atomic_write_bytes(target, output.getvalue())
        return target

    def extract(
        self,
        source: Path,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> tuple[list[FigureRecord], CarrierManifest]:
        try:
            with zipfile.ZipFile(source) as archive:
                if len(archive.namelist()) != len(set(archive.namelist())):
                    raise CarrierError("Office package contains duplicate ZIP members")
                if _OFFICE_MARKERS[self.format] not in archive.namelist():
                    raise CarrierFormatError(f"file is not {self.format.upper()}")
                try:
                    info = archive.getinfo(MANIFEST_PART)
                except KeyError as exc:
                    raise CarrierError(
                        f"{self.format.upper()} has no embedded ReproFig manifest"
                    ) from exc
                if info.file_size > max_decompressed or info.compress_size > max_compressed:
                    raise CarrierError("Office ReproFig manifest exceeds size limit")
                manifest = CarrierManifest.from_json(archive.read(info))
        except zipfile.BadZipFile as exc:
            raise CarrierFormatError("Office package ZIP is invalid") from exc
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest


PptxAdapter = lambda: OfficeAdapter("pptx")
DocxAdapter = lambda: OfficeAdapter("docx")
XlsxAdapter = lambda: OfficeAdapter("xlsx")
