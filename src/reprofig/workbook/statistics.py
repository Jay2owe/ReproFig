"""Canonical publication statistics ledger normalization and reconciliation."""

from __future__ import annotations

import csv
import io
import json
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..schema import deterministic_json, sha256_bytes
from .models import (
    CoverageDeclaration,
    PublicationDataset,
    PublicationStatistic,
    StatisticOccurrence,
    TestFamily,
)

LEDGER_SCHEMA = "reprofig-statistics-ledger/1"

NORMALIZED_COLUMNS = (
    "test_id", "analysis_id", "figure_ids", "panel_ids", "claim_ids", "displayed",
    "outcome", "group_a", "group_b", "unit_of_analysis", "n_total", "n_group_a",
    "n_group_b", "n_pairs", "n_excluded", "test_name", "test_version", "paired",
    "alternative", "alpha", "statistic_name", "statistic_exact", "statistic_numeric",
    "df_exact", "df1_exact", "df2_exact", "p_raw_exact", "p_raw_numeric",
    "p_adjusted_exact", "p_adjusted_numeric", "p_displayed", "correction",
    "correction_family_id", "ci_level", "ci_low_exact", "ci_high_exact", "ci_method",
    "effect_size_name", "effect_size_exact", "effect_ci_low_exact",
    "effect_ci_high_exact", "missing_policy", "model_formula", "covariates_json",
    "random_seed", "resamples", "producer_package", "producer_version", "source",
    "reconciliation_status", "raw_record_json",
)

_ALIASES: dict[str, tuple[str, ...]] = {
    "analysis_id": ("analysis_id",),
    "outcome": ("outcome", "dependent_variable", "variable"),
    "group_a": ("group_a", "group1", "control"),
    "group_b": ("group_b", "group2", "treatment"),
    "unit_of_analysis": ("unit_of_analysis", "unit"),
    "n_total": ("n_total", "n"),
    "n_group_a": ("n_group_a", "n_a", "n1"),
    "n_group_b": ("n_group_b", "n_b", "n2"),
    "n_pairs": ("n_pairs",),
    "n_excluded": ("n_excluded", "excluded_n"),
    "test_name": ("test_name", "test", "method", "name"),
    "test_version": ("test_version", "algorithm_version"),
    "paired": ("paired",),
    "alternative": ("alternative", "tail", "tailedness"),
    "alpha": ("alpha",),
    "statistic_name": ("statistic_name", "stat_name"),
    "statistic_exact": ("statistic_exact", "statistic", "stat", "t", "u", "f", "h"),
    "df_exact": ("df_exact", "df", "degrees_of_freedom"),
    "df1_exact": ("df1_exact", "df1"),
    "df2_exact": ("df2_exact", "df2"),
    "p_raw_exact": ("p_raw_exact", "p_raw", "p", "pvalue", "p_value"),
    "p_adjusted_exact": ("p_adjusted_exact", "p_adjusted", "p_adj", "q", "q_value"),
    "p_displayed": ("p_displayed", "display_p", "annotation", "label"),
    "correction": ("correction", "adjustment"),
    "correction_family_id": ("correction_family_id", "family_id"),
    "ci_level": ("ci_level", "confidence_level"),
    "ci_low_exact": ("ci_low_exact", "ci_low", "confidence_low"),
    "ci_high_exact": ("ci_high_exact", "ci_high", "confidence_high"),
    "ci_method": ("ci_method",),
    "effect_size_name": ("effect_size_name", "effect_name"),
    "effect_size_exact": ("effect_size_exact", "effect_size", "effect"),
    "effect_ci_low_exact": ("effect_ci_low_exact", "effect_ci_low"),
    "effect_ci_high_exact": ("effect_ci_high_exact", "effect_ci_high"),
    "missing_policy": ("missing_policy", "nan_policy"),
    "model_formula": ("model_formula", "formula"),
    "random_seed": ("random_seed", "seed"),
    "resamples": ("resamples", "n_resamples", "iterations"),
    "producer_package": ("producer_package", "package"),
    "producer_version": ("producer_version", "package_version", "version"),
}


@dataclass
class ImportedLedger:
    statistics: list[dict[str, Any]] = field(default_factory=list)
    families: list[TestFamily] = field(default_factory=list)
    analysis_id: str | None = None
    coverage: str = "incomplete"
    ledger_sha256: str | None = None
    declaration_source: str | None = None


def _flatten(value: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, item in value.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(item, Mapping):
            result.update(_flatten(item, name))
        else:
            result[name] = item
            result.setdefault(str(key), item)
    return result


def _first(flat: Mapping[str, Any], aliases: Sequence[str]) -> Any:
    for alias in aliases:
        if alias in flat and flat[alias] not in (None, ""):
            return flat[alias]
    return None


def _exact(value: Any) -> str | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _number(value: Any) -> int | float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        result = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    if not math.isfinite(result):
        return None
    return int(result) if result.is_integer() and abs(result) <= 2**53 else result


def normalize_statistic(
    record: Mapping[str, Any],
    *,
    test_id: str,
    source: str,
    occurrences: Sequence[StatisticOccurrence] = (),
    displayed: bool = True,
    analysis_id: str | None = None,
) -> PublicationStatistic:
    """Normalize known fields without discarding or guessing unknown fields."""

    raw = dict(record)
    flat = _flatten(raw)
    normalized: dict[str, Any] = {
        "test_id": test_id,
        "analysis_id": analysis_id or _first(flat, _ALIASES["analysis_id"]),
        "figure_ids": sorted({value.figure_id for value in occurrences}),
        "panel_ids": sorted(
            {
                str(value.metadata.get("panel_id"))
                for value in occurrences
                if value.metadata.get("panel_id") not in (None, "")
            }
        ),
        "claim_ids": sorted(str(value) for value in raw.get("claim_ids", []) or []),
        "displayed": bool(displayed),
        "source": source,
        "reconciliation_status": "unreconciled",
        "raw_record_json": deterministic_json(raw),
    }
    for field_name, aliases in _ALIASES.items():
        if field_name in {"analysis_id"}:
            continue
        value = _first(flat, aliases)
        if field_name.endswith("_exact"):
            normalized[field_name] = _exact(value)
        else:
            normalized[field_name] = value
    if "covariates" in raw:
        normalized["covariates_json"] = deterministic_json(raw["covariates"])
    else:
        normalized["covariates_json"] = _exact(flat.get("covariates_json"))
    for exact_name, numeric_name in (
        ("statistic_exact", "statistic_numeric"),
        ("p_raw_exact", "p_raw_numeric"),
        ("p_adjusted_exact", "p_adjusted_numeric"),
    ):
        normalized[numeric_name] = _number(normalized.get(exact_name))
    normalized = {name: normalized.get(name) for name in NORMALIZED_COLUMNS}
    return PublicationStatistic(
        test_id=test_id,
        raw_record=raw,
        occurrences=list(occurrences),
        displayed=displayed,
        source=source,
        normalized=normalized,
        family_id=normalized.get("correction_family_id"),
    )


def import_statistics_ledger(
    value: str | os.PathLike[str] | Sequence[Mapping[str, Any]] | None,
    *,
    declare_complete: bool = False,
) -> ImportedLedger:
    if value is None:
        if declare_complete:
            raise ValueError("declare_ledger_complete requires a statistics ledger")
        return ImportedLedger()
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, os.PathLike)):
        rows = [dict(item) for item in value]
        raw = deterministic_json(rows).encode("utf-8")
        return ImportedLedger(
            statistics=rows,
            coverage="analysis_complete" if declare_complete else "incomplete",
            ledger_sha256=sha256_bytes(raw),
            declaration_source="caller" if declare_complete else None,
        )

    path = Path(value)
    raw = path.read_bytes()
    if path.suffix.lower() == ".csv":
        rows = list(csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline="")))
        if any(not (row.get("test_id") or "").strip() for row in rows):
            raise ValueError("every CSV statistics-ledger row requires a non-empty test_id")
        return ImportedLedger(
            statistics=[dict(row) for row in rows],
            coverage="analysis_complete" if declare_complete else "incomplete",
            ledger_sha256=sha256_bytes(raw),
            declaration_source="caller" if declare_complete else None,
        )

    parsed = json.loads(raw)
    if isinstance(parsed, list):
        parsed = {"statistics": parsed}
    if not isinstance(parsed, dict):
        raise ValueError("statistics ledger JSON must contain an object or list")
    schema = parsed.get("schema")
    if schema not in (None, LEDGER_SCHEMA):
        raise ValueError(f"unsupported statistics ledger schema {schema!r}")
    declared = parsed.get("coverage") in {"complete", "analysis_complete"}
    families = [TestFamily.from_dict(item) for item in parsed.get("families", [])]
    return ImportedLedger(
        statistics=[dict(item) for item in parsed.get("statistics", [])],
        families=families,
        analysis_id=parsed.get("analysis_id"),
        coverage="analysis_complete" if (declared or declare_complete) else "incomplete",
        ledger_sha256=sha256_bytes(raw),
        declaration_source="ledger" if declared else ("caller" if declare_complete else None),
    )


def _scientific_projection(statistic: PublicationStatistic) -> dict[str, Any]:
    ignored = {"figure_ids", "panel_ids", "displayed", "source", "reconciliation_status", "raw_record_json"}
    return {
        key: value
        for key, value in statistic.normalized.items()
        if key not in ignored and value not in (None, "", [], {})
    }


def _scientific_conflicts(
    left: PublicationStatistic, right: PublicationStatistic
) -> list[str]:
    left_values = _scientific_projection(left)
    right_values = _scientific_projection(right)
    return sorted(
        key
        for key in left_values.keys() & right_values.keys()
        if left_values[key] != right_values[key]
    )


def reconcile_statistics(
    dataset: PublicationDataset,
    ledger: ImportedLedger | None = None,
) -> PublicationDataset:
    """Merge shared test identifiers and retain unplotted ledger tests."""

    ledger = ledger or ImportedLedger()
    merged: dict[str, PublicationStatistic] = {}

    for item in dataset.statistics:
        declared = item.metadata.get("declared_test_id")
        test_id = str(declared or item.test_id)
        normalized = normalize_statistic(
            item.raw_record,
            test_id=test_id,
            source="figure",
            occurrences=item.occurrences,
            displayed=item.displayed,
        )
        existing = merged.get(test_id)
        if existing is None:
            merged[test_id] = normalized
        else:
            conflicts = _scientific_conflicts(existing, normalized)
            if conflicts:
                raise ValueError(
                    f"conflicting scientific values for test_id {test_id!r}: "
                    + ", ".join(conflicts)
                )
            existing.occurrences.extend(normalized.occurrences)
            existing.occurrences.sort(key=lambda value: value.sort_key())

    ledger_ids: set[str] = set()
    for row in ledger.statistics:
        test_id = str(row.get("test_id") or "").strip()
        if not test_id:
            raise ValueError("every experiment-ledger statistic requires test_id")
        if test_id in ledger_ids:
            raise ValueError(f"duplicate test_id in experiment ledger: {test_id}")
        ledger_ids.add(test_id)
        imported = normalize_statistic(
            row,
            test_id=test_id,
            source="experiment_ledger",
            displayed=False,
            analysis_id=ledger.analysis_id,
        )
        existing = merged.get(test_id)
        if existing is None:
            imported.normalized["reconciliation_status"] = "ledger_only"
            merged[test_id] = imported
        else:
            conflicts = _scientific_conflicts(existing, imported)
            if conflicts:
                raise ValueError(
                    f"figure and experiment ledger disagree for test_id {test_id!r}: "
                    + ", ".join(conflicts)
                )
            existing.source = "both"
            existing.raw_record = imported.raw_record
            existing.normalized.update(imported.normalized)
            existing.normalized["figure_ids"] = sorted(
                {occurrence.figure_id for occurrence in existing.occurrences}
            )
            existing.normalized["panel_ids"] = sorted(
                {
                    str(occurrence.metadata.get("panel_id"))
                    for occurrence in existing.occurrences
                    if occurrence.metadata.get("panel_id") not in (None, "")
                }
            )
            existing.normalized["displayed"] = True
            existing.normalized["source"] = "both"
            existing.normalized["reconciliation_status"] = "matched"

    if ledger.coverage == "analysis_complete":
        missing = sorted(
            test_id for test_id, item in merged.items() if item.displayed and test_id not in ledger_ids
        )
        if missing:
            raise ValueError(
                "declared-complete experiment ledger is missing displayed tests: "
                + ", ".join(missing)
            )

    figure_statuses = {
        str(figure.metadata.get("statistics_status", "incomplete"))
        for figure in dataset.figures
    }
    if ledger.coverage == "analysis_complete":
        coverage = "analysis_complete"
    elif not merged and figure_statuses <= {"not_applicable", "complete"}:
        coverage = "not_applicable"
    elif figure_statuses and figure_statuses <= {"complete", "not_applicable"}:
        coverage = "figure_complete"
    else:
        coverage = "incomplete"

    dataset.statistics = sorted(merged.values(), key=lambda value: value.test_id or "")
    dataset.test_families = sorted(ledger.families, key=lambda value: value.family_id or "")
    dataset.statistics_coverage = coverage
    dataset.coverage = CoverageDeclaration(
        figure_ids=[figure.figure_id for figure in dataset.figures],
        test_ids=[item.test_id or "" for item in dataset.statistics],
        ledger_sha256=ledger.ledger_sha256,
        declared_by=ledger.declaration_source,
        details={"analysis_id": ledger.analysis_id} if ledger.analysis_id else {},
    )
    errors = dataset.validate()
    if errors:
        raise ValueError("invalid reconciled publication dataset:\n- " + "\n- ".join(errors))
    return dataset


def statistics_rows(dataset: PublicationDataset) -> list[dict[str, Any]]:
    return [
        {name: statistic.normalized.get(name) for name in NORMALIZED_COLUMNS}
        for statistic in dataset.statistics
    ]


__all__ = [
    "ImportedLedger",
    "LEDGER_SCHEMA",
    "NORMALIZED_COLUMNS",
    "import_statistics_ledger",
    "normalize_statistic",
    "reconcile_statistics",
    "statistics_rows",
]
