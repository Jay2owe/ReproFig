"""Publication-workbook profile preparation and privacy rules."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..profiles import derive_profile
from ..schema import FigureRecord
from ..validation import scrub_private_strings

_PUBLIC_STATISTIC_FIELDS = {
    "test_id", "id", "analysis_id", "panel_id", "claim_ids", "displayed", "outcome",
    "group_a", "group_b", "unit_of_analysis", "unit", "n", "n_total", "n_a", "n_b",
    "n_group_a", "n_group_b", "n_pairs", "n_excluded", "test", "test_name", "method",
    "test_version", "paired", "alternative", "tail", "tailedness", "alpha", "statistic",
    "stat", "statistic_name", "df", "df1", "df2", "degrees_of_freedom", "p", "p_raw",
    "p_adjusted", "p_adj", "q", "p_displayed", "annotation", "correction", "family_id",
    "correction_family_id", "ci_level", "ci_low", "ci_high", "ci_method", "effect_size",
    "effect_size_name", "effect_ci_low", "effect_ci_high", "missing_policy", "model_formula",
    "covariates", "random_seed", "resamples", "producer_package", "producer_version",
    "specification", "inputs", "parameters", "expected", "algorithm_id",
}


def public_statistic_record(record: Mapping[str, Any]) -> dict[str, Any]:
    return scrub_private_strings(
        {key: value for key, value in record.items() if key in _PUBLIC_STATISTIC_FIELDS}
    )


def qualified_safe_columns(
    record: FigureRecord,
    configured: Mapping[str, Sequence[str]] | Sequence[str] | None,
) -> Mapping[str, Sequence[str]] | Sequence[str] | None:
    if configured is None or not isinstance(configured, Mapping):
        return configured
    result: dict[str, Sequence[str]] = {}
    fallback = configured.get("*")
    for table in record.data_tables:
        qualified = f"{record.figure_id}/{table.name}"
        selected = configured.get(qualified, configured.get(table.name, fallback))
        if selected is not None:
            result[table.name] = selected
    return result


def prepare_record_for_workbook(
    record: FigureRecord,
    *,
    profile: str,
    safe_columns: Mapping[str, Sequence[str]] | Sequence[str] | None = None,
    public_sources: Mapping[str, str] | None = None,
) -> FigureRecord:
    profile = profile.replace("-", "_")
    prepared = derive_profile(
        record,
        profile,
        safe_columns=qualified_safe_columns(record, safe_columns),
        public_sources=public_sources,
    )
    if profile != "master":
        prepared.statistics = [
            public_statistic_record(statistic)
            for statistic in prepared.statistics
        ]
        prepared.extensions = scrub_private_strings(
            {
                key: value
                for key, value in prepared.extensions.items()
                if key in {"proof", "proof_lineage", "public_metadata"}
            }
        )
    return prepared


def prepare_records_for_workbook(
    records: Sequence[FigureRecord],
    *,
    profile: str,
    safe_columns: Mapping[str, Sequence[str]] | Sequence[str] | None = None,
    public_sources: Mapping[str, str] | None = None,
) -> list[FigureRecord]:
    return [
        prepare_record_for_workbook(
            record,
            profile=profile,
            safe_columns=safe_columns,
            public_sources=public_sources,
        )
        for record in records
    ]


__all__ = [
    "prepare_record_for_workbook",
    "prepare_records_for_workbook",
    "public_statistic_record",
    "qualified_safe_columns",
]
