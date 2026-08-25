"""Format-neutral public API for ReproFig artifact carriers."""

from __future__ import annotations

import os
import csv
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .carriers.base import CarrierError
from .carriers.manifest import CarrierManifest
from .carriers.payload import DEFAULT_MAX_COMPRESSED, DEFAULT_MAX_DECOMPRESSED
from .carriers.registry import formats, get_adapter, identify_format
from .profiles import derive_profile
from .profiles import approved_public_tables
from .schema import FigureRecord, deterministic_json
from .tables import safe_filename_token, statistics_csv_bytes
from .validation import (
    ValidationReport,
    record_has_private_strings,
    validate_record,
    validate_svg,
)
from .sources import file_sha256, source_status

RASTER_FORMATS = frozenset({"png", "jpeg", "tiff", "webp", "avif", "heif"})
VECTOR_FORMATS = frozenset({"svg", "pdf"})
DEFAULT_RASTER_DPI = 300
SCREEN_DPI = 150
LINE_ART_DPI = 600


def _records(value: FigureRecord | Sequence[FigureRecord]) -> list[FigureRecord]:
    result = [value] if isinstance(value, FigureRecord) else list(value)
    if not result:
        raise ValueError("at least one FigureRecord is required")
    if not all(isinstance(item, FigureRecord) for item in result):
        raise TypeError("records must contain FigureRecord values")
    identifiers = [item.figure_id for item in result]
    if len(identifiers) != len(set(identifiers)):
        raise ValueError("figure identifiers must be unique within one carrier")
    return result


def _dedupe_records(records: Sequence[FigureRecord]) -> list[FigureRecord]:
    unique: dict[str, FigureRecord] = {}
    for record in records:
        previous = unique.get(record.figure_id)
        if previous is not None and previous.fingerprint() != record.fingerprint():
            raise CarrierError(
                f"conflicting records share figure identifier {record.figure_id!r}"
            )
        unique[record.figure_id] = record
    return list(unique.values())


def _render_facts(
    path: Path,
    format: str,
    requested_dpi: float | None = None,
    *,
    requested_width: float | None = None,
    requested_height: float | None = None,
    format_options: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    facts: dict[str, Any] = {"kind": "vector" if format in VECTOR_FORMATS else "raster"}
    if requested_dpi is not None:
        facts["requested_dpi"] = float(requested_dpi)
    if format not in RASTER_FORMATS:
        facts["intrinsic_dpi"] = False
        facts["embedded_raster_min_dpi"] = None
        return facts
    try:
        from PIL import Image

        with Image.open(path) as image:
            facts["width_px"] = image.width
            facts["height_px"] = image.height
            facts["source_width_px"] = image.width
            facts["source_height_px"] = image.height
            facts["color_space"] = image.mode
            facts["bit_depth"] = 16 if "16" in image.mode else 8
            facts["codec"] = format
            facts["resampled"] = False
            dpi = image.info.get("dpi")
            if dpi and len(dpi) >= 2:
                facts["actual_dpi_x"] = round(float(dpi[0]), 6)
                facts["actual_dpi_y"] = round(float(dpi[1]), 6)
                if dpi[0] and dpi[1]:
                    facts["physical_width_inches"] = round(image.width / float(dpi[0]), 6)
                    facts["physical_height_inches"] = round(image.height / float(dpi[1]), 6)
    except Exception:
        pass
    if requested_width is not None:
        facts["requested_width_inches"] = float(requested_width)
    if requested_height is not None:
        facts["requested_height_inches"] = float(requested_height)
    for key in ("quality", "chroma_subsampling", "compression", "compress_level"):
        if format_options and key in format_options:
            facts[key] = format_options[key]
    return facts


def embed_file(
    source: str | os.PathLike[str],
    records: FigureRecord | Sequence[FigureRecord],
    *,
    output_path: str | os.PathLike[str] | None = None,
    format: str | None = None,
    figure_profile: str | None = None,
    safe_columns: Sequence[str] | Mapping[str, Sequence[str]] | None = None,
    public_sources: Mapping[str, str] | None = None,
    targets: Sequence[Mapping[str, Any] | None] | None = None,
    renders: Sequence[Mapping[str, Any] | None] | None = None,
    allow_reencode: bool = False,
    options: Mapping[str, Any] | None = None,
) -> Path:
    """Embed one or more records without silently changing carrier strategy."""

    source_path = Path(source)
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    target = Path(output_path) if output_path is not None else source_path
    carrier_format = identify_format(source_path, format=format)
    adapter = get_adapter(carrier_format)
    final_records = _records(records)
    if figure_profile is not None:
        final_records = [
            derive_profile(
                record,
                figure_profile,
                safe_columns=safe_columns,
                public_sources=public_sources,
            )
            for record in final_records
        ]
    if len(final_records) > 1 and not adapter.capabilities.multiple_records:
        raise CarrierError(f"{carrier_format} supports only one ReproFig record")
    render_values = list(renders) if renders is not None else [
        _render_facts(source_path, carrier_format) for _record in final_records
    ]
    manifest = CarrierManifest.for_records(
        carrier_format,
        final_records,
        media_type=adapter.capabilities.mime_types[0],
        targets=targets,
        renders=render_values,
        carrier={
            "metadata_only": adapter.capabilities.metadata_only,
            "preserves_encoded_media": adapter.capabilities.preserves_encoded_media,
        },
    )
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, candidate_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=target.suffix + ".candidate"
    )
    os.close(descriptor)
    candidate = Path(candidate_name)
    try:
        adapter.embed(
            source_path,
            candidate,
            final_records,
            manifest=manifest,
            allow_reencode=allow_reencode,
            options=dict(options or {}),
        )
        recovered, recovered_manifest = adapter.extract(
            candidate,
            max_compressed=DEFAULT_MAX_COMPRESSED,
            max_decompressed=DEFAULT_MAX_DECOMPRESSED,
        )
        expected_fingerprints = [record.fingerprint() for record in final_records]
        if [record.fingerprint() for record in recovered] != expected_fingerprints:
            raise CarrierError("embedded records failed post-write verification")
        if recovered_manifest.format != manifest.format:
            raise CarrierError("embedded carrier manifest format changed during write")
        os.replace(candidate, target)
    finally:
        try:
            candidate.unlink()
        except OSError:
            pass
    return target


def extract_records(
    path: str | os.PathLike[str],
    *,
    format: str | None = None,
    max_compressed: int = DEFAULT_MAX_COMPRESSED,
    max_decompressed: int = DEFAULT_MAX_DECOMPRESSED,
    include_manifest: bool = False,
) -> list[FigureRecord] | tuple[list[FigureRecord], CarrierManifest]:
    artifact = Path(path)
    carrier_format = identify_format(artifact, format=format)
    records, manifest = get_adapter(carrier_format).extract(
        artifact,
        max_compressed=max_compressed,
        max_decompressed=max_decompressed,
    )
    return (records, manifest) if include_manifest else records


def extract_record(
    path: str | os.PathLike[str],
    *,
    figure_id: str | None = None,
    format: str | None = None,
) -> FigureRecord:
    """Return one selected record and reject ambiguous multi-record carriers."""

    records = extract_records(path, format=format)
    if figure_id is not None:
        matches = [record for record in records if record.figure_id == figure_id]
        if not matches:
            raise CarrierError(f"carrier has no figure record {figure_id!r}")
        return matches[0]
    if len(records) != 1:
        raise CarrierError(
            f"carrier has {len(records)} figure records; provide figure_id="
        )
    return records[0]


def extract_artifact(
    path: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    *,
    overwrite: bool = False,
    figure_id: str | None = None,
) -> list[Path]:
    records, manifest = extract_records(path, include_manifest=True)
    if figure_id is not None:
        records = [record for record in records if record.figure_id == figure_id]
        if not records:
            raise CarrierError(f"carrier has no figure record {figure_id!r}")
    for record in records:
        integrity = validate_record(record, require_complete=False)
        if not integrity.valid:
            messages = "; ".join(issue.message for issue in integrity.issues)
            raise CarrierError(f"record {record.figure_id} failed validation: {messages}")
    destination = Path(output_dir)
    destination.mkdir(parents=True, exist_ok=True)
    planned: list[tuple[str, bytes]] = []

    def write(name: str, value: bytes) -> None:
        planned.append((name, value))

    write("reprofig-manifest.json", manifest.to_json(indent=2).encode("utf-8"))
    for record in records:
        prefix = safe_filename_token(record.figure_id)
        write(f"{prefix}.record.json", record.to_json(indent=2).encode("utf-8"))
        for index, table in enumerate(record.data_tables):
            if table.contents is not None:
                write(
                    f"{prefix}.{index:03d}-{safe_filename_token(table.name)}.csv",
                    table.contents.encode("utf-8"),
                )
        write(f"{prefix}.statistics.csv", statistics_csv_bytes(record.statistics))
        from .publication import caption_for

        write(f"{prefix}.caption.md", caption_for(record).encode("utf-8"))
        write(
            f"{prefix}.producer.json",
            (deterministic_json(record.producer, indent=2) + "\n").encode("utf-8"),
        )
        script = record.reproduction.get("script")
        if isinstance(script, str) and script:
            write(f"{prefix}.reproduce.py", script.encode("utf-8"))
    names = [name for name, _value in planned]
    if len(names) != len(set(names)):
        raise ValueError("artifact extraction filenames collide")
    if not overwrite:
        existing = [destination / name for name in names if (destination / name).exists()]
        if existing:
            raise FileExistsError(
                "extraction would overwrite: " + ", ".join(str(path) for path in existing)
            )
    outputs: list[Path] = []
    with tempfile.TemporaryDirectory(dir=destination, prefix=".reprofig-extract-") as temporary_name:
        temporary = Path(temporary_name)
        for name, value in planned:
            (temporary / name).write_bytes(value)
        for name, _value in planned:
            output = destination / name
            os.replace(temporary / name, output)
            outputs.append(output)
    return outputs


def bundle_artifacts(
    artifacts: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    output_path: str | os.PathLike[str],
) -> Path:
    """Build a deterministic ReproFig ZIP/RO-Crate around existing artifacts."""

    import zipfile

    sources = _artifact_paths(artifacts)
    all_records: list[FigureRecord] = []
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent, prefix=".reprofig-bundle-") as name:
        temporary = Path(name)
        seed = temporary / "seed.zip"
        with zipfile.ZipFile(seed, "w") as archive:
            used: set[str] = set()
            for source in sources:
                member = f"figures/{source.name}"
                if member in used:
                    raise ValueError(f"bundle artifact names collide at {source.name}")
                used.add(member)
                archive.write(source, member)
                all_records.extend(extract_records(source))
        embed_file(seed, _dedupe_records(all_records), output_path=destination, format="zip")
    return destination


def validate_artifact(
    path: str | os.PathLike[str],
    *,
    expected_profile: str | None = None,
    require_complete: bool = False,
    public_safety: bool | None = None,
) -> ValidationReport:
    artifact = Path(path)
    try:
        carrier_format = identify_format(artifact)
    except (OSError, CarrierError) as exc:
        report = ValidationReport(path=str(artifact))
        report.add("error", "carrier_unreadable", str(exc))
        return report
    if carrier_format == "svg":
        return validate_svg(
            artifact,
            expected_profile=expected_profile,
            require_complete=require_complete,
            public_safety=public_safety,
        )
    report = ValidationReport(path=str(artifact))
    report.checks.extend(["carrier_format", "embedded_manifest", "record_integrity"])
    try:
        records, manifest = extract_records(artifact, include_manifest=True)
    except (OSError, CarrierError, ValueError) as exc:
        report.add("error", "record_unreadable", str(exc))
        return report
    profiles = {record.distribution_profile for record in records}
    report.profile = next(iter(profiles)) if len(profiles) == 1 else "mixed"
    for record in records:
        nested = validate_record(record, require_complete=require_complete)
        report.issues.extend(nested.issues)
        if expected_profile and record.distribution_profile != expected_profile:
            report.add(
                "error",
                "profile_mismatch",
                f"expected {expected_profile}, found {record.distribution_profile}",
                record.figure_id,
            )
        safety = public_safety
        if safety is None:
            safety = record.distribution_profile in {"public", "minimal_public"}
        if safety:
            report.checks.append("private_paths_and_credentials")
            for code, excerpt in record_has_private_strings(record):
                report.add("error", "record_" + code, "public record contains private material", excerpt)
            if record.distribution_profile == "minimal_public":
                embedded = [table.name for table in record.data_tables if table.contents is not None]
                if embedded:
                    report.add(
                        "error",
                        "minimal_data_embedded",
                        f"minimal_public record embeds row-level tables: {embedded}",
                    )
    if carrier_format in RASTER_FORMATS and manifest.records:
        report.checks.append("render_resolution")
        actual = _render_facts(artifact, carrier_format)
        for entry in manifest.records:
            render = entry.render
            for field in ("width_px", "height_px"):
                if render.get(field) is not None and actual.get(field) != render.get(field):
                    report.add(
                        "error",
                        "render_dimension_mismatch",
                        f"manifest {field}={render.get(field)} but carrier has {actual.get(field)}",
                        entry.figure_id,
                    )
            requested = render.get("requested_dpi")
            actual_x = actual.get("actual_dpi_x")
            actual_y = actual.get("actual_dpi_y")
            if requested is not None and (actual_x is None or actual_y is None):
                report.add(
                    "warning",
                    "density_missing",
                    "requested DPI is not stored in the completed raster",
                    entry.figure_id,
                )
            if actual_x and actual_y and abs(actual_x - actual_y) > 0.5:
                report.add(
                    "warning",
                    "density_anisotropic",
                    f"raster density differs by axis: {actual_x} x {actual_y} DPI",
                    entry.figure_id,
                )
            if requested is not None and actual_x is not None and actual_x + 1 < float(requested):
                report.add(
                    "warning",
                    "density_below_requested",
                    f"completed raster is {actual_x} DPI, below requested {requested} DPI",
                    entry.figure_id,
                )
            width_in = actual.get("physical_width_inches")
            if width_in and actual_x:
                expected_pixels = width_in * actual_x
                if abs(expected_pixels - actual.get("width_px", 0)) > 1.1:
                    report.add(
                        "error",
                        "density_dimension_conflict",
                        "pixel width, physical width, and DPI disagree",
                        entry.figure_id,
                    )
    return report


def inspect_artifact(
    path: str | os.PathLike[str],
    *,
    figure_id: str | None = None,
    project_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    artifact = Path(path)
    carrier_format = identify_format(artifact)
    records, manifest = extract_records(artifact, include_manifest=True)
    selected = (
        [record for record in records if record.figure_id == figure_id]
        if figure_id
        else records
    )
    if figure_id and not selected:
        raise CarrierError(f"carrier has no figure record {figure_id!r}")
    report = validate_artifact(artifact)
    return {
        "path": str(artifact.resolve()),
        "format": carrier_format,
        "media_type": manifest.media_type,
        "record_count": len(records),
        "valid": report.valid,
        "records": [
            {
                "schema": record.schema,
                "figure_id": record.figure_id,
                "created_at": record.created_at,
                "profile": record.distribution_profile,
                "title": record.title,
                "producer": record.producer,
                "analysis": record.analysis,
                "data_tables": [
                    {
                        "name": table.name,
                        "rows": table.row_count,
                        "columns": table.column_count,
                        "embedded": table.embedded,
                        "sha256": table.sha256,
                    }
                    for table in record.data_tables
                ],
                "statistics_status": record.statistics_status,
                "statistics_count": len(record.statistics),
                "sources": [
                    {**source.to_dict(), "status": source_status(source, project_root=project_root)}
                    for source in record.sources
                ],
                "record_sha256": record.fingerprint(),
            }
            for record in selected
        ],
        "targets": [entry.target for entry in manifest.records],
        "render": [entry.render for entry in manifest.records],
    }


def artifact_paths(
    value: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
) -> list[Path]:
    values = [Path(value)] if isinstance(value, (str, os.PathLike)) else [Path(item) for item in value]
    extensions = {
        extension
        for capability in formats()
        for extension in capability["extensions"]
    }
    expanded: list[Path] = []
    for candidate in values:
        if candidate.is_dir():
            expanded.extend(
                path for path in candidate.rglob("*") if path.is_file() and path.suffix.lower() in extensions
            )
        else:
            expanded.append(candidate)
    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in expanded:
        resolved = candidate.resolve()
        key = os.path.normcase(str(resolved))
        if key not in seen:
            seen.add(key)
            unique.append(resolved)
    if not unique:
        raise ValueError("no supported artifacts were provided")
    for path in unique:
        if not path.is_file():
            raise FileNotFoundError(path)
    return unique


# Backward-compatible internal alias retained for older callers.
_artifact_paths = artifact_paths


def scan_artifacts(
    artifacts: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    *,
    output_csv: str | os.PathLike[str] | None = None,
    output_jsonl: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in artifact_paths(artifacts):
        try:
            info = inspect_artifact(path)
            for record in info["records"]:
                producer = record["producer"]
                rows.append(
                    {
                        "figure_id": record["figure_id"],
                        "path": str(path),
                        "format": info["format"],
                        "title": record["title"],
                        "created_at": record["created_at"],
                        "profile": record["profile"],
                        "package": producer.get("package"),
                        "package_version": producer.get("package_version") or producer.get("version"),
                        "function": producer.get("function"),
                        "statistics_count": record["statistics_count"],
                        "data_tables": ";".join(table["name"] for table in record["data_tables"]),
                        "valid": info["valid"],
                    }
                )
        except Exception as exc:
            rows.append({"path": str(path), "valid": False, "error": str(exc)})
    fields = sorted({key for row in rows for key in row})
    if output_csv:
        target = Path(output_csv)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    if output_jsonl:
        target = Path(output_jsonl)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "".join(deterministic_json(row) + "\n" for row in rows), encoding="utf-8"
        )
    return rows


@dataclass
class ArtifactPublicationResult:
    output_dir: Path
    artifact_paths: list[Path] = field(default_factory=list)
    csv_paths: list[Path] = field(default_factory=list)
    manifest_path: Path | None = None
    validation_path: Path | None = None
    bundle_path: Path | None = None
    reports: list[ValidationReport] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return all(report.valid for report in self.reports)


def publish_artifacts(
    artifacts: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    *,
    output_dir: str | os.PathLike[str],
    figure_profile: str = "public",
    safe_columns: Sequence[str] | Mapping[str, Sequence[str]] | None = None,
    public_sources: Mapping[str, str] | None = None,
    write_csv: bool = True,
    allow_reencode: bool = False,
    bundle: bool = False,
) -> ArtifactPublicationResult:
    """Create validated public derivatives from a mixed-format artifact batch."""

    if figure_profile not in {"public", "minimal_public"}:
        raise ValueError("publication profile must be public or minimal_public")
    sources = _artifact_paths(artifacts)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = ArtifactPublicationResult(output_dir=output)
    manifest_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    reserved: set[str] = {"publication_manifest.json", "publication_validation.json"}
    with tempfile.TemporaryDirectory(dir=output, prefix=".reprofig-") as temporary_name:
        temporary = Path(temporary_name)
        pending: list[tuple[Path, Path, str]] = []
        all_derived: list[FigureRecord] = []
        for source in sources:
            records, old_manifest = extract_records(source, include_manifest=True)
            derived_records: list[FigureRecord] = []
            public_table_sets: list[list[Any]] = []
            for master in records:
                configured = safe_columns
                if isinstance(safe_columns, Mapping):
                    configured = safe_columns.get(master.figure_id, safe_columns)
                public_tables = approved_public_tables(master, safe_columns=configured)
                public_table_sets.append(public_tables)
                derived_records.append(
                    derive_profile(
                        master,
                        figure_profile,
                        safe_columns=configured,
                        public_sources=public_sources,
                    )
                )
            suffix = "public" if figure_profile == "public" else "minimal-public"
            output_name = f"{source.stem}.{suffix}{source.suffix}"
            if output_name in reserved or (output / output_name).exists():
                raise FileExistsError(f"publication output collision at {output_name}")
            reserved.add(output_name)
            candidate = temporary / output_name
            embed_file(
                source,
                derived_records,
                output_path=candidate,
                targets=[entry.target for entry in old_manifest.records],
                renders=[entry.render for entry in old_manifest.records],
                allow_reencode=allow_reencode,
            )
            if identify_format(candidate) == "svg":
                from .svg import replace_dublin_core_description

                record = derived_records[0]
                replace_dublin_core_description(
                    candidate,
                    {
                        "schema": record.schema,
                        "figure_id": record.figure_id,
                        "distribution_profile": record.distribution_profile,
                        "producer": record.producer,
                    },
                )
            report = validate_artifact(
                candidate,
                expected_profile=figure_profile,
                public_safety=True,
            )
            report.path = output_name
            report.transformations.append(f"profile -> {figure_profile}")
            result.reports.append(report)
            validation_rows.append(report.to_dict())
            if not report.valid:
                errors = "; ".join(
                    issue.message for issue in report.issues if issue.severity == "error"
                )
                raise ValueError(f"public validation failed for {source.name}: {errors}")
            pending.append((candidate, output / output_name, "artifact"))
            all_derived.extend(derived_records)
            csv_names: list[str] = []
            if write_csv:
                for derived, tables in zip(derived_records, public_table_sets):
                    prefix = source.stem if len(records) == 1 else f"{source.stem}.{safe_filename_token(derived.figure_id)}"
                    for index, table in enumerate(tables):
                        if table.contents is None:
                            continue
                        name = f"{prefix}.source-data.csv" if index == 0 else f"{prefix}.{safe_filename_token(table.name)}.csv"
                        if name in reserved or (output / name).exists():
                            raise FileExistsError(f"publication output collision at {name}")
                        reserved.add(name)
                        csv_path = temporary / name
                        csv_path.write_bytes(table.contents.encode("utf-8"))
                        pending.append((csv_path, output / name, "csv"))
                        csv_names.append(name)
                    stats_name = f"{prefix}.statistics.csv"
                    if stats_name in reserved or (output / stats_name).exists():
                        raise FileExistsError(f"publication output collision at {stats_name}")
                    reserved.add(stats_name)
                    stats_path = temporary / stats_name
                    stats_path.write_bytes(statistics_csv_bytes(derived.statistics))
                    pending.append((stats_path, output / stats_name, "csv"))
                    csv_names.append(stats_name)
            manifest_rows.append(
                {
                    "input": source.name,
                    "output": output_name,
                    "format": identify_format(source),
                    "profile": figure_profile,
                    "figure_ids": [record.figure_id for record in derived_records],
                    "record_sha256s": [record.fingerprint() for record in derived_records],
                    "companion_csvs": csv_names,
                    "output_sha256": file_sha256(candidate),
                }
            )
        manifest_path = temporary / "publication_manifest.json"
        manifest_path.write_text(
            deterministic_json({"profile": figure_profile, "artifacts": manifest_rows}, indent=2) + "\n",
            encoding="utf-8",
        )
        validation_path = temporary / "publication_validation.json"
        validation_path.write_text(
            deterministic_json({"valid": result.valid, "artifacts": validation_rows}, indent=2) + "\n",
            encoding="utf-8",
        )
        pending.extend(
            [
                (manifest_path, output / manifest_path.name, "manifest"),
                (validation_path, output / validation_path.name, "validation"),
            ]
        )
        if bundle:
            import zipfile

            raw_zip = temporary / "bundle-source.zip"
            with zipfile.ZipFile(raw_zip, "w") as archive:
                for candidate, _target, kind in pending:
                    if kind in {"artifact", "csv"}:
                        archive.write(candidate, f"figures/{candidate.name}" if kind == "artifact" else f"data/{candidate.name}")
            bundle_candidate = temporary / "publication.reprofig.zip"
            embed_file(
                raw_zip,
                _dedupe_records(all_derived),
                output_path=bundle_candidate,
                format="zip",
            )
            pending.append((bundle_candidate, output / bundle_candidate.name, "bundle"))
        for source_path, target_path, kind in pending:
            os.replace(source_path, target_path)
            if kind == "artifact":
                result.artifact_paths.append(target_path)
            elif kind == "csv":
                result.csv_paths.append(target_path)
            elif kind == "manifest":
                result.manifest_path = target_path
            elif kind == "validation":
                result.validation_path = target_path
            elif kind == "bundle":
                result.bundle_path = target_path
    return result


def save_figure(
    figure: Any,
    path: str | os.PathLike[str],
    *,
    record: FigureRecord | None = None,
    figure_profile: str = "master",
    dpi: float | str | None = None,
    dpi_preset: str | None = None,
    render_preset: str | None = None,
    width: float | None = None,
    height: float | None = None,
    format_options: Mapping[str, Any] | None = None,
    write_companion_csv: bool = False,
    savefig_kwargs: Mapping[str, Any] | None = None,
    allow_reencode: bool = False,
    safe_columns: Sequence[str] | Mapping[str, Sequence[str]] | None = None,
    public_sources: Mapping[str, str] | None = None,
    proof: bool = False,
    proof_policy: Mapping[str, Any] | None = None,
    **record_kwargs: Any,
) -> FigureRecord:
    """Save a Matplotlib-like figure in any supported image/PDF carrier."""

    from .api import build_record_for_figure, save_svg, write_companion_tables

    target = Path(path)
    carrier_format = identify_format(target)
    if carrier_format not in RASTER_FORMATS | VECTOR_FORMATS:
        raise ValueError(f"save_figure cannot render directly to {carrier_format}")
    if record is None:
        record = build_record_for_figure(
            figure,
            title=record_kwargs.pop("title", None) or target.stem,
            original_stem=target.stem,
            **record_kwargs,
        )
        record_kwargs.clear()
    if record_kwargs:
        raise TypeError(f"unexpected record arguments: {sorted(record_kwargs)}")
    capture_proof = bool(proof or proof_policy)
    render_manifest = None
    if capture_proof:
        from .render.matplotlib import capture_matplotlib

        render_manifest = capture_matplotlib(figure)
    if carrier_format == "svg" and not capture_proof:
        return save_svg(
            figure,
            target,
            record=record,
            figure_profile=figure_profile,
            safe_columns=safe_columns,
            public_sources=public_sources,
            write_companion_csv=write_companion_csv,
            savefig_kwargs=savefig_kwargs,
        )
    chosen_preset = render_preset or dpi_preset
    if dpi is None and chosen_preset:
        presets = {"screen": SCREEN_DPI, "continuous_tone": DEFAULT_RASTER_DPI, "line_art": LINE_ART_DPI}
        try:
            dpi = presets[chosen_preset]
        except KeyError as exc:
            raise ValueError(f"unknown render_preset {chosen_preset!r}") from exc
    if dpi == "preserve":
        raise ValueError("dpi='preserve' applies to embed_file; newly rendered figures need a numeric DPI")
    if dpi is not None and (not isinstance(dpi, (int, float)) or float(dpi) <= 0):
        raise ValueError("dpi must be a positive number")
    for name, value in (("width", width), ("height", height)):
        if value is not None and float(value) <= 0:
            raise ValueError(f"{name} must be a positive number of inches")
    effective_dpi = dpi if dpi is not None else (DEFAULT_RASTER_DPI if carrier_format in RASTER_FORMATS else None)
    final_record = derive_profile(
        record,
        figure_profile,
        safe_columns=safe_columns,
        public_sources=public_sources,
    )
    if render_manifest is not None:
        # The semantic manifest describes the scientific geometry and is shared
        # by every carrier variant. Pixel/subtree references are attached later
        # as carrier-specific bindings so SVG, PDF and raster variants retain
        # one evidence root.
        final_record.extensions["render_manifest"] = render_manifest.to_dict()
        from .evidence import refresh_evidence_graph

        final_record = refresh_evidence_graph(final_record)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=target.suffix
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    original_size = None
    try:
        kwargs = dict(savefig_kwargs or {})
        if format_options:
            if carrier_format in {"png", "jpeg", "tiff", "webp"}:
                pil_kwargs = dict(kwargs.get("pil_kwargs") or {})
                pil_kwargs.update(dict(format_options))
                kwargs["pil_kwargs"] = pil_kwargs
            elif carrier_format not in {"avif", "heif"}:
                kwargs.update(dict(format_options))
        if effective_dpi is not None:
            kwargs.setdefault("dpi", effective_dpi)
        if width is not None or height is not None:
            original_size = tuple(float(value) for value in figure.get_size_inches())
            aspect = original_size[0] / original_size[1]
            requested_width = float(width) if width is not None else float(height) * aspect
            requested_height = float(height) if height is not None else float(width) / aspect
            figure.set_size_inches(requested_width, requested_height, forward=False)
        else:
            requested_width = requested_height = None
        if carrier_format in {"avif", "heif"}:
            from PIL import Image

            png_path = temporary.with_suffix(temporary.suffix + ".png")
            try:
                figure.savefig(png_path, format="png", **kwargs)
                with Image.open(png_path) as rendered:
                    if carrier_format == "avif":
                        rendered.save(
                            temporary,
                            format="AVIF",
                            **dict(format_options or {}),
                        )
                    else:
                        import pillow_heif

                        heif = pillow_heif.from_pillow(rendered)
                        heif.save(temporary, **dict(format_options or {}))
            finally:
                try:
                    png_path.unlink()
                except OSError:
                    pass
        else:
            figure.savefig(temporary, format=carrier_format, **kwargs)
        if render_manifest is not None:
            if carrier_format == "svg":
                from .render.vector import bind_svg_semantics
                from .render.schema import RenderManifest

                carrier_manifest = RenderManifest.from_dict(render_manifest.to_dict())
                bind_svg_semantics(str(temporary), carrier_manifest)
                final_record.extensions["visual_reference"] = {
                    "schema": "reprofig-visual-reference/1",
                    "format": "svg",
                    "vector_elements": dict(
                        carrier_manifest.environment.get("vector_elements") or {}
                    ),
                }
            elif carrier_format in RASTER_FORMATS:
                from .render.canonical import capture_raster_reference

                final_record.extensions["visual_reference"] = {
                    "schema": "reprofig-visual-reference/1",
                    "format": carrier_format,
                    "raster_reference": capture_raster_reference(
                        temporary, manifest=render_manifest
                    ),
                }
            elif carrier_format == "pdf":
                try:
                    from .render.canonical import capture_pdf_reference

                    final_record.extensions["visual_reference"] = {
                        "schema": "reprofig-visual-reference/1",
                        "format": "pdf",
                        "raster_reference": capture_pdf_reference(
                            temporary, manifest=render_manifest
                        ),
                    }
                except RuntimeError:
                    # PDF proof remains internally checkable without the
                    # optional renderer; required display verification fails
                    # honestly later as unavailable.
                    final_record.extensions.pop("visual_reference", None)
        render = _render_facts(
            temporary,
            carrier_format,
            float(effective_dpi) if effective_dpi is not None else None,
            requested_width=requested_width,
            requested_height=requested_height,
            format_options=format_options,
        )
        if proof_policy:
            embedded_handle, embedded_name = tempfile.mkstemp(
                dir=str(target.parent),
                prefix=f".{target.name}.proof.",
                suffix=target.suffix,
            )
            os.close(embedded_handle)
            embedded_candidate = Path(embedded_name)
            try:
                embedded_candidate.unlink()
                embed_file(
                    temporary,
                    final_record,
                    output_path=embedded_candidate,
                    format=carrier_format,
                    renders=[render],
                    allow_reencode=allow_reencode
                    or carrier_format in {"avif", "heif"},
                )
                from .policy import apply_artifact_policy

                final_record, _policy_report = apply_artifact_policy(
                    embedded_candidate,
                    proof_policy,
                    record=final_record,
                    reuse_encrypted_sections=any(
                        bool(value.get("encrypted"))
                        for value in (
                            (record.extensions.get("proof") or {}).get("sections", [])
                            if isinstance(record.extensions.get("proof"), Mapping)
                            else []
                        )
                    ),
                )
                os.replace(embedded_candidate, target)
            finally:
                try:
                    embedded_candidate.unlink()
                except OSError:
                    pass
        else:
            embed_file(
                temporary,
                final_record,
                output_path=target,
                format=carrier_format,
                renders=[render],
                allow_reencode=allow_reencode or carrier_format in {"avif", "heif"},
            )
    finally:
        if original_size is not None:
            figure.set_size_inches(*original_size, forward=False)
        try:
            temporary.unlink()
        except OSError:
            pass
    if write_companion_csv:
        companion = final_record
        if figure_profile == "minimal_public":
            companion = derive_profile(
                record,
                "public",
                safe_columns=safe_columns,
                public_sources=public_sources,
            )
        write_companion_tables(companion, target)
    return final_record
