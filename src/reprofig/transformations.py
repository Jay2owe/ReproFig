"""Safe, versioned reconstruction of plotted tables from declared sources."""

from __future__ import annotations

import csv
import io
from collections import defaultdict
from typing import Any, Callable, Mapping, Sequence

from .schema import DataTable, FigureRecord, TransformationSpec, deterministic_json, sha256_bytes
from .tables import table_from_data
from .verification import ProofCheck

TRANSFORMATION_SCHEMA = "reprofig-transformation-registry/1"
MAX_ROWS = 2_000_000


def stable_row_id(row: Mapping[str, Any], index: int) -> str:
    return "row:" + sha256_bytes(
        deterministic_json({"index": index, "values": dict(row)}).encode("utf-8")
    )[:24]


def canonical_rows(table: DataTable) -> list[dict[str, Any]]:
    if table.contents is None:
        raise PermissionError(f"table {table.name!r} is protected or inaccessible")
    reader = csv.DictReader(io.StringIO(table.contents, newline=""))
    rows = [dict(row) for row in reader]
    if len(rows) > MAX_ROWS:
        raise ValueError(f"table {table.name!r} exceeds reconstruction row limit")
    for index, row in enumerate(rows):
        row.setdefault("__reprofig_row_id", stable_row_id(row, index))
    return rows


def _select(rows: list[dict[str, Any]], parameters: Mapping[str, Any]) -> list[dict[str, Any]]:
    columns = [str(value) for value in parameters.get("columns", [])]
    return [
        {
            **{key: row.get(key) for key in columns},
            **(
                {"__reprofig_row_id": row["__reprofig_row_id"]}
                if "__reprofig_row_id" in row
                else {}
            ),
        }
        for row in rows
    ]


def _rename(rows: list[dict[str, Any]], parameters: Mapping[str, Any]) -> list[dict[str, Any]]:
    mapping = {str(key): str(value) for key, value in (parameters.get("columns") or {}).items()}
    return [{mapping.get(key, key): value for key, value in row.items()} for row in rows]


def _cast_value(value: Any, dtype: str, *, missing: Sequence[str]) -> Any:
    if value is None or str(value) in missing:
        return None
    if dtype in {"str", "string", "text"}:
        return str(value)
    if dtype in {"int", "integer"}:
        return int(str(value))
    if dtype in {"float", "number"}:
        return float(str(value))
    if dtype in {"bool", "boolean"}:
        lowered = str(value).casefold()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
        raise ValueError(f"cannot cast {value!r} to bool")
    raise ValueError(f"unsupported cast dtype {dtype!r}")


def _cast(rows: list[dict[str, Any]], parameters: Mapping[str, Any]) -> list[dict[str, Any]]:
    columns = parameters.get("columns") or {}
    missing = [str(value) for value in parameters.get("missing_values", [""])]
    return [
        {
            key: _cast_value(value, str(columns[key]), missing=missing) if key in columns else value
            for key, value in row.items()
        }
        for row in rows
    ]


def _filter(rows: list[dict[str, Any]], parameters: Mapping[str, Any]) -> list[dict[str, Any]]:
    column = str(parameters.get("column", ""))
    operator = str(parameters.get("operator", "eq"))
    expected = parameters.get("value")
    operators: dict[str, Callable[[Any, Any], bool]] = {
        "eq": lambda left, right: left == right,
        "ne": lambda left, right: left != right,
        "lt": lambda left, right: left < right,
        "le": lambda left, right: left <= right,
        "gt": lambda left, right: left > right,
        "ge": lambda left, right: left >= right,
        "in": lambda left, right: left in right,
        "not_in": lambda left, right: left not in right,
    }
    if operator not in operators:
        raise ValueError(f"unsupported filter operator {operator!r}")
    return [row for row in rows if operators[operator](row.get(column), expected)]


def _drop_missing(rows: list[dict[str, Any]], parameters: Mapping[str, Any]) -> list[dict[str, Any]]:
    columns = [str(value) for value in parameters.get("columns", [])]
    missing = {str(value) for value in parameters.get("missing_values", [""])}
    return [
        row for row in rows
        if all(row.get(column) is not None and str(row.get(column)) not in missing for column in columns)
    ]


def _sort(rows: list[dict[str, Any]], parameters: Mapping[str, Any]) -> list[dict[str, Any]]:
    by = [str(value) for value in parameters.get("by", [])]
    reverse = bool(parameters.get("descending", False))
    return sorted(rows, key=lambda row: tuple((row.get(key) is None, row.get(key)) for key in by), reverse=reverse)


def _group(rows: list[dict[str, Any]], parameters: Mapping[str, Any]) -> list[dict[str, Any]]:
    by = [str(value) for value in parameters.get("by", [])]
    result: list[dict[str, Any]] = []
    for key, members in _grouped(rows, by):
        result.append({**dict(zip(by, key)), "rows": members})
    return result


def _grouped(rows: list[dict[str, Any]], by: Sequence[str]):
    grouped: dict[tuple[Any, ...], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[tuple(row.get(column) for column in by)].append(row)
    for key in sorted(grouped, key=lambda value: deterministic_json(value)):
        yield key, grouped[key]


def _aggregate(rows: list[dict[str, Any]], parameters: Mapping[str, Any]) -> list[dict[str, Any]]:
    by = [str(value) for value in parameters.get("by", [])]
    aggregations = parameters.get("aggregations") or {}
    result: list[dict[str, Any]] = []
    for key, members in _grouped(rows, by):
        output = dict(zip(by, key))
        contributors = sorted(
            str(member.get("__reprofig_row_id"))
            for member in members
            if member.get("__reprofig_row_id") is not None
        )
        for output_name, specification in aggregations.items():
            if isinstance(specification, str):
                operation, column = specification, output_name
            else:
                operation = str(specification.get("operation"))
                column = str(specification.get("column", output_name))
            values = [member.get(column) for member in members if member.get(column) is not None]
            numeric = [float(value) for value in values]
            if operation == "count":
                output[str(output_name)] = len(values)
            elif operation == "sum":
                output[str(output_name)] = sum(numeric)
            elif operation == "mean":
                output[str(output_name)] = sum(numeric) / len(numeric) if numeric else None
            elif operation == "min":
                output[str(output_name)] = min(numeric) if numeric else None
            elif operation == "max":
                output[str(output_name)] = max(numeric) if numeric else None
            else:
                raise ValueError(f"unsupported aggregate operation {operation!r}")
        output["__reprofig_contributor_count"] = len(contributors)
        output["__reprofig_contributor_sha256"] = sha256_bytes(
            deterministic_json(contributors).encode("utf-8")
        )
        result.append(output)
    return result


OPERATIONS = {
    "select/v1": _select,
    "rename/v1": _rename,
    "cast/v1": _cast,
    "filter/v1": _filter,
    "drop-missing/v1": _drop_missing,
    "sort/v1": _sort,
    "group/v1": _group,
    "aggregate/v1": _aggregate,
}


def apply_transformation(rows: list[dict[str, Any]], specification: TransformationSpec) -> list[dict[str, Any]]:
    key = f"{specification.operation}/{specification.version}"
    implementation = OPERATIONS.get(key)
    if implementation is None:
        raise ValueError(f"unsupported transformation {key!r}")
    return implementation([dict(row) for row in rows], specification.parameters)


def reconstruct_tables(
    specifications: Sequence[TransformationSpec],
    tables: Mapping[str, DataTable | list[dict[str, Any]]],
) -> dict[str, list[dict[str, Any]]]:
    available: dict[str, list[dict[str, Any]]] = {
        identity: canonical_rows(value) if isinstance(value, DataTable) else [dict(row) for row in value]
        for identity, value in tables.items()
    }
    pending = list(specifications)
    while pending:
        progressed = False
        for specification in list(pending):
            if not all(identity in available for identity in specification.input_table_ids):
                continue
            if len(specification.input_table_ids) != 1:
                raise ValueError("version 1 transformations require exactly one input table")
            available[specification.output_table_id] = apply_transformation(
                available[specification.input_table_ids[0]], specification
            )
            pending.remove(specification)
            progressed = True
        if not progressed:
            missing = sorted({identity for spec in pending for identity in spec.input_table_ids if identity not in available})
            raise ValueError("transformation graph is cyclic or missing tables: " + ", ".join(missing))
    return available


def verify_record_transformations(
    record: FigureRecord,
    *,
    supplied_tables: Mapping[str, Any],
) -> list[ProofCheck]:
    proof = record.extensions.get("proof") or {}
    values = proof.get("transformations") if isinstance(proof, Mapping) else None
    if not values:
        return [ProofCheck("source-reconstruction", "source_linked", "unavailable", record.figure_id, "No transformations were declared.")]
    specifications = [TransformationSpec.from_dict(value) for value in values]
    tables: dict[str, DataTable | list[dict[str, Any]]] = {
        f"table:{table.sha256}": table for table in record.data_tables
    }
    tables.update(supplied_tables)
    try:
        reconstructed = reconstruct_tables(specifications, tables)
    except PermissionError as exc:
        return [ProofCheck(
            "source-reconstruction", "source_linked", "inaccessible",
            record.figure_id, str(exc),
        )]
    except Exception as exc:
        return [ProofCheck("source-reconstruction", "source_linked", "fail", record.figure_id, str(exc))]
    checks: list[ProofCheck] = []
    targets = {f"table:{table.sha256}": table for table in record.data_tables}
    for specification in specifications:
        target = targets.get(specification.output_table_id)
        if target is None:
            continue
        rebuilt = table_from_data(
            [
                {
                    key: value
                    for key, value in row.items()
                    if not key.startswith("__reprofig_")
                }
                for row in reconstructed[specification.output_table_id]
            ],
            name=target.name,
            purpose=target.purpose,
        )
        status = "pass" if rebuilt.sha256 == target.sha256 else "fail"
        checks.append(ProofCheck(
            f"transform:{specification.transform_id}", "source_linked", status,
            specification.output_table_id,
            "Reconstructed table matches exact canonical bytes." if status == "pass" else "Reconstructed table differs from embedded target.",
            expected=target.sha256, actual=rebuilt.sha256,
        ))
    if not checks:
        checks.append(ProofCheck("source-reconstruction", "source_linked", "pass", record.figure_id, "Declared transformation graph executed."))
    return checks


__all__ = [
    "OPERATIONS",
    "apply_transformation",
    "canonical_rows",
    "reconstruct_tables",
    "stable_row_id",
    "verify_record_transformations",
]
