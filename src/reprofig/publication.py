"""Extract, inspect, publish, catalogue, and archive figure records."""

from __future__ import annotations

import csv
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from .naming import (
    collision_safe_stems,
    export_name_override,
    export_stem,
    normalize_naming_mode,
    readable_filename_token,
    role_filename,
    unique_role_filenames,
)
from .profiles import approved_public_tables, derive_profile
from .schema import DataTable, FigureRecord, deterministic_json
from .sources import file_sha256, source_status
from .svg import (
    embed_record,
    extract_record,
    legacy_dublin_core_record,
    replace_dublin_core_description,
)
from .tables import safe_filename_token, statistics_csv_bytes
from .validation import ValidationReport, privacy_leaks, validate_record, validate_svg


@dataclass
class PublicationResult:
    output_dir: Path
    svg_paths: list[Path] = field(default_factory=list)
    csv_paths: list[Path] = field(default_factory=list)
    manifest_path: Path | None = None
    validation_path: Path | None = None
    reports: list[ValidationReport] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return all(report.valid for report in self.reports)


def _paths(value: str | os.PathLike[str] | Iterable[str | os.PathLike[str]]) -> list[Path]:
    if isinstance(value, (str, os.PathLike)):
        candidates = [Path(value)]
    else:
        candidates = [Path(item) for item in value]
    expanded: list[Path] = []
    for candidate in candidates:
        if candidate.is_dir():
            expanded.extend(sorted(candidate.rglob("*.svg")))
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
        raise ValueError("no SVG figures were provided")
    for candidate in unique:
        if not candidate.is_file():
            raise FileNotFoundError(candidate)
    return unique


def _safe_columns_for(
    path: Path,
    record: FigureRecord,
    configured: Sequence[str] | Mapping[str, Any] | None,
) -> Sequence[str] | Mapping[str, Sequence[str]] | None:
    if not isinstance(configured, Mapping):
        return configured
    for key in (str(path), path.name, path.stem, record.figure_id):
        if key in configured:
            return configured[key]
    table_names = {table.name for table in record.data_tables}
    if set(map(str, configured)).issubset(table_names | {"*"}):
        return configured
    return None


def caption_for(record: FigureRecord) -> str:
    """Create a factual caption draft without scientific interpretation."""

    lines: list[str] = []
    if record.title:
        lines.append(record.title.rstrip("." ) + ".")
    unit = record.analysis.get("independent_unit")
    if unit:
        lines.append(f"The independent sample unit was {unit}.")
    for statistic in record.statistics:
        headline = statistic.get("headline")
        if headline:
            lines.append(str(headline).rstrip(".") + ".")
        test = statistic.get("test")
        if isinstance(test, Mapping):
            test_name = test.get("name") or "statistical test"
            p_value = statistic.get("p_raw", test.get("p"))
        else:
            test_name = statistic.get("test") or statistic.get("kind") or "statistical test"
            p_value = statistic.get("p_raw", statistic.get("p"))
        detail = str(test_name)
        if p_value is not None:
            detail += f", exact p={p_value}"
        adjusted = statistic.get("p_adjusted", statistic.get("q"))
        if adjusted is not None:
            detail += f", adjusted p={adjusted}"
        correction = statistic.get("correction")
        if correction:
            detail += f", correction={correction}"
        if statistic.get("n") is not None:
            detail += f", n={statistic['n']}"
        groups = statistic.get("groups")
        if isinstance(groups, Sequence) and not isinstance(groups, (str, bytes)):
            sizes = [
                f"{group.get('name', 'group')} n={group.get('n')}"
                for group in groups
                if isinstance(group, Mapping) and group.get("n") is not None
            ]
            if sizes:
                detail += ", " + ", ".join(sizes)
        effect = statistic.get("effect") or statistic.get("effect_size")
        if isinstance(effect, Mapping) and effect.get("value") is not None:
            detail += f", {effect.get('name', 'effect')}={effect['value']}"
        elif effect is not None:
            detail += f", effect={effect}"
        lines.append(detail.rstrip(".") + ".")
    if not record.statistics and record.statistics_status == "not_applicable":
        lines.append("No inferential statistics applied to this figure.")
    return " ".join(lines).strip() + ("\n" if lines else "")


def inspect_figure(
    svg_path: str | os.PathLike[str],
    *,
    project_root: str | os.PathLike[str] | None = None,
) -> dict[str, Any]:
    path = Path(svg_path)
    record = extract_record(path)
    sample_sizes: list[Any] = []
    p_values: list[float] = []
    metrics: list[str] = []
    groups_seen: list[str] = []
    for statistic in record.statistics:
        for key in ("metric", "outcome", "x", "y"):
            value = statistic.get(key)
            if value is not None and str(value) not in metrics:
                metrics.append(str(value))
        group_value = statistic.get("group")
        if group_value is not None and str(group_value) not in groups_seen:
            groups_seen.append(str(group_value))
        if "n" in statistic:
            sample_sizes.append(statistic["n"])
        for key in ("p", "p_raw", "p_adjusted", "q"):
            try:
                if statistic.get(key) is not None:
                    p_values.append(float(statistic[key]))
            except (TypeError, ValueError):
                pass
        nested_test = statistic.get("test")
        if isinstance(nested_test, Mapping):
            for key in ("p", "p_raw", "p_adjusted", "q"):
                try:
                    if nested_test.get(key) is not None:
                        p_values.append(float(nested_test[key]))
                except (TypeError, ValueError):
                    pass
        for group in statistic.get("groups", []) if isinstance(statistic, dict) else []:
            if isinstance(group, Mapping) and group.get("n") is not None:
                sample_sizes.append(group["n"])
            if isinstance(group, Mapping) and group.get("name") is not None:
                name = str(group["name"])
                if name not in groups_seen:
                    groups_seen.append(name)
    return {
        "path": str(path.resolve()),
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
        "sample_sizes": sample_sizes,
        "metrics": metrics,
        "groups": groups_seen,
        "smallest_p": min(p_values) if p_values else None,
        "sources": [
            {**source.to_dict(), "status": source_status(source, project_root=project_root)}
            for source in record.sources
        ],
        "reproduction_available": bool(record.reproduction.get("script")),
        "valid": validate_svg(path).valid,
        "provenance_level": _record_provenance_level(record),
    }


def _record_provenance_level(record: FigureRecord) -> str:
    complete_data = record.data_status == "complete" and bool(record.data_tables)
    complete_statistics = record.statistics_status in {"complete", "not_applicable"}
    complete_producer = bool(record.producer.get("package"))
    complete_sources = bool(record.sources)
    return (
        "complete"
        if complete_data and complete_statistics and complete_producer and complete_sources
        else "incomplete"
    )


def _sidecar_entry(path: Path) -> dict[str, Any] | None:
    manifest = path.parent / "figures.json"
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
        figures = value.get("figures") if isinstance(value, Mapping) else None
        entry = figures.get(path.name) if isinstance(figures, Mapping) else None
        return dict(entry) if isinstance(entry, Mapping) else None
    except (OSError, ValueError, TypeError):
        return None


def classify_figure(svg_path: str | os.PathLike[str]) -> dict[str, Any]:
    """Classify complete, legacy, sidecar-only, and unrecorded SVG figures."""

    path = Path(svg_path)
    try:
        record = extract_record(path)
        return {
            "provenance_level": _record_provenance_level(record),
            "figure_id": record.figure_id,
            "record": record,
        }
    except Exception:
        pass
    legacy = legacy_dublin_core_record(path)
    if legacy:
        return {"provenance_level": "producer_only", "legacy": legacy}
    sidecar = _sidecar_entry(path)
    if sidecar:
        return {"provenance_level": "sidecar_only", "sidecar": sidecar}
    return {"provenance_level": "none"}


def _table_filename(record: FigureRecord, table: DataTable, index: int) -> str:
    if index == 0:
        return f"{record.original_stem or record.figure_id}.source-data.csv"
    safe = "".join(char if char.isalnum() or char in "-_" else "-" for char in table.name)
    return f"{record.original_stem or record.figure_id}.{safe}.csv"


def extract_figure(
    svg_path: str | os.PathLike[str],
    output_dir: str | os.PathLike[str],
    *,
    overwrite: bool = False,
    export_name: str | None = None,
    naming: str = "readable",
) -> list[Path]:
    source = Path(svg_path)
    mode = normalize_naming_mode(naming)
    record = extract_record(source)
    integrity = validate_record(record, require_complete=False)
    if not integrity.valid:
        messages = "; ".join(issue.message for issue in integrity.issues)
        raise ValueError(f"figure record failed integrity validation: {messages}")
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    stem = (
        export_stem(
            record,
            source,
            export_name=export_name,
            naming=mode,
        )
        if mode == "readable"
        else source.stem
    )
    planned: list[tuple[Path, bytes]] = []
    readable_names = unique_role_filenames(
        stem,
        [table.name for table in record.data_tables],
        "csv",
        naming=mode,
    ) if mode == "readable" else []
    for index, table in enumerate(record.data_tables):
        if table.contents is None:
            continue
        if mode == "readable":
            table_name = readable_names[index]
        else:
            suffix = "source-data" if index == 0 else safe_filename_token(table.name)
            table_name = f"{stem}.{suffix}.csv"
        planned.append(
            (output / table_name, table.contents.encode("utf-8"))
        )
    planned.extend(
        [
            (
                output / role_filename(stem, "statistics", "csv", naming=mode),
                statistics_csv_bytes(record.statistics),
            ),
            (
                output
                / role_filename(
                    stem,
                    "record" if mode == "readable" else "provenance",
                    "json",
                    naming=mode,
                ),
                (record.to_json(indent=2) + "\n").encode("utf-8"),
            ),
            (
                output / role_filename(stem, "caption", "md", naming=mode),
                caption_for(record).encode("utf-8"),
            ),
        ]
    )
    script = record.reproduction.get("script")
    if isinstance(script, str) and script:
        planned.append(
            (
                output
                / role_filename(
                    stem,
                    "plot" if mode == "readable" else "reproduce",
                    "py",
                    naming=mode,
                ),
                script.encode("utf-8"),
            )
        )
    planned_paths = [path for path, _contents in planned]
    if len(planned_paths) != len(set(planned_paths)):
        raise ValueError("extracted filenames collide after sanitization")
    if not overwrite:
        existing = [str(path) for path, _contents in planned if path.exists()]
        if existing:
            raise FileExistsError("extraction would overwrite: " + ", ".join(existing))
    written: list[Path] = []
    for path, contents in planned:
        path.write_bytes(contents)
        written.append(path)
    return written


def _public_description(record: FigureRecord) -> dict[str, Any]:
    return {
        "schema": record.schema,
        "figure_id": record.figure_id,
        "distribution_profile": record.distribution_profile,
        "producer": record.producer,
    }


def publish_figures(
    figures: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
    *,
    output_dir: str | os.PathLike[str],
    figure_profile: str = "public",
    safe_columns: Sequence[str] | Mapping[str, Any] | None = None,
    public_sources: Mapping[str, str] | None = None,
    strict: bool = True,
    write_csv: bool = True,
    rocrate: bool = False,
    export_name: str | Mapping[str, str] | None = None,
    naming: str = "readable",
) -> PublicationResult:
    """Create validated public derivatives and public-safe publisher CSV files."""

    if figure_profile not in {"public", "minimal_public"}:
        raise ValueError("publication profile must be public or minimal_public")
    mode = normalize_naming_mode(naming)
    sources = _paths(figures)
    output = Path(output_dir).resolve()
    output.mkdir(parents=True, exist_ok=True)
    records = [(path, extract_record(path)) for path in sources]
    for path, record in records:
        integrity = validate_record(
            record,
            require_complete=record.distribution_profile == "master",
        )
        if not integrity.valid:
            messages = "; ".join(issue.message for issue in integrity.issues)
            raise ValueError(f"cannot publish {path.name}: {messages}")
    requested_stems = [
        (
            export_stem(
                record,
                path,
                export_name=export_name_override(
                    export_name,
                    path,
                    [record],
                    source_count=len(records),
                ),
                naming=mode,
            )
            if mode == "readable"
            else path.stem
        )
        for path, record in records
    ]
    stems = (
        collision_safe_stems(
            requested_stems,
            [record.figure_id for _path, record in records],
        )
        if mode == "readable"
        else requested_stems
    )
    if mode == "legacy" and len(stems) != len(set(stems)):
        raise ValueError("duplicate figure stems would collide in publication output")
    profile_suffix = "public" if figure_profile == "public" else "minimal-public"
    planned_names: set[str] = set()

    def reserve(name: str) -> None:
        if name in planned_names:
            raise ValueError(f"publication outputs would collide at {name}")
        planned_names.add(name)

    prepared: list[
        tuple[Path, FigureRecord, FigureRecord, list[DataTable], list[str], str, str]
    ] = []
    for (source, master), stem in zip(records, stems):
        if master.distribution_profile == "minimal_public" and figure_profile == "public":
            raise ValueError(f"cannot recreate public row-level data from {source}")
        configured_columns = _safe_columns_for(source, master, safe_columns)
        safe_tables = approved_public_tables(master, safe_columns=configured_columns)
        derived = derive_profile(
            master,
            figure_profile,
            safe_columns=configured_columns,
            public_sources=public_sources,
        )
        output_name = role_filename(
            stem,
            profile_suffix,
            "svg",
            naming=mode,
        )
        reserve(output_name)
        table_names: list[str] = []
        if write_csv:
            table_roles = [
                (
                    "source-data"
                    if index == 0
                    else (
                        readable_filename_token(table.name, fallback="data")
                        if mode == "readable"
                        else safe_filename_token(table.name)
                    )
                )
                for index, table in enumerate(safe_tables)
            ]
            readable_table_names = (
                unique_role_filenames(
                    stem,
                    table_roles,
                    "csv",
                    naming=mode,
                )
                if mode == "readable"
                else []
            )
            for index, table in enumerate(safe_tables):
                if table.contents is None:
                    continue
                csv_name = (
                    readable_table_names[index]
                    if mode == "readable"
                    else role_filename(
                        stem,
                        table_roles[index],
                        "csv",
                        naming=mode,
                    )
                )
                reserve(csv_name)
                table_names.append(csv_name)
            reserve(role_filename(stem, "statistics", "csv", naming=mode))
        prepared.append(
            (source, master, derived, safe_tables, table_names, output_name, stem)
        )
    manifest_name = (
        "publication-manifest.csv"
        if mode == "readable"
        else "publication_manifest.csv"
    )
    validation_name = (
        "publication-validation.json"
        if mode == "readable"
        else "publication_validation.json"
    )
    reserve(manifest_name)
    reserve(validation_name)
    existing = [name for name in planned_names if (output / name).exists()]
    if existing:
        raise FileExistsError("publication would overwrite: " + ", ".join(sorted(existing)))

    result = PublicationResult(output_dir=output)
    manifest_rows: list[dict[str, Any]] = []
    validation_rows: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(dir=output, prefix=".reprofig-") as temporary_name:
        temporary = Path(temporary_name)
        pending: list[tuple[Path, Path, str]] = []
        for (
            source,
            master,
            derived,
            safe_tables,
            reserved_table_names,
            output_name,
            stem,
        ) in prepared:
            temporary_svg = temporary / output_name
            shutil.copy2(source, temporary_svg)
            replace_dublin_core_description(temporary_svg, _public_description(derived))
            embed_record(temporary_svg, derived)
            report = validate_svg(
                temporary_svg,
                expected_profile=figure_profile,
                require_complete=False,
                public_safety=True,
            )
            report.path = output_name
            report.transformations.append(
                f"profile {master.distribution_profile} -> {figure_profile}"
            )
            removed_columns = sorted({
                column.name
                for table in master.data_tables
                for column in table.columns
            } - {
                column.name
                for table in derived.data_tables
                for column in table.columns
            })
            if removed_columns:
                report.transformations.append(
                    "removed data columns: " + ", ".join(removed_columns)
                )
            if figure_profile == "minimal_public" and any(
                table.contents is not None for table in master.data_tables
            ):
                report.transformations.append("removed embedded row-level table contents")
            removed_producer = sorted(set(master.producer) - set(derived.producer))
            if removed_producer:
                report.transformations.append(
                    "removed producer fields: " + ", ".join(removed_producer)
                )
            if master.reproduction != derived.reproduction:
                report.transformations.append("rewrote private reproduction strings")
            if any(
                before.relative_path != after.relative_path or before.uri != after.uri
                for before, after in zip(master.sources, derived.sources)
            ):
                report.transformations.append("removed or replaced private source locations")
            result.reports.append(report)
            validation_rows.append(report.to_dict())
            privacy_errors = [
                issue
                for issue in report.issues
                if issue.severity == "error"
                and (
                    "path" in issue.code
                    or "credential" in issue.code
                    or issue.code.startswith("record_file_uri")
                )
            ]
            if privacy_errors or (strict and not report.valid):
                messages = "; ".join(
                    issue.message for issue in report.issues if issue.severity == "error"
                )
                raise ValueError(f"public validation failed for {source.name}: {messages}")
            if not report.valid:
                result.warnings.append(
                    f"{source.name} has validation errors because strict=False"
                )
            pending.append((temporary_svg, output / output_name, "svg"))
            table_names: list[str] = []
            if write_csv:
                csv_name_iter = iter(reserved_table_names)
                for table in safe_tables:
                    if table.contents is None:
                        continue
                    csv_name = next(csv_name_iter)
                    table_path = temporary / csv_name
                    table_path.write_bytes(table.contents.encode("utf-8"))
                    pending.append((table_path, output / csv_name, "csv"))
                    table_names.append(csv_name)
                stats_name = role_filename(
                    stem,
                    "statistics",
                    "csv",
                    naming=mode,
                )
                stats_path = temporary / stats_name
                stats_path.write_bytes(statistics_csv_bytes(derived.statistics))
                pending.append((stats_path, output / stats_name, "csv"))
            manifest_rows.append(
                {
                    "figure_id": master.figure_id,
                    "master_svg": source.name,
                    "output_svg": output_name,
                    "profile": figure_profile,
                    "source_data_csvs": ";".join(table_names),
                    "source_data_sha256s": ";".join(
                        table.sha256 for table in safe_tables if table.contents is not None
                    ),
                    "statistics_csv": (
                        role_filename(stem, "statistics", "csv", naming=mode)
                        if write_csv
                        else ""
                    ),
                    "statistics_csv_sha256": derived.statistics_csv_sha256 or "",
                    "public_source_links": ";".join(
                        source_ref.uri for source_ref in derived.sources if source_ref.uri
                    ),
                    "validation_status": "valid" if report.valid else "invalid",
                    "record_sha256": derived.fingerprint(),
                    "output_svg_sha256": file_sha256(temporary_svg),
                }
            )
        manifest = temporary / manifest_name
        fields = [
            "figure_id",
            "master_svg",
            "output_svg",
            "profile",
            "source_data_csvs",
            "source_data_sha256s",
            "statistics_csv",
            "statistics_csv_sha256",
            "public_source_links",
            "validation_status",
            "record_sha256",
            "output_svg_sha256",
        ]
        with manifest.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(manifest_rows)
        validation = temporary / validation_name
        validation.write_text(
            deterministic_json({"valid": result.valid, "figures": validation_rows}, indent=2)
            + "\n",
            encoding="utf-8",
        )
        pending.extend(
            [
                (manifest, output / manifest.name, "manifest"),
                (validation, output / validation.name, "validation"),
            ]
        )
        for candidate, _target, kind in pending:
            if kind == "svg":
                continue
            text = candidate.read_text(encoding="utf-8-sig")
            leaks = privacy_leaks(text)
            if leaks:
                codes = ", ".join(sorted({code for code, _excerpt in leaks}))
                raise ValueError(f"public {kind} contains private material: {codes}")
        for source_path, target_path, kind in pending:
            os.replace(source_path, target_path)
            if kind == "svg":
                result.svg_paths.append(target_path)
            elif kind == "csv":
                result.csv_paths.append(target_path)
            elif kind == "manifest":
                result.manifest_path = target_path
            elif kind == "validation":
                result.validation_path = target_path
    if rocrate:
        export_rocrate(output, result.svg_paths + result.csv_paths)
    return result


def scan_figures(
    figures: str | os.PathLike[str] | Iterable[str | os.PathLike[str]],
    *,
    output_csv: str | os.PathLike[str] | None = None,
    output_jsonl: str | os.PathLike[str] | None = None,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in _paths(figures):
        try:
            info = inspect_figure(path)
            producer = info.get("producer") or {}
            rows.append(
                {
                    "figure_id": info.get("figure_id"),
                    "path": str(path),
                    "title": info.get("title"),
                    "created_at": info.get("created_at"),
                    "profile": info.get("profile"),
                    "package": producer.get("package"),
                    "package_version": producer.get("package_version") or producer.get("version"),
                    "function": producer.get("function"),
                    "statistics_count": info.get("statistics_count"),
                    "smallest_p": info.get("smallest_p"),
                    "metrics": ";".join(info.get("metrics", [])),
                    "groups": ";".join(info.get("groups", [])),
                    "sample_sizes": ";".join(map(str, info.get("sample_sizes", []))),
                    "data_tables": ";".join(table["name"] for table in info.get("data_tables", [])),
                    "source_roles": ";".join(source.get("role", "") for source in info.get("sources", [])),
                    "source_names": ";".join(
                        str(source.get("relative_path") or source.get("source_id") or source.get("uri") or "")
                        for source in info.get("sources", [])
                    ),
                    "source_states": ";".join(
                        str(source.get("status", "")) for source in info.get("sources", [])
                    ),
                    "run_id": producer.get("run_id"),
                    "reproduction_available": info.get("reproduction_available"),
                    "valid": info.get("valid"),
                    "provenance_level": info.get("provenance_level"),
                }
            )
        except Exception as exc:
            classification = classify_figure(path)
            fallback = classification.get("legacy") or classification.get("sidecar") or {}
            rows.append({
                "path": str(path),
                "valid": False,
                "provenance_level": classification["provenance_level"],
                "figure_id": fallback.get("figure_id"),
                "created_at": fallback.get("created_at") or fallback.get("saved_at"),
                "package_version": fallback.get("pyflash_version"),
                "function": fallback.get("function"),
                "error": str(exc),
            })
    fields = sorted({key for row in rows for key in row})
    if output_csv is not None:
        target = Path(output_csv)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("w", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=fields, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    if output_jsonl is not None:
        target = Path(output_jsonl)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            "".join(deterministic_json(row) + "\n" for row in rows), encoding="utf-8"
        )
    return rows


def export_rocrate(
    output_dir: str | os.PathLike[str], artifacts: Sequence[str | os.PathLike[str]]
) -> Path:
    """Write a dependency-free Research Object Crate 1.2 metadata document."""

    output = Path(output_dir)
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
            "name": "Scientific figure publication artifacts",
            "hasPart": [{"@id": Path(path).name} for path in artifacts],
        },
    ]
    for artifact in artifacts:
        path = Path(artifact)
        graph.append(
            {
                "@id": path.name,
                "@type": "File",
                "encodingFormat": (
                    "image/svg+xml" if path.suffix.lower() == ".svg" else "text/csv"
                ),
            }
        )
    target = output / "ro-crate-metadata.json"
    target.write_text(
        deterministic_json(
            {"@context": "https://w3id.org/ro/crate/1.2/context", "@graph": graph},
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    return target
