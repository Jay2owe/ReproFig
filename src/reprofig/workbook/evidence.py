"""Aggregate publication evidence embedded in Excel carriers."""

from __future__ import annotations

import os
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Mapping

from ..artifacts import embed_file
from ..schema import DataTable, FigureRecord, sha256_bytes
from ..tables import statistics_csv_bytes
from .models import PublicationDataset


def _version() -> str:
    # Prefer the running source tree. importlib.metadata may describe an older
    # globally installed wheel while tests or integrations import local source.
    try:
        from .. import __version__

        return __version__
    except (ImportError, AttributeError):
        pass
    try:
        return version("reprofig")
    except PackageNotFoundError:
        return "0+local"


def publication_record(
    dataset: PublicationDataset,
    *,
    sheet_map: Mapping[str, str],
) -> FigureRecord:
    tables: list[DataTable] = []
    for table in dataset.tables:
        tables.append(
            DataTable(
                name=sheet_map[str(table.table_id)],
                purpose="publication_source_data",
                sha256=table.sha256,
                row_count=table.row_count,
                column_count=table.column_count,
                columns=list(table.columns),
                contents=table.contents,
                format=table.format,
                newline=table.newline,
                metadata={
                    "publication_table_id": table.table_id,
                    "original_names": sorted(
                        {occurrence.table_name for occurrence in table.occurrences}
                    ),
                    "occurrences": [occurrence.to_dict() for occurrence in table.occurrences],
                },
            )
        )
    statistics = [
        {
            **statistic.normalized,
            "test_id": statistic.test_id,
            "raw_record_json": statistic.normalized.get("raw_record_json"),
        }
        for statistic in dataset.statistics
    ]
    manifest = {
        "schema": dataset.schema,
        "publication_id": dataset.publication_id,
        "logical_fingerprint": dataset.fingerprint(),
        "profile": dataset.profile,
        "statistics_coverage": dataset.statistics_coverage,
        "coverage": dataset.coverage.to_dict(),
        "source_figures": [figure.to_dict() for figure in dataset.figures],
        "sheet_map": dict(sorted(sheet_map.items())),
        "dataset": dataset.evidence_dict(),
    }
    return FigureRecord(
        figure_id=str(dataset.publication_id),
        title="Publication source data workbook",
        original_stem="Publication-source-data",
        distribution_profile=dataset.profile,
        producer={"package": "reprofig", "package_version": _version(), "function": "build_publication_workbook"},
        analysis={"statistics_coverage": dataset.statistics_coverage},
        data_status="complete" if all(table.contents is not None for table in tables) else "incomplete",
        data_tables=tables,
        statistics_status=(
            "not_applicable"
            if dataset.statistics_coverage == "not_applicable"
            else ("complete" if dataset.statistics_coverage != "incomplete" else "incomplete")
        ),
        statistics=statistics,
        statistics_csv_sha256=sha256_bytes(statistics_csv_bytes(statistics)),
        integrity={"publication_fingerprint": dataset.fingerprint()},
        extensions={"publication_workbook": manifest},
    )


def publication_dataset_from_record(record: FigureRecord) -> PublicationDataset:
    extension = record.extensions.get("publication_workbook")
    if not isinstance(extension, dict) or not isinstance(extension.get("dataset"), dict):
        raise ValueError("ReproFig record is not a publication-workbook aggregate record")
    dataset = PublicationDataset.from_dict(extension["dataset"])
    expected = extension.get("visible_logical_fingerprint", extension.get("logical_fingerprint"))
    if dataset.fingerprint() != expected:
        raise ValueError("publication-workbook logical fingerprint mismatch")
    return dataset


def embed_publication_evidence(
    source_workbook: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    dataset: PublicationDataset,
    *,
    sheet_map: Mapping[str, str],
    overwrite: bool = False,
) -> Path:
    target = Path(output_path)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    record = publication_record(dataset, sheet_map=sheet_map)
    return embed_publication_record(
        source_workbook,
        output_path,
        record,
        overwrite=overwrite,
    )


def embed_publication_record(
    source_workbook: str | os.PathLike[str],
    output_path: str | os.PathLike[str],
    record: FigureRecord,
    *,
    overwrite: bool = False,
) -> Path:
    target = Path(output_path)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    return embed_file(
        source_workbook,
        record,
        output_path=output_path,
    )


__all__ = [
    "embed_publication_evidence",
    "embed_publication_record",
    "publication_dataset_from_record",
    "publication_record",
]
