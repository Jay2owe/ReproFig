"""Deterministic CSV serialization and table transformations."""

from __future__ import annotations

import csv
import io
import json
import re
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from .schema import ColumnSpec, DataTable, deterministic_json, json_safe, sha256_bytes

_PREFERRED_STAT_COLUMNS = (
    "record_index",
    "kind",
    "metric",
    "outcome",
    "comparison",
    "group",
    "group_a",
    "group_b",
    "test",
    "statistic",
    "degrees_of_freedom",
    "p",
    "p_raw",
    "p_adjusted",
    "q",
    "correction",
    "n",
    "effect_size",
    "confidence_interval",
    "headline",
)


def safe_filename_token(value: Any, *, fallback: str = "table") -> str:
    """Turn an embedded label into one path-safe filename component."""

    token = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value)).strip(".-_")
    return token or fallback


def _normalise_newlines(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n")


def _read_csv_shape(contents: str) -> tuple[list[str], int]:
    reader = csv.reader(io.StringIO(contents, newline=""))
    try:
        columns = next(reader)
    except StopIteration:
        return [], 0
    rows = sum(1 for _ in reader)
    return [str(column) for column in columns], rows


def _classification_for(
    name: str,
    classification: Mapping[str, str | Mapping[str, Any]] | None,
    roles: Mapping[str, str] | None,
    dtype: str,
) -> ColumnSpec:
    state = "unclassified"
    public_name = None
    role = (roles or {}).get(name)
    configured = (classification or {}).get(name)
    if isinstance(configured, str):
        state = configured
    elif isinstance(configured, Mapping):
        state = str(configured.get("public_state", configured.get("state", state)))
        public_name = configured.get("public_name")
        role = configured.get("role", role)
    return ColumnSpec(
        name=name,
        dtype=dtype,
        role=role,
        public_state=state,
        public_name=public_name,
    )


def _from_dataframe(value: Any, *, include_index: bool) -> tuple[str, list[str], list[str], int]:
    frame = value
    if include_index:
        frame = value.reset_index()
    columns = [str(column) for column in frame.columns]
    if len(columns) != len(set(columns)):
        raise ValueError("CSV table column names must be unique")
    buffer = io.StringIO(newline="")
    frame.to_csv(buffer, index=False, lineterminator="\n")
    dtypes = [str(dtype) for dtype in frame.dtypes]
    return _normalise_newlines(buffer.getvalue()), columns, dtypes, int(len(frame.index))


def _from_records(value: Iterable[Mapping[str, Any]]) -> tuple[str, list[str], list[str], int]:
    records = [dict(item) for item in value]
    columns: list[str] = []
    for record in records:
        for key in record:
            name = str(key)
            if name not in columns:
                columns.append(name)
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=columns, lineterminator="\n")
    writer.writeheader()
    for record in records:
        writer.writerow({name: _csv_scalar(record.get(name)) for name in columns})
    return buffer.getvalue(), columns, ["unknown"] * len(columns), len(records)


def _csv_scalar(value: Any) -> Any:
    safe = json_safe(value)
    if isinstance(safe, (dict, list)):
        return deterministic_json(safe)
    return safe


def table_from_data(
    value: Any,
    *,
    name: str = "plotted_data",
    purpose: str = "plot_and_statistics",
    classification: Mapping[str, str | Mapping[str, Any]] | None = None,
    roles: Mapping[str, str] | None = None,
    include_index: bool = False,
    metadata: Mapping[str, Any] | None = None,
) -> DataTable:
    """Serialize bytes, CSV text, a DataFrame, or records to an embedded table."""

    dtypes: list[str]
    if isinstance(value, bytes):
        contents = _normalise_newlines(value.decode("utf-8-sig"))
        columns, row_count = _read_csv_shape(contents)
        dtypes = ["unknown"] * len(columns)
    elif isinstance(value, str):
        contents = _normalise_newlines(value.lstrip("\ufeff"))
        columns, row_count = _read_csv_shape(contents)
        dtypes = ["unknown"] * len(columns)
    elif hasattr(value, "to_csv") and hasattr(value, "columns"):
        contents, columns, dtypes, row_count = _from_dataframe(
            value, include_index=include_index
        )
    elif isinstance(value, Mapping):
        contents, columns, dtypes, row_count = _from_records([value])
    elif isinstance(value, Iterable):
        contents, columns, dtypes, row_count = _from_records(value)
    else:
        raise TypeError(
            "plotted data must be CSV bytes/text, a pandas-like DataFrame, "
            "or an iterable of mappings"
        )
    if contents and not contents.endswith("\n"):
        contents += "\n"
    specs = [
        _classification_for(column, classification, roles, dtypes[index])
        for index, column in enumerate(columns)
    ]
    raw = contents.encode("utf-8")
    return DataTable(
        name=name,
        purpose=purpose,
        sha256=sha256_bytes(raw),
        row_count=row_count,
        column_count=len(columns),
        columns=specs,
        contents=contents,
        metadata=dict(metadata or {}),
    )


def _flatten_record(record: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    flattened: dict[str, Any] = {}
    for key, value in record.items():
        name = f"{prefix}.{key}" if prefix else str(key)
        if isinstance(value, Mapping):
            nested = _flatten_record(value, name)
            if nested:
                flattened.update(nested)
            else:
                flattened[name] = "{}"
        elif isinstance(value, (list, tuple)):
            flattened[name] = deterministic_json(value)
        else:
            flattened[name] = _csv_scalar(value)
    return flattened


def statistics_csv_bytes(records: Sequence[Mapping[str, Any]] | None) -> bytes:
    """Create a deterministic, loss-aware human-readable statistics table."""

    rows: list[dict[str, Any]] = []
    columns: set[str] = {"record_index"}
    for index, record in enumerate(records or []):
        row = {"record_index": index}
        row.update(_flatten_record(dict(record)))
        rows.append(row)
        columns.update(row)
    ordered = [column for column in _PREFERRED_STAT_COLUMNS if column in columns]
    ordered.extend(sorted(columns.difference(ordered)))
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(
        buffer,
        fieldnames=ordered,
        extrasaction="ignore",
        lineterminator="\n",
    )
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8")


def select_table_columns(
    table: DataTable,
    columns: Sequence[str],
    *,
    public_names: Mapping[str, str] | None = None,
) -> DataTable:
    """Return a newly serialized table containing exactly the approved columns."""

    if table.contents is None:
        raise ValueError(f"data table {table.name!r} has no embedded contents")
    requested = [str(column) for column in columns]
    known = [column.name for column in table.columns]
    missing = [column for column in requested if column not in known]
    if missing:
        raise ValueError(f"unknown columns for {table.name}: {missing}")
    if len(requested) != len(set(requested)):
        raise ValueError(f"duplicate approved columns for {table.name}")
    reader = csv.DictReader(io.StringIO(table.contents, newline=""))
    renamed = {name: (public_names or {}).get(name, name) for name in requested}
    output_names = [renamed[name] for name in requested]
    if len(output_names) != len(set(output_names)):
        raise ValueError(f"duplicate public column names for {table.name}")
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=output_names, lineterminator="\n")
    writer.writeheader()
    row_count = 0
    for row in reader:
        writer.writerow({renamed[name]: row.get(name, "") for name in requested})
        row_count += 1
    contents = buffer.getvalue()
    by_name = {column.name: column for column in table.columns}
    specs = [
        ColumnSpec(
            name=renamed[name],
            dtype=by_name[name].dtype,
            role=by_name[name].role,
            public_state="safe",
            public_name=renamed[name],
        )
        for name in requested
    ]
    return DataTable(
        name=table.name,
        purpose=table.purpose,
        sha256=sha256_bytes(contents.encode("utf-8")),
        row_count=row_count,
        column_count=len(specs),
        columns=specs,
        contents=contents,
        metadata=dict(table.metadata),
    )


def without_contents(table: DataTable) -> DataTable:
    value = table.to_dict()
    value.pop("contents", None)
    return DataTable.from_dict(value)


def table_by_name(tables: Sequence[DataTable], name: str) -> DataTable:
    for table in tables:
        if table.name == name:
            return table
    raise KeyError(name)
