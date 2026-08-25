"""Collect canonical publication evidence from ReproFig carriers."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Sequence

from ..artifacts import artifact_paths, extract_records
from ..schema import FigureRecord
from ..validation import ValidationReport, validate_record
from .models import (
    PublicationDataset,
    PublicationFigure,
    PublicationStatistic,
    PublicationTable,
    StatisticOccurrence,
    TableOccurrence,
    VerificationRow,
)


@dataclass(frozen=True)
class ArtifactOccurrence:
    """Runtime-only location of one record; absolute paths are never serialized."""

    path: Path
    carrier_format: str
    figure_id: str
    record_sha256: str


@dataclass
class CollectedPublication:
    dataset: PublicationDataset
    records: list[FigureRecord]
    artifact_occurrences: list[ArtifactOccurrence] = field(default_factory=list)
    reports: list[ValidationReport] = field(default_factory=list)


def collect_records(
    records_with_sources: Sequence[tuple[FigureRecord, Path, str]],
    *,
    publication_id: str | None = None,
    require_complete: bool = True,
) -> CollectedPublication:
    """Collect already-extracted records into one deterministic logical dataset."""

    errors: list[str] = []
    reports: list[ValidationReport] = []
    figures: dict[str, tuple[FigureRecord, str, set[str]]] = {}
    occurrences: list[ArtifactOccurrence] = []

    for record, path, carrier_format in records_with_sources:
        report = validate_record(record, require_complete=require_complete)
        reports.append(report)
        if not report.valid:
            messages = "; ".join(issue.message for issue in report.issues)
            errors.append(f"{path.name}: figure {record.figure_id}: {messages}")
            continue
        fingerprint = record.fingerprint()
        label = path.name
        previous = figures.get(record.figure_id)
        if previous and previous[1] != fingerprint:
            errors.append(
                f"{label}: figure_id {record.figure_id!r} conflicts with another record "
                f"({previous[1]} != {fingerprint})"
            )
            continue
        if previous:
            previous[2].add(label)
        else:
            figures[record.figure_id] = (record, fingerprint, {label})
        occurrences.append(
            ArtifactOccurrence(path.resolve(), carrier_format, record.figure_id, fingerprint)
        )

    if errors:
        raise ValueError("publication collection failed:\n- " + "\n- ".join(sorted(errors)))

    publication_figures: list[PublicationFigure] = []
    tables: dict[str, PublicationTable] = {}
    raw_statistics: list[PublicationStatistic] = []
    canonical_records: list[FigureRecord] = []

    for display_order, figure_id in enumerate(sorted(figures), start=1):
        record, fingerprint, labels = figures[figure_id]
        canonical_records.append(record)
        publication_figures.append(
            PublicationFigure(
                figure_id=figure_id,
                figure_record_sha256=fingerprint,
                display_order=display_order,
                schema=record.schema,
                profile=record.distribution_profile,
                title=record.title,
                original_stem=record.original_stem,
                source_label=sorted(labels)[0],
                metadata={
                    "carrier_labels": sorted(labels),
                    "statistics_status": record.statistics_status,
                    "data_status": record.data_status,
                },
            )
        )
        for table_index, table in enumerate(record.data_tables):
            occurrence = TableOccurrence(
                figure_id=figure_id,
                figure_record_sha256=fingerprint,
                table_name=table.name,
                table_index=table_index,
                metadata={"purpose": table.purpose},
            )
            existing = tables.get(table.sha256)
            if existing is None:
                tables[table.sha256] = PublicationTable(
                    sha256=table.sha256,
                    name=table.name,
                    purpose=table.purpose,
                    row_count=table.row_count,
                    column_count=table.column_count,
                    columns=list(table.columns),
                    occurrences=[occurrence],
                    contents=table.contents,
                    format=table.format,
                    newline=table.newline,
                    metadata=dict(table.metadata),
                )
            else:
                if existing.contents != table.contents:
                    raise ValueError(
                        f"table {table.name!r} in figure {figure_id} shares SHA-256 "
                        f"{table.sha256} but not exact bytes"
                    )
                existing.occurrences.append(occurrence)
                existing.occurrences.sort(key=lambda value: value.sort_key())

        for statistic_index, statistic in enumerate(record.statistics):
            explicit_id = statistic.get("test_id") or statistic.get("id")
            raw_statistics.append(
                PublicationStatistic(
                    test_id=f"figure-stat:{figure_id}:{statistic_index}",
                    raw_record=dict(statistic),
                    occurrences=[
                        StatisticOccurrence(
                            figure_id=figure_id,
                            figure_record_sha256=fingerprint,
                            statistic_index=statistic_index,
                            displayed=bool(statistic.get("displayed", True)),
                            metadata={"panel_id": statistic.get("panel_id")},
                        )
                    ],
                    displayed=bool(statistic.get("displayed", True)),
                    source="figure",
                    metadata={
                        "declared_test_id": str(explicit_id) if explicit_id else None
                    },
                )
            )

    verification = [
        VerificationRow(
            subject_id=figure.figure_id,
            status="pass",
            check="record_integrity",
            message="Source figure record and embedded table hashes validated.",
        )
        for figure in publication_figures
    ]
    dataset = PublicationDataset(
        publication_id=publication_id,
        profile=(publication_figures[0].profile if publication_figures else "master"),
        figures=publication_figures,
        tables=list(tables.values()),
        statistics=raw_statistics,
        verification=verification,
        statistics_coverage="not_applicable" if not raw_statistics else "incomplete",
    )
    dataset_errors = dataset.validate()
    if dataset_errors:
        raise ValueError("invalid publication dataset:\n- " + "\n- ".join(dataset_errors))
    return CollectedPublication(dataset, canonical_records, occurrences, reports)


def collect_publication(
    artifacts: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    *,
    publication_id: str | None = None,
    require_complete: bool = True,
    transform: Callable[[FigureRecord], FigureRecord] | None = None,
) -> CollectedPublication:
    """Extract, validate, deduplicate and index one mixed carrier batch."""

    extracted: list[tuple[FigureRecord, Path, str]] = []
    errors: list[str] = []
    for path in artifact_paths(artifacts):
        try:
            records, manifest = extract_records(path, include_manifest=True)
            for record in records:
                extracted.append((transform(record) if transform else record, path, manifest.format))
        except Exception as exc:
            errors.append(f"{path.name}: {exc}")
    if errors:
        raise ValueError("publication collection failed:\n- " + "\n- ".join(sorted(errors)))
    return collect_records(
        extracted,
        publication_id=publication_id,
        require_complete=require_complete,
    )


__all__ = [
    "ArtifactOccurrence",
    "CollectedPublication",
    "collect_publication",
    "collect_records",
]
