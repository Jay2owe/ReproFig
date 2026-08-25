"""Deterministic ZIP/RO-Crate carrier."""

from __future__ import annotations

import io
import posixpath
import stat
import zipfile
from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord, deterministic_json, sha256_bytes
from ..tables import safe_filename_token, statistics_csv_bytes
from .base import (
    CarrierCapabilities,
    CarrierError,
    CarrierFormatError,
    atomic_write_bytes,
    record_path_tokens,
)
from .manifest import CarrierManifest

MANIFEST = "manifest.json"
LEGACY_MANIFEST = "reprofig/manifest.json"
ROCRATE = "ro-crate-metadata.json"
CHECKSUMS = "checksums.sha256"
MAX_BUNDLE_UNCOMPRESSED = 2 * 1024 * 1024 * 1024
MAX_COMPRESSION_RATIO = 1000


def _valid_member(name: str) -> bool:
    normalized = posixpath.normpath(name.replace("\\", "/"))
    return not (
        normalized.startswith("../")
        or normalized.startswith("/")
        or ":" in normalized.split("/", 1)[0]
    )


def _info(name: str) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    return info


def _rocrate(
    records: Sequence[FigureRecord],
    manifest: CarrierManifest,
    tokens: dict[str, str],
) -> bytes:
    graph: list[dict[str, Any]] = [
        {
            "@id": "ro-crate-metadata.json",
            "@type": "CreativeWork",
            "about": {"@id": "./"},
            "conformsTo": {"@id": "https://w3id.org/ro/crate/1.2"},
        },
        {
            "@id": "./",
            "@type": "Dataset",
            "name": "ReproFig reproducible figure bundle",
            "hasPart": [
                {"@id": f"records/{tokens[record.figure_id]}/record.json"}
                for record in records
            ],
        },
    ]
    for record in records:
        graph.append(
            {
                "@id": f"records/{tokens[record.figure_id]}/record.json",
                "@type": "File",
                "encodingFormat": "application/vnd.reprofig+json",
                "name": record.title or record.figure_id,
                "sha256": record.fingerprint(),
            }
        )
    return deterministic_json(
        {"@context": "https://w3id.org/ro/crate/1.2/context", "@graph": graph}, indent=2
    ).encode("utf-8")


class BundleAdapter:
    capabilities = CarrierCapabilities(
        format="zip",
        extensions=(".zip", ".reprofig"),
        mime_types=("application/zip",),
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        if not prefix.startswith(b"PK"):
            return False
        try:
            with zipfile.ZipFile(path) as archive:
                names = set(archive.namelist())
                return MANIFEST in names or LEGACY_MANIFEST in names or not any(
                    marker in names
                    for marker in ("ppt/presentation.xml", "word/document.xml", "xl/workbook.xml")
                )
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
        entries: dict[str, bytes] = {}
        try:
            with zipfile.ZipFile(source) as archive:
                seen: set[str] = set()
                for info in archive.infolist():
                    if not _valid_member(info.filename):
                        raise CarrierError(f"unsafe ZIP member {info.filename!r}")
                    normalized = posixpath.normpath(info.filename.replace("\\", "/"))
                    if normalized in seen:
                        raise CarrierError(f"duplicate ZIP member {normalized!r}")
                    seen.add(normalized)
                    mode = info.external_attr >> 16
                    if mode and (stat.S_ISLNK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode)):
                        raise CarrierError(f"unsafe special ZIP member {info.filename!r}")
                    if info.is_dir() or info.filename in {MANIFEST, LEGACY_MANIFEST, ROCRATE, CHECKSUMS}:
                        continue
                    if info.filename.startswith(("reprofig/records/", "records/", "data/", "statistics/")):
                        continue
                    entries[info.filename] = archive.read(info)
        except zipfile.BadZipFile as exc:
            raise CarrierFormatError("file is not a valid ZIP archive") from exc
        tokens = record_path_tokens(records)
        for entry in manifest.records:
            entry.record_path = f"records/{tokens[entry.figure_id]}/record.json"
        entries[MANIFEST] = manifest.to_json(indent=2).encode("utf-8")
        entries[ROCRATE] = _rocrate(records, manifest, tokens)
        for record in records:
            token = tokens[record.figure_id]
            entries[f"records/{token}/record.json"] = record.to_json(indent=2).encode(
                "utf-8"
            )
            for index, table in enumerate(record.data_tables):
                if table.contents is not None:
                    entries[
                        f"data/{token}/{index:03d}-{safe_filename_token(table.name)}.csv"
                    ] = table.contents.encode("utf-8")
            entries[f"statistics/{token}.csv"] = statistics_csv_bytes(
                record.statistics
            )
        entries[CHECKSUMS] = "".join(
            f"{sha256_bytes(entries[name])}  {name}\n"
            for name in sorted(entries)
            if name != CHECKSUMS
        ).encode("utf-8")
        output = io.BytesIO()
        with zipfile.ZipFile(output, "w") as archive:
            for name in sorted(entries):
                archive.writestr(_info(name), entries[name])
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
                seen: set[str] = set()
                total_size = 0
                for info in archive.infolist():
                    if not _valid_member(info.filename):
                        raise CarrierError(f"unsafe ZIP member {info.filename!r}")
                    normalized = posixpath.normpath(info.filename.replace("\\", "/"))
                    if normalized in seen:
                        raise CarrierError(f"duplicate ZIP member {normalized!r}")
                    seen.add(normalized)
                    mode = info.external_attr >> 16
                    if mode and (stat.S_ISLNK(mode) or stat.S_ISCHR(mode) or stat.S_ISBLK(mode)):
                        raise CarrierError(f"unsafe special ZIP member {info.filename!r}")
                    total_size += info.file_size
                    if total_size > MAX_BUNDLE_UNCOMPRESSED:
                        raise CarrierError("ZIP exceeds total decompressed-size limit")
                    if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
                        raise CarrierError(f"ZIP member has unsafe compression ratio: {info.filename}")
                if CHECKSUMS not in archive.namelist():
                    raise CarrierError("ZIP has no ReproFig checksum manifest")
                if archive.getinfo(CHECKSUMS).file_size > max_decompressed:
                    raise CarrierError("ZIP checksum manifest exceeds size limit")
                checksum_lines = archive.read(CHECKSUMS).decode("utf-8").splitlines()
                expected: dict[str, str] = {}
                for line in checksum_lines:
                    digest, separator, name = line.partition("  ")
                    if not separator or len(digest) != 64 or not _valid_member(name):
                        raise CarrierError("ZIP checksum manifest is invalid")
                    if name in expected:
                        raise CarrierError(f"duplicate checksum entry {name!r}")
                    expected[name] = digest
                actual_members = {
                    info.filename
                    for info in archive.infolist()
                    if not info.is_dir() and info.filename != CHECKSUMS
                }
                if set(expected) != actual_members:
                    missing_hashes = sorted(actual_members - set(expected))
                    stale_hashes = sorted(set(expected) - actual_members)
                    raise CarrierError(
                        "ZIP checksum coverage mismatch: "
                        f"unhashed={missing_hashes}, missing={stale_hashes}"
                    )
                for name, digest in expected.items():
                    if name not in archive.namelist():
                        raise CarrierError(f"checksummed ZIP member is missing: {name}")
                    if sha256_bytes(archive.read(name)) != digest:
                        raise CarrierError(f"ZIP member checksum mismatch: {name}")
                try:
                    info = archive.getinfo(MANIFEST)
                except KeyError as exc:
                    try:
                        info = archive.getinfo(LEGACY_MANIFEST)
                    except KeyError:
                        raise CarrierError("ZIP has no embedded ReproFig manifest") from exc
                if info.file_size > max_decompressed or info.compress_size > max_compressed:
                    raise CarrierError("ZIP ReproFig manifest exceeds size limit")
                manifest = CarrierManifest.from_json(archive.read(info))
        except zipfile.BadZipFile as exc:
            raise CarrierFormatError("file is not a valid ZIP archive") from exc
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest
