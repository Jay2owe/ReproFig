"""High-level construction, attachment, save, and extraction primitives."""

from __future__ import annotations

import json
import os
import tempfile
import weakref
from contextlib import nullcontext
from pathlib import Path
from threading import RLock
from typing import Any, Mapping, Sequence

from .profiles import derive_profile
from .schema import (
    DataTable,
    FigureRecord,
    SourceReference,
    StatisticalSpecification,
    deterministic_json,
    sha256_bytes,
)
from .svg import embed_record, extract_record as _extract_svg_record
from .tables import safe_filename_token, statistics_csv_bytes, table_from_data
from .naming import (
    export_stem,
    normalize_naming_mode,
    role_filename,
    unique_role_filenames,
)
from .validation import privacy_leaks, scrub_private_strings, validate_svg

_ATTACHMENTS: "weakref.WeakKeyDictionary[Any, dict[str, Any]]" = (
    weakref.WeakKeyDictionary()
)
_ATTACHMENT_LOCK = RLock()


def attach(
    figure: Any,
    *,
    plotted_data: Any | None = None,
    data_tables: Sequence[DataTable] | Mapping[str, Any] | None = None,
    statistics: Sequence[Mapping[str, Any]] | None = None,
    statistical_specifications: (
        Sequence[StatisticalSpecification | Mapping[str, Any]] | None
    ) = None,
    analysis: Mapping[str, Any] | None = None,
    sources: (
        Sequence[SourceReference | Mapping[str, Any] | str | os.PathLike[str]]
        | SourceReference
        | Mapping[str, Any]
        | str
        | os.PathLike[str]
        | None
    ) = None,
    column_classification: Mapping[str, Any] | None = None,
    column_roles: Mapping[str, str] | None = None,
    data_status: str | None = None,
    statistics_status: str | None = None,
    append_plotted_data: bool = False,
) -> None:
    """Attach package-supplied scientific meaning to a live figure weakly."""

    with _ATTACHMENT_LOCK:
        current = dict(_ATTACHMENTS.get(figure, {}))
        if plotted_data is not None:
            existing = current.get("plotted_data")
            if append_plotted_data and existing is not None:
                try:
                    import pandas as pd

                    plotted_data = pd.concat(
                        [existing, plotted_data], ignore_index=True
                    )
                except Exception:
                    try:
                        plotted_data = list(existing) + list(plotted_data)
                    except Exception:
                        pass
            current["plotted_data"] = plotted_data
        if data_tables is not None:
            current["data_tables"] = data_tables
        if statistics is not None:
            current.setdefault("statistics", []).extend(list(statistics))
        if statistical_specifications is not None:
            current.setdefault("statistical_specifications", []).extend(
                list(statistical_specifications)
            )
        if analysis is not None:
            merged = dict(current.get("analysis") or {})
            merged.update(dict(analysis))
            current["analysis"] = merged
        if sources is not None:
            current["sources"] = _source_values(sources)
        if column_classification is not None:
            current["column_classification"] = dict(column_classification)
        if column_roles is not None:
            current["column_roles"] = dict(column_roles)
        if data_status is not None:
            current["data_status"] = data_status
        if statistics_status is not None:
            current["statistics_status"] = statistics_status
        _ATTACHMENTS[figure] = current


def attachment_for(figure: Any) -> dict[str, Any]:
    with _ATTACHMENT_LOCK:
        try:
            return dict(_ATTACHMENTS.get(figure, {}))
        except TypeError:
            # Plotly Figure objects are intentionally unhashable and therefore
            # cannot participate in the optional weak attachment cache.
            return {}


def detach(figure: Any) -> dict[str, Any]:
    with _ATTACHMENT_LOCK:
        try:
            return dict(_ATTACHMENTS.pop(figure, {}))
        except TypeError:
            return {}


def _source_values(
    sources: (
        Sequence[SourceReference | Mapping[str, Any] | str | os.PathLike[str]]
        | SourceReference
        | Mapping[str, Any]
        | str
        | os.PathLike[str]
    ),
) -> list[SourceReference | Mapping[str, Any] | str | os.PathLike[str]]:
    if isinstance(sources, (SourceReference, Mapping, str, os.PathLike)):
        return [sources]
    return list(sources)


def _coerce_sources(
    sources: (
        Sequence[SourceReference | Mapping[str, Any] | str | os.PathLike[str]]
        | SourceReference
        | Mapping[str, Any]
        | str
        | os.PathLike[str]
        | None
    ),
    *,
    project_root: str | os.PathLike[str] | None = None,
) -> list[SourceReference]:
    values = _source_values(sources) if sources is not None else []
    coerced: list[SourceReference] = []
    for value in values:
        if isinstance(value, SourceReference):
            coerced.append(value)
        elif isinstance(value, (str, os.PathLike)):
            from .sources import source_reference

            coerced.append(
                source_reference(
                    value,
                    role="raw_user_input",
                    project_root=project_root,
                )
            )
        else:
            coerced.append(SourceReference.from_dict(value))
    cleaned: list[SourceReference] = []
    for source in coerced:
        relative_path = source.relative_path
        if relative_path and privacy_leaks(relative_path):
            relative_path = relative_path.replace("\\", "/").rsplit("/", 1)[-1]
        uri = source.uri
        if uri and privacy_leaks(uri):
            uri = None
        cleaned.append(
            SourceReference(
                role=source.role,
                relative_path=relative_path,
                uri=uri,
                sha256=source.sha256,
                size_bytes=source.size_bytes,
                modified_at=source.modified_at,
                source_id=source.source_id,
                metadata=dict(scrub_private_strings(source.metadata)),
            )
        )
    return cleaned


def _with_statistical_specifications(
    extensions: Mapping[str, Any] | None,
    specifications: Sequence[StatisticalSpecification],
) -> dict[str, Any]:
    result = dict(extensions or {})
    if not specifications:
        return result
    proof = dict(result.get("proof") or {})
    existing = list(proof.get("statistical_specifications") or [])
    existing.extend(value.to_dict() for value in specifications)
    proof["statistical_specifications"] = existing
    result["proof"] = proof
    return result


def _coerce_statistical_specifications(
    values: Sequence[StatisticalSpecification | Mapping[str, Any]] | None,
) -> list[StatisticalSpecification]:
    return [
        (
            value
            if isinstance(value, StatisticalSpecification)
            else StatisticalSpecification.from_dict(value)
        )
        for value in (values or [])
    ]


def _enrich_statistics(
    statistics: Sequence[Mapping[str, Any]] | None,
    specifications: Sequence[StatisticalSpecification],
) -> list[dict[str, Any]]:
    records = [dict(item) for item in (statistics or [])]
    by_id = {
        str(record.get("statistic_id")): record
        for record in records
        if record.get("statistic_id")
    }
    for specification in specifications:
        identity = str(specification.statistic_id)
        record = by_id.get(identity)
        if record is None and len(records) == 1 and not records[0].get("statistic_id"):
            record = records[0]
            record["statistic_id"] = identity
            by_id[identity] = record
        if record is None:
            record = {"statistic_id": identity}
            records.append(record)
            by_id[identity] = record
        record.setdefault("algorithm_id", specification.algorithm_id)
        for field, value in (
            ("inputs_json", specification.inputs),
            ("parameters_json", specification.parameters),
            ("expected_json", specification.expected),
            ("display_json", specification.display),
            ("tolerances_json", specification.tolerances),
        ):
            record.setdefault(field, deterministic_json(value))
    return records


def _coerce_tables(
    *,
    plotted_data: Any | None,
    data_tables: Sequence[DataTable] | Mapping[str, Any] | None,
    classification: Mapping[str, Any] | None,
    roles: Mapping[str, str] | None,
) -> list[DataTable]:
    tables: list[DataTable] = []
    if plotted_data is not None:
        tables.append(
            table_from_data(
                plotted_data,
                name="plotted_data",
                purpose="plot_and_statistics",
                classification=classification,
                roles=roles,
            )
        )
    if isinstance(data_tables, Mapping):
        for name, value in data_tables.items():
            if isinstance(value, DataTable):
                table = value
            else:
                table = table_from_data(
                    value,
                    name=str(name),
                    purpose="analysis",
                    classification=classification,
                    roles=roles,
                )
            tables.append(table)
    elif data_tables:
        tables.extend(
            value if isinstance(value, DataTable) else DataTable.from_dict(value)
            for value in data_tables
        )
    names = [table.name for table in tables]
    if len(names) != len(set(names)):
        raise ValueError(f"duplicate data table names: {names}")
    return tables


def build_record(
    *,
    title: str | None = None,
    original_stem: str | None = None,
    producer: Mapping[str, Any] | None = None,
    analysis: Mapping[str, Any] | None = None,
    plotted_data: Any | None = None,
    data_tables: Sequence[DataTable] | Mapping[str, Any] | None = None,
    statistics: Sequence[Mapping[str, Any]] | None = None,
    statistical_specifications: (
        Sequence[StatisticalSpecification | Mapping[str, Any]] | None
    ) = None,
    sources: (
        Sequence[SourceReference | Mapping[str, Any] | str | os.PathLike[str]]
        | SourceReference
        | Mapping[str, Any]
        | str
        | os.PathLike[str]
        | None
    ) = None,
    reproduction: Mapping[str, Any] | None = None,
    project_root: str | os.PathLike[str] | None = None,
    column_classification: Mapping[str, Any] | None = None,
    column_roles: Mapping[str, str] | None = None,
    data_status: str | None = None,
    statistics_status: str | None = None,
    extensions: Mapping[str, Any] | None = None,
) -> FigureRecord:
    tables = _coerce_tables(
        plotted_data=plotted_data,
        data_tables=data_tables,
        classification=column_classification,
        roles=column_roles,
    )
    specifications = _coerce_statistical_specifications(statistical_specifications)
    statistic_records = [
        dict(scrub_private_strings(item))
        for item in _enrich_statistics(statistics, specifications)
    ]
    for table in tables:
        if table.contents is not None:
            leaks = privacy_leaks(table.contents)
            if leaks:
                codes = ", ".join(sorted({code for code, _excerpt in leaks}))
                raise ValueError(
                    f"data table {table.name!r} contains private material: {codes}"
                )
        table.metadata = dict(scrub_private_strings(table.metadata))
    if data_status is None:
        data_status = "complete" if tables else "incomplete"
    if statistics_status is None:
        statistics_status = "complete" if statistic_records else "incomplete"
    statistics_csv = statistics_csv_bytes(statistic_records)
    return FigureRecord(
        title=title,
        original_stem=original_stem,
        producer=dict(scrub_private_strings(dict(producer or {}))),
        analysis=dict(scrub_private_strings(dict(analysis or {}))),
        data_status=data_status,
        data_tables=tables,
        statistics_status=statistics_status,
        statistics=statistic_records,
        statistics_csv_sha256=sha256_bytes(statistics_csv),
        sources=_coerce_sources(sources, project_root=project_root),
        reproduction=dict(scrub_private_strings(dict(reproduction or {}))),
        extensions=dict(
            scrub_private_strings(
                _with_statistical_specifications(
                    extensions,
                    specifications,
                )
            )
        ),
    )


def build_record_for_figure(
    figure: Any,
    *,
    title: str | None = None,
    original_stem: str | None = None,
    producer: Mapping[str, Any] | None = None,
    analysis: Mapping[str, Any] | None = None,
    plotted_data: Any | None = None,
    data_tables: Sequence[DataTable] | Mapping[str, Any] | None = None,
    statistics: Sequence[Mapping[str, Any]] | None = None,
    statistical_specifications: (
        Sequence[StatisticalSpecification | Mapping[str, Any]] | None
    ) = None,
    sources: (
        Sequence[SourceReference | Mapping[str, Any] | str | os.PathLike[str]]
        | SourceReference
        | Mapping[str, Any]
        | str
        | os.PathLike[str]
        | None
    ) = None,
    reproduction: Mapping[str, Any] | None = None,
    project_root: str | os.PathLike[str] | None = None,
    column_classification: Mapping[str, Any] | None = None,
    column_roles: Mapping[str, str] | None = None,
    data_status: str | None = None,
    statistics_status: str | None = None,
    extensions: Mapping[str, Any] | None = None,
) -> FigureRecord:
    attached = attachment_for(figure)
    merged_analysis = dict(attached.get("analysis") or {})
    merged_analysis.update(dict(analysis or {}))
    attached_stats = list(attached.get("statistics") or [])
    if statistics is not None:
        attached_stats.extend(statistics)
    attached_specs = list(attached.get("statistical_specifications") or [])
    if statistical_specifications is not None:
        attached_specs.extend(statistical_specifications)
    return build_record(
        title=title,
        original_stem=original_stem,
        producer=producer,
        analysis=merged_analysis,
        plotted_data=(
            plotted_data if plotted_data is not None else attached.get("plotted_data")
        ),
        data_tables=(
            data_tables if data_tables is not None else attached.get("data_tables")
        ),
        statistics=(
            attached_stats if (statistics is not None or attached_stats) else None
        ),
        statistical_specifications=(
            attached_specs
            if statistical_specifications is not None or attached_specs
            else None
        ),
        sources=sources if sources is not None else attached.get("sources"),
        reproduction=reproduction,
        project_root=project_root,
        column_classification=(
            column_classification
            if column_classification is not None
            else attached.get("column_classification")
        ),
        column_roles=(
            column_roles if column_roles is not None else attached.get("column_roles")
        ),
        data_status=(
            data_status if data_status is not None else attached.get("data_status")
        ),
        statistics_status=(
            statistics_status
            if statistics_status is not None
            else attached.get("statistics_status")
        ),
        extensions=extensions,
    )


def _metadata_summary(record: FigureRecord) -> dict[str, str]:
    producer = record.producer
    description = {
        "schema": record.schema,
        "figure_id": record.figure_id,
        "distribution_profile": record.distribution_profile,
        "producer": {
            key: producer[key]
            for key in ("package", "package_version", "version", "function")
            if key in producer
        },
    }
    metadata = {
        "Creator": "ReproFig",
        "Description": json.dumps(description, ensure_ascii=False, sort_keys=True),
    }
    if record.title:
        metadata["Title"] = record.title
    return metadata


def write_companion_tables(
    record: FigureRecord,
    svg_path: str | os.PathLike[str],
    *,
    naming: str = "readable",
) -> list[Path]:
    path = Path(svg_path)
    mode = normalize_naming_mode(naming)
    stem = export_stem(artifact=path, naming=mode) if mode == "readable" else path.stem
    outputs: list[Path] = []
    readable_names = (
        unique_role_filenames(
            stem,
            [table.name for table in record.data_tables],
            "csv",
            naming=mode,
        )
        if mode == "readable"
        else []
    )
    for index, table in enumerate(record.data_tables):
        if table.contents is None:
            continue
        if mode == "readable":
            output = path.with_name(readable_names[index])
        else:
            suffix = "source-data" if index == 0 else safe_filename_token(table.name)
            output = path.with_name(f"{path.stem}.{suffix}.csv")
        if output in outputs:
            raise ValueError(f"companion table filenames collide at {output.name}")
        output.write_bytes(table.contents.encode("utf-8"))
        outputs.append(output)
    stats = path.with_name(role_filename(stem, "statistics", "csv", naming=mode))
    if stats in outputs:
        raise ValueError(f"companion table filenames collide at {stats.name}")
    stats.write_bytes(statistics_csv_bytes(record.statistics))
    outputs.append(stats)
    return outputs


def save_svg(
    figure: Any,
    path: str | os.PathLike[str],
    *,
    record: FigureRecord | None = None,
    title: str | None = None,
    producer: Mapping[str, Any] | None = None,
    analysis: Mapping[str, Any] | None = None,
    plotted_data: Any | None = None,
    data_tables: Sequence[DataTable] | Mapping[str, Any] | None = None,
    statistics: Sequence[Mapping[str, Any]] | None = None,
    sources: Sequence[SourceReference | Mapping[str, Any]] | None = None,
    reproduction: Mapping[str, Any] | None = None,
    column_classification: Mapping[str, Any] | None = None,
    column_roles: Mapping[str, str] | None = None,
    data_status: str | None = None,
    statistics_status: str | None = None,
    figure_profile: str = "master",
    safe_columns: Sequence[str] | Mapping[str, Sequence[str]] | None = None,
    public_sources: Mapping[str, str] | None = None,
    write_companion_csv: bool = False,
    companion_naming: str = "readable",
    savefig_kwargs: Mapping[str, Any] | None = None,
) -> FigureRecord:
    """Save a Matplotlib-like figure and embed its complete record atomically."""

    target = Path(path)
    if target.suffix.lower() != ".svg":
        raise ValueError("ReproFig save_svg requires an .svg path")
    target.parent.mkdir(parents=True, exist_ok=True)
    if record is None:
        record = build_record_for_figure(
            figure,
            title=title or target.stem,
            original_stem=target.stem,
            producer=producer,
            analysis=analysis,
            plotted_data=plotted_data,
            data_tables=data_tables,
            statistics=statistics,
            sources=sources,
            reproduction=reproduction,
            column_classification=column_classification,
            column_roles=column_roles,
            data_status=data_status,
            statistics_status=statistics_status,
        )
    final_record = derive_profile(
        record,
        figure_profile,
        safe_columns=safe_columns,
        public_sources=public_sources,
    )
    companion_record = final_record
    if figure_profile == "minimal_public":
        companion_record = derive_profile(
            record,
            "public",
            safe_columns=safe_columns,
            public_sources=public_sources,
        )
    descriptor, temporary_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.stem}.", suffix=".svg"
    )
    os.close(descriptor)
    temporary = Path(temporary_name)
    try:
        kwargs = dict(savefig_kwargs or {})
        existing_metadata = dict(kwargs.pop("metadata", {}) or {})
        existing_metadata.update(_metadata_summary(final_record))
        try:
            import matplotlib

            style_context = matplotlib.rc_context(
                {"svg.fonttype": "none", "mathtext.default": "regular"}
            )
        except Exception:
            style_context = nullcontext()
        with style_context:
            figure.savefig(
                temporary, format="svg", metadata=existing_metadata, **kwargs
            )
        embed_record(temporary, final_record)
        report = validate_svg(
            temporary,
            expected_profile=figure_profile,
            require_complete=False,
            public_safety=figure_profile != "master",
        )
        if not report.valid:
            raise ValueError(
                "saved SVG failed validation: "
                + "; ".join(
                    issue.message
                    for issue in report.issues
                    if issue.severity == "error"
                )
            )
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink()
        except OSError:
            pass
    if write_companion_csv:
        write_companion_tables(
            companion_record,
            target,
            naming=companion_naming,
        )
    return final_record


def read_svg(path: str | os.PathLike[str]) -> FigureRecord:
    return _extract_svg_record(path)


# Format-neutral APIs are imported last so their Matplotlib save path can reuse
# the record-building functions above without an import cycle.
from .artifacts import (  # noqa: E402
    ArtifactPublicationResult,
    bundle_artifacts,
    embed_file,
    extract_artifact,
    extract_record,
    extract_records,
    formats,
    inspect_artifact,
    publish_artifacts,
    save_figure,
    scan_artifacts,
    validate_artifact,
)

from .workbook.api import (  # noqa: E402
    PublicationWorkbookResult,
    build_publication_workbook,
)
from .evidence import (  # noqa: E402
    EvidenceGraph,
    attach_evidence_graph,
    calculate_evidence_root,
    graph_from_record,
    refresh_evidence_graph,
)
from .verification import (  # noqa: E402
    ProofCheck,
    ProofVerificationReport,
    verify_artifact as verify_proof,
)
from .reproduction import (  # noqa: E402
    FigureReproductionReport,
    ReproductionPolicy,
    reproduce_figure,
    verify_figure_reproduction,
)
from .render import bind_artist, capture_matplotlib  # noqa: E402
from .render.reference import refresh_visual_reference  # noqa: E402
from .crypto.encryption import (
    decrypt_record,
    decrypt_sections,
    encrypt_sections,
)  # noqa: E402
from .crypto.signatures import sign_record, verify_record_signatures  # noqa: E402
from .crypto.attestations import attest_report  # noqa: E402
from .crypto.trust import (  # noqa: E402
    TrustEntry,
    TrustPolicy,
    TrustStore,
    evaluate_record_trust,
)
from .policy import apply_artifact_policy  # noqa: E402
