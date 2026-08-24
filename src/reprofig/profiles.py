"""One-way transformations from internal masters to publication profiles."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import PurePath
from typing import Any
from urllib.parse import urlparse

from .schema import DataTable, FigureRecord, SourceReference, SUPPORTED_PROFILES
from .tables import select_table_columns, statistics_csv_bytes, without_contents
from .validation import scrub_private_strings
from .schema import sha256_bytes

_PUBLIC_PRODUCER_FIELDS = {
    "package",
    "package_version",
    "version",
    "function",
    "git_commit",
    "python_version",
    "created_by",
}
_PUBLIC_ANALYSIS_FIELDS = {
    "independent_unit",
    "transformations",
    "missing_or_excluded",
    "method",
    "model",
}


def _approved_for_table(
    table: DataTable,
    safe_columns: Sequence[str] | Mapping[str, Sequence[str]] | None,
) -> list[str]:
    if isinstance(safe_columns, Mapping):
        configured = safe_columns.get(table.name)
        if configured is None and len(safe_columns) == 1 and "*" in safe_columns:
            configured = safe_columns["*"]
        if configured is None:
            configured = []
        return [str(value) for value in configured]
    if safe_columns is not None:
        return [str(value) for value in safe_columns]
    return [column.name for column in table.columns if column.public_state == "safe"]


def _public_names(table: DataTable) -> dict[str, str]:
    return {
        column.name: column.public_name
        for column in table.columns
        if column.public_name and column.public_name != column.name
    }


def _source_key(source: SourceReference) -> list[str]:
    keys = [value for value in (source.source_id, source.role, source.relative_path) if value]
    if source.relative_path:
        keys.append(PurePath(source.relative_path).name)
    return [str(value) for value in keys]


def _public_source(
    source: SourceReference, public_sources: Mapping[str, str] | None
) -> SourceReference:
    approved_uri = None
    for key in _source_key(source):
        if public_sources and key in public_sources:
            approved_uri = str(public_sources[key])
            break
    if approved_uri is None and source.uri:
        parsed = urlparse(source.uri)
        if parsed.scheme in {"http", "https", "doi"}:
            approved_uri = source.uri
    return SourceReference(
        role=source.role,
        uri=approved_uri,
        sha256=source.sha256,
        size_bytes=source.size_bytes,
        source_id=source.source_id,
        metadata={
            key: value
            for key, value in source.metadata.items()
            if key in {"description", "citation", "license"}
        },
    )


def _public_producer(producer: Mapping[str, Any]) -> dict[str, Any]:
    return scrub_private_strings(
        {key: producer[key] for key in _PUBLIC_PRODUCER_FIELDS if key in producer}
    )


def _public_analysis(analysis: Mapping[str, Any]) -> dict[str, Any]:
    return scrub_private_strings(
        {key: analysis[key] for key in _PUBLIC_ANALYSIS_FIELDS if key in analysis}
    )


def derive_profile(
    record: FigureRecord,
    figure_profile: str,
    *,
    safe_columns: Sequence[str] | Mapping[str, Sequence[str]] | None = None,
    public_sources: Mapping[str, str] | None = None,
) -> FigureRecord:
    """Create a one-way master/public/minimal-public record derivative."""

    if figure_profile not in SUPPORTED_PROFILES:
        raise ValueError(f"unknown figure profile {figure_profile!r}")
    allowed = {
        "master": {"master", "public", "minimal_public"},
        "public": {"public", "minimal_public"},
        "minimal_public": {"minimal_public"},
    }
    if figure_profile not in allowed[record.distribution_profile]:
        raise ValueError(
            f"cannot recreate {figure_profile} from reduced {record.distribution_profile} record"
        )
    if figure_profile == "master":
        return FigureRecord.from_dict(record.to_dict())

    selected: list[DataTable] = []
    for table in record.data_tables:
        approved = _approved_for_table(table, safe_columns)
        if table.column_count and not approved:
            raise ValueError(
                f"no public columns were approved for data table {table.name!r}"
            )
        selected.append(
            select_table_columns(table, approved, public_names=_public_names(table))
        )
    if figure_profile == "minimal_public":
        embedded_tables = [without_contents(table) for table in selected]
    else:
        embedded_tables = selected

    reproduction = scrub_private_strings(record.reproduction)
    script = reproduction.get("script") if isinstance(reproduction, dict) else None
    if isinstance(script, str):
        reproduction["script"] = script
    result = FigureRecord(
        schema=record.schema,
        figure_id=record.figure_id,
        created_at=record.created_at,
        title=record.title,
        original_stem=record.original_stem,
        distribution_profile=figure_profile,
        producer=_public_producer(record.producer),
        analysis=_public_analysis(record.analysis),
        data_status=record.data_status,
        data_tables=embedded_tables,
        statistics_status=record.statistics_status,
        statistics=record.statistics,
        statistics_csv_sha256=sha256_bytes(statistics_csv_bytes(record.statistics)),
        sources=[_public_source(source, public_sources) for source in record.sources],
        reproduction=reproduction,
        integrity={
            "derived_from_profile": record.distribution_profile,
            "master_figure_id": record.figure_id,
        },
        extensions=dict(record.extensions),
    )
    return result


def approved_public_tables(
    record: FigureRecord,
    *,
    safe_columns: Sequence[str] | Mapping[str, Sequence[str]] | None,
) -> list[DataTable]:
    """Return public-safe tables even when the SVG profile will omit contents."""

    tables: list[DataTable] = []
    for table in record.data_tables:
        approved = _approved_for_table(table, safe_columns)
        if table.column_count and not approved:
            raise ValueError(
                f"no public columns were approved for data table {table.name!r}"
            )
        tables.append(
            select_table_columns(table, approved, public_names=_public_names(table))
        )
    return tables

