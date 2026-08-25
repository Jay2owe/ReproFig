"""Dispatch and compare independent statistical calculations."""

from __future__ import annotations

import math
from importlib.metadata import PackageNotFoundError, version
from typing import Any, Mapping, Sequence

from ..schema import FigureRecord, StatisticalSpecification
from ..transformations import canonical_rows
from ..verification import ProofCheck
from .registry import get_algorithm

VERIFIER_IMPLEMENTATION = "reprofig-reference-statistics/1"


def _resolve_value(value: Any, record: FigureRecord) -> Any:
    if isinstance(value, list):
        return [_resolve_value(item, record) for item in value]
    if not isinstance(value, Mapping):
        return value
    if "table_id" not in value:
        return {key: _resolve_value(item, record) for key, item in value.items()}
    table_id = str(value["table_id"])
    tables = {f"table:{table.sha256}": table for table in record.data_tables}
    table = tables.get(table_id)
    if table is None:
        raise ValueError(f"statistical input references unknown table {table_id}")
    if table.contents is None:
        raise PermissionError(
            f"statistical input table {table_id} is protected or inaccessible"
        )
    rows = canonical_rows(table)
    where = value.get("where")
    if isinstance(where, Mapping):
        rows = [row for row in rows if all(row.get(str(key)) == expected for key, expected in where.items())]
    column = value.get("column")
    if column is None:
        return [{key: item for key, item in row.items() if key != "__reprofig_row_id"} for row in rows]
    return [row.get(str(column)) for row in rows]


def calculate_specification(
    specification: StatisticalSpecification,
    *,
    record: FigureRecord | None = None,
) -> dict[str, Any]:
    algorithm = get_algorithm(specification.algorithm_id)
    if algorithm is None:
        raise NotImplementedError(specification.algorithm_id)
    inputs = {
        key: _resolve_value(value, record) if record is not None else value
        for key, value in specification.inputs.items()
    }
    missing = sorted(set(algorithm.input_roles) - set(inputs))
    missing_parameters = sorted(set(algorithm.required_parameters) - set(specification.parameters))
    if missing or missing_parameters:
        raise ValueError(
            f"{specification.algorithm_id} is missing inputs {missing} and parameters {missing_parameters}"
        )
    parameters = {
        key: value
        for key, value in specification.parameters.items()
        if key not in {"producer_implementation", "producer_package", "producer_version"}
    }
    return algorithm.calculator(**inputs, **parameters)


def _flatten(value: Any, prefix: str = "") -> dict[str, Any]:
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, item in value.items():
            name = f"{prefix}.{key}" if prefix else str(key)
            result.update(_flatten(item, name))
        return result
    if isinstance(value, list):
        result = {}
        for index, item in enumerate(value):
            name = f"{prefix}[{index}]"
            result.update(_flatten(item, name))
        return result
    return {prefix: value}


def _matches(expected: Any, actual: Any, tolerance: Mapping[str, Any]) -> bool:
    if isinstance(expected, (int, float)) and isinstance(actual, (int, float)):
        if isinstance(expected, bool) or isinstance(actual, bool):
            return expected == actual
        absolute = float(tolerance.get("absolute", 1e-12))
        relative = float(tolerance.get("relative", 1e-9))
        return math.isclose(float(expected), float(actual), abs_tol=absolute, rel_tol=relative)
    return expected == actual


def _format_display(field: str, value: Any, format_id: str) -> str:
    numeric = float(value)
    if format_id == "p_equals_4dp/v1":
        return f"p = {numeric:.4f}"
    if format_id == "p_equals_3dp/v1":
        return f"p = {numeric:.3f}"
    if format_id == "p_threshold_0.001/v1":
        return "p < 0.001" if numeric < 0.001 else f"p = {numeric:.3f}"
    if format_id == "exact/v1":
        return str(value)
    raise NotImplementedError(format_id)


def specifications_from_record(record: FigureRecord) -> list[StatisticalSpecification]:
    proof = record.extensions.get("proof") or {}
    values = proof.get("statistical_specifications") if isinstance(proof, Mapping) else None
    result = [StatisticalSpecification.from_dict(item) for item in values or []]
    for section in proof.get("sections", []) if isinstance(proof, Mapping) else []:
        if section.get("kind") == "statistical_specification" and isinstance(section.get("payload"), Mapping):
            result.append(StatisticalSpecification.from_dict(section["payload"]))
    unique: dict[str, StatisticalSpecification] = {}
    for item in result:
        if item.statistic_id in unique:
            if unique[str(item.statistic_id)].to_dict() != item.to_dict():
                raise ValueError(f"conflicting statistical specification {item.statistic_id}")
            continue
        unique[str(item.statistic_id)] = item
    return list(unique.values())


def verify_record_statistics(record: FigureRecord) -> list[ProofCheck]:
    try:
        specifications = specifications_from_record(record)
    except Exception as exc:
        return [ProofCheck("statistics-specifications", "independently_verified", "fail", record.figure_id, str(exc))]
    if not specifications:
        return [ProofCheck("statistics-specifications", "independently_verified", "unavailable", record.figure_id, "No typed statistical specifications are present.")]
    checks: list[ProofCheck] = []
    for specification in specifications:
        algorithm = get_algorithm(specification.algorithm_id)
        if algorithm is None:
            checks.append(ProofCheck(f"stat:{specification.statistic_id}", "independently_verified", "unsupported", specification.statistic_id, f"Unsupported algorithm {specification.algorithm_id}."))
            continue
        try:
            actual = calculate_specification(specification, record=record)
        except PermissionError as exc:
            checks.append(ProofCheck(
                f"stat:{specification.statistic_id}",
                "independently_verified",
                "inaccessible",
                specification.statistic_id,
                str(exc),
            ))
            continue
        except Exception as exc:
            checks.append(ProofCheck(f"stat:{specification.statistic_id}", "independently_verified", "fail", specification.statistic_id, str(exc)))
            continue
        expected = _flatten(specification.expected)
        calculated = _flatten(actual)
        if not expected:
            checks.append(ProofCheck(f"stat:{specification.statistic_id}", "reproduced", "unavailable", specification.statistic_id, "Specification has no expected result to compare."))
            continue
        mismatches = []
        for name, expected_value in expected.items():
            if name not in calculated:
                mismatches.append(f"{name}: missing")
                continue
            tolerance = specification.tolerances.get(name, specification.tolerances.get("*", {}))
            if not _matches(expected_value, calculated[name], tolerance if isinstance(tolerance, Mapping) else {}):
                mismatches.append(f"{name}: expected {expected_value!r}, got {calculated[name]!r}")
        producer = str(specification.parameters.get("producer_implementation", ""))
        meaning = "reproduced" if producer == VERIFIER_IMPLEMENTATION else "independently_verified"
        status = "fail" if mismatches else "pass"
        checks.append(ProofCheck(
            f"stat:{specification.statistic_id}", meaning, status, specification.statistic_id,
            "; ".join(mismatches) if mismatches else f"{specification.algorithm_id} independently matched declared outputs.",
            expected=specification.expected, actual=actual, tolerance=specification.tolerances,
        ))
        display = specification.display
        if display.get("text") is not None or display.get("format") is not None:
            field = str(display.get("field", "p_value"))
            format_id = str(display.get("format", ""))
            try:
                displayed = _format_display(field, actual[field], format_id)
                display_status = (
                    "pass" if displayed == str(display.get("text")) else "fail"
                )
                display_message = (
                    "Calculated value reproduces the declared display text."
                    if display_status == "pass"
                    else "Calculated value does not reproduce the declared display text."
                )
            except (KeyError, TypeError, ValueError) as exc:
                displayed = None
                display_status = "fail"
                display_message = str(exc)
            except NotImplementedError:
                displayed = None
                display_status = "unsupported"
                display_message = f"Unsupported statistical formatter {format_id}."
            checks.append(ProofCheck(
                f"stat-display:{specification.statistic_id}", meaning,
                display_status, specification.statistic_id, display_message,
                expected=display.get("text"), actual=displayed,
            ))
    return checks


__all__ = [
    "VERIFIER_IMPLEMENTATION",
    "calculate_specification",
    "specifications_from_record",
    "verify_record_statistics",
]
