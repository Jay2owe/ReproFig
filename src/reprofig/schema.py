"""Versioned, dependency-light figure record schema."""

from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import uuid
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Mapping

SCHEMA_ID = "reprofig/1"
LEGACY_SCHEMA_IDS = frozenset({"figure-artifact/1", "metafig/1"})
SUPPORTED_SCHEMA_IDS = frozenset({SCHEMA_ID, *LEGACY_SCHEMA_IDS})
SUPPORTED_PROFILES = frozenset({"master", "public", "minimal_public"})
PUBLIC_STATES = frozenset({"safe", "private", "unclassified"})


def _now() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def new_figure_id() -> str:
    return "rf-" + uuid.uuid4().hex


def json_safe(value: Any) -> Any:
    """Return a deterministic JSON-compatible representation.

    Non-finite numbers are tagged instead of relying on JavaScript's invalid
    ``NaN`` and ``Infinity`` tokens. Scientific scalar objects are handled by
    their conventional ``item`` method without importing NumPy or pandas.
    """

    if value is None or isinstance(value, (str, bool, int)):
        return value
    if isinstance(value, float):
        if math.isnan(value):
            return {"$number": "NaN"}
        if math.isinf(value):
            return {"$number": "Infinity" if value > 0 else "-Infinity"}
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Path) or hasattr(value, "__fspath__"):
        return str(value)
    if dataclasses.is_dataclass(value):
        return json_safe(dataclasses.asdict(value))
    if isinstance(value, Mapping):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [json_safe(item) for item in value]
    item = getattr(value, "item", None)
    if callable(item):
        try:
            return json_safe(item())
        except Exception:
            pass
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return json_safe(to_dict())
        except Exception:
            pass
    return str(value)


def deterministic_json(value: Any, *, indent: int | None = None) -> str:
    separators = (",", ":") if indent is None else None
    return json.dumps(
        json_safe(value),
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        indent=indent,
        separators=separators,
    )


def sha256_bytes(contents: bytes) -> str:
    return hashlib.sha256(contents).hexdigest()


@dataclass
class ColumnSpec:
    name: str
    dtype: str = "unknown"
    role: str | None = None
    public_state: str = "unclassified"
    public_name: str | None = None

    def __post_init__(self) -> None:
        self.name = str(self.name)
        self.dtype = str(self.dtype)
        if self.public_state not in PUBLIC_STATES:
            raise ValueError(
                f"public_state must be one of {sorted(PUBLIC_STATES)}, "
                f"not {self.public_state!r}"
            )

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in dataclasses.asdict(self).items() if value is not None}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ColumnSpec":
        return cls(
            name=str(value.get("name", "")),
            dtype=str(value.get("dtype", "unknown")),
            role=value.get("role"),
            public_state=str(value.get("public_state", "unclassified")),
            public_name=value.get("public_name"),
        )


@dataclass
class DataTable:
    name: str
    purpose: str
    sha256: str
    row_count: int
    column_count: int
    columns: list[ColumnSpec] = field(default_factory=list)
    contents: str | None = None
    format: str = "text/csv; charset=utf-8"
    newline: str = "LF"
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = str(self.name)
        self.purpose = str(self.purpose)
        self.sha256 = str(self.sha256)
        self.row_count = int(self.row_count)
        self.column_count = int(self.column_count)
        self.columns = [
            value if isinstance(value, ColumnSpec) else ColumnSpec.from_dict(value)
            for value in self.columns
        ]

    @property
    def embedded(self) -> bool:
        return self.contents is not None

    def content_bytes(self) -> bytes | None:
        return None if self.contents is None else self.contents.encode("utf-8")

    def verify(self) -> bool:
        contents = self.content_bytes()
        return contents is None or sha256_bytes(contents) == self.sha256

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "name": self.name,
            "purpose": self.purpose,
            "format": self.format,
            "newline": self.newline,
            "sha256": self.sha256,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": [column.to_dict() for column in self.columns],
            "embedded": self.embedded,
        }
        if self.contents is not None:
            result["contents"] = self.contents
        if self.metadata:
            result["metadata"] = json_safe(self.metadata)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "DataTable":
        return cls(
            name=str(value.get("name", "data")),
            purpose=str(value.get("purpose", "analysis")),
            format=str(value.get("format", "text/csv; charset=utf-8")),
            newline=str(value.get("newline", "LF")),
            sha256=str(value.get("sha256", "")),
            row_count=int(value.get("row_count", 0)),
            column_count=int(value.get("column_count", 0)),
            columns=[ColumnSpec.from_dict(item) for item in value.get("columns", [])],
            contents=value.get("contents"),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class SourceReference:
    role: str
    relative_path: str | None = None
    uri: str | None = None
    sha256: str | None = None
    size_bytes: int | None = None
    modified_at: str | None = None
    source_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        result = {
            key: value
            for key, value in dataclasses.asdict(self).items()
            if value is not None and value != {}
        }
        return json_safe(result)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SourceReference":
        return cls(
            role=str(value.get("role", "source")),
            relative_path=value.get("relative_path"),
            uri=value.get("uri"),
            sha256=value.get("sha256"),
            size_bytes=value.get("size_bytes"),
            modified_at=value.get("modified_at"),
            source_id=value.get("source_id"),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class EvidenceSection:
    """One independently hashed unit in a proof-carrying record."""

    kind: str
    payload: Any
    section_id: str | None = None
    schema: str = "reprofig-evidence-section/1"
    dependencies: list[str] = field(default_factory=list)
    sha256: str | None = None
    encrypted: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.kind = str(self.kind)
        self.payload = json_safe(self.payload)
        self.dependencies = sorted({str(value) for value in self.dependencies})
        self.metadata = dict(json_safe(self.metadata))
        identity_input = {"schema": self.schema, "kind": self.kind, "payload": self.payload}
        if not self.section_id:
            self.section_id = f"evidence:{self.kind}:{sha256_bytes(deterministic_json(identity_input).encode('utf-8'))[:24]}"

    def content_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "section_id": self.section_id,
            "kind": self.kind,
            "payload": json_safe(self.payload),
            "dependencies": list(self.dependencies),
            "encrypted": self.encrypted,
            "metadata": json_safe(self.metadata),
        }

    def digest(self) -> str:
        return sha256_bytes(deterministic_json(self.content_dict()).encode("utf-8"))

    def to_dict(self) -> dict[str, Any]:
        value = self.content_dict()
        value["sha256"] = self.sha256 or self.digest()
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "EvidenceSection":
        return cls(
            schema=str(value.get("schema", "reprofig-evidence-section/1")),
            section_id=value.get("section_id"),
            kind=str(value.get("kind", "unknown")),
            payload=value.get("payload"),
            dependencies=[str(item) for item in value.get("dependencies", [])],
            sha256=value.get("sha256"),
            encrypted=bool(value.get("encrypted", False)),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class ScientificClaim:
    text: str
    claim_id: str | None = None
    evidence_ids: list[str] = field(default_factory=list)
    statistic_ids: list[str] = field(default_factory=list)
    schema: str = "reprofig-claim/1"

    def __post_init__(self) -> None:
        self.text = str(self.text)
        self.evidence_ids = sorted({str(value) for value in self.evidence_ids})
        self.statistic_ids = sorted({str(value) for value in self.statistic_ids})
        if not self.claim_id:
            identity = deterministic_json({
                "text": self.text,
                "evidence_ids": self.evidence_ids,
                "statistic_ids": self.statistic_ids,
            })
            self.claim_id = "claim:" + sha256_bytes(identity.encode("utf-8"))[:24]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "claim_id": self.claim_id,
            "text": self.text,
            "evidence_ids": list(self.evidence_ids),
            "statistic_ids": list(self.statistic_ids),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "ScientificClaim":
        return cls(
            schema=str(value.get("schema", "reprofig-claim/1")),
            claim_id=value.get("claim_id"),
            text=str(value.get("text", "")),
            evidence_ids=[str(item) for item in value.get("evidence_ids", [])],
            statistic_ids=[str(item) for item in value.get("statistic_ids", [])],
        )


@dataclass
class TransformationSpec:
    operation: str
    input_table_ids: list[str]
    output_table_id: str
    parameters: dict[str, Any] = field(default_factory=dict)
    transform_id: str | None = None
    version: str = "v1"
    schema: str = "reprofig-transformation/1"

    def __post_init__(self) -> None:
        self.operation = str(self.operation)
        self.input_table_ids = [str(value) for value in self.input_table_ids]
        self.output_table_id = str(self.output_table_id)
        self.parameters = dict(json_safe(self.parameters))
        if not self.transform_id:
            value = deterministic_json({
                "operation": self.operation,
                "version": self.version,
                "inputs": self.input_table_ids,
                "output": self.output_table_id,
                "parameters": self.parameters,
            })
            self.transform_id = "transform:" + sha256_bytes(value.encode("utf-8"))[:24]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "transform_id": self.transform_id,
            "operation": self.operation,
            "version": self.version,
            "input_table_ids": list(self.input_table_ids),
            "output_table_id": self.output_table_id,
            "parameters": json_safe(self.parameters),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TransformationSpec":
        return cls(
            schema=str(value.get("schema", "reprofig-transformation/1")),
            transform_id=value.get("transform_id"),
            operation=str(value.get("operation", "")),
            version=str(value.get("version", "v1")),
            input_table_ids=[str(item) for item in value.get("input_table_ids", [])],
            output_table_id=str(value.get("output_table_id", "")),
            parameters=dict(value.get("parameters") or {}),
        )


@dataclass
class StatisticalSpecification:
    algorithm_id: str
    inputs: dict[str, Any]
    expected: dict[str, Any]
    statistic_id: str | None = None
    parameters: dict[str, Any] = field(default_factory=dict)
    display: dict[str, Any] = field(default_factory=dict)
    tolerances: dict[str, Any] = field(default_factory=dict)
    schema: str = "reprofig-statistical-specification/1"

    def __post_init__(self) -> None:
        self.algorithm_id = str(self.algorithm_id)
        self.inputs = dict(json_safe(self.inputs))
        self.parameters = dict(json_safe(self.parameters))
        self.expected = dict(json_safe(self.expected))
        self.display = dict(json_safe(self.display))
        self.tolerances = dict(json_safe(self.tolerances))
        if not self.statistic_id:
            value = deterministic_json({
                "algorithm_id": self.algorithm_id,
                "inputs": self.inputs,
                "parameters": self.parameters,
                "expected": self.expected,
            })
            self.statistic_id = "statistic:" + sha256_bytes(value.encode("utf-8"))[:24]

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "statistic_id": self.statistic_id,
            "algorithm_id": self.algorithm_id,
            "inputs": json_safe(self.inputs),
            "parameters": json_safe(self.parameters),
            "expected": json_safe(self.expected),
            "display": json_safe(self.display),
            "tolerances": json_safe(self.tolerances),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StatisticalSpecification":
        return cls(
            schema=str(value.get("schema", "reprofig-statistical-specification/1")),
            statistic_id=value.get("statistic_id"),
            algorithm_id=str(value.get("algorithm_id", "")),
            inputs=dict(value.get("inputs") or {}),
            parameters=dict(value.get("parameters") or {}),
            expected=dict(value.get("expected") or {}),
            display=dict(value.get("display") or {}),
            tolerances=dict(value.get("tolerances") or {}),
        )


@dataclass
class FigureRecord:
    figure_id: str = field(default_factory=new_figure_id)
    created_at: str = field(default_factory=_now)
    title: str | None = None
    original_stem: str | None = None
    distribution_profile: str = "master"
    producer: dict[str, Any] = field(default_factory=dict)
    analysis: dict[str, Any] = field(default_factory=dict)
    data_status: str = "incomplete"
    data_tables: list[DataTable] = field(default_factory=list)
    statistics_status: str = "incomplete"
    statistics: list[dict[str, Any]] = field(default_factory=list)
    statistics_csv_sha256: str | None = None
    sources: list[SourceReference] = field(default_factory=list)
    reproduction: dict[str, Any] = field(default_factory=dict)
    integrity: dict[str, Any] = field(default_factory=dict)
    schema: str = SCHEMA_ID
    extensions: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.distribution_profile not in SUPPORTED_PROFILES:
            raise ValueError(
                f"distribution_profile must be one of {sorted(SUPPORTED_PROFILES)}"
            )
        self.data_tables = [
            value if isinstance(value, DataTable) else DataTable.from_dict(value)
            for value in self.data_tables
        ]
        self.sources = [
            value if isinstance(value, SourceReference) else SourceReference.from_dict(value)
            for value in self.sources
        ]
        self.producer = dict(json_safe(self.producer))
        self.analysis = dict(json_safe(self.analysis))
        self.statistics = list(json_safe(self.statistics))
        self.reproduction = dict(json_safe(self.reproduction))
        self.integrity = dict(json_safe(self.integrity))
        self.extensions = dict(json_safe(self.extensions))

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema": self.schema,
            "figure_id": self.figure_id,
            "created_at": self.created_at,
            "distribution_profile": self.distribution_profile,
            "producer": json_safe(self.producer),
            "analysis": json_safe(self.analysis),
            "data_status": self.data_status,
            "data_tables": [table.to_dict() for table in self.data_tables],
            "statistics_status": self.statistics_status,
            "statistics": json_safe(self.statistics),
            "sources": [source.to_dict() for source in self.sources],
        }
        for name in ("title", "original_stem", "statistics_csv_sha256"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        if self.reproduction:
            result["reproduction"] = json_safe(self.reproduction)
        if self.integrity:
            result["integrity"] = json_safe(self.integrity)
        if self.extensions:
            result["extensions"] = json_safe(self.extensions)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FigureRecord":
        schema = str(value.get("schema", ""))
        if not schema.startswith(("reprofig/", "metafig/", "figure-artifact/")):
            raise ValueError(f"Unsupported figure record schema {schema!r}")
        return cls(
            schema=schema,
            figure_id=str(value.get("figure_id") or new_figure_id()),
            created_at=str(value.get("created_at") or _now()),
            title=value.get("title"),
            original_stem=value.get("original_stem"),
            distribution_profile=str(value.get("distribution_profile", "master")),
            producer=dict(value.get("producer") or {}),
            analysis=dict(value.get("analysis") or {}),
            data_status=str(value.get("data_status", "incomplete")),
            data_tables=[DataTable.from_dict(item) for item in value.get("data_tables", [])],
            statistics_status=str(value.get("statistics_status", "incomplete")),
            statistics=list(value.get("statistics") or []),
            statistics_csv_sha256=value.get("statistics_csv_sha256"),
            sources=[SourceReference.from_dict(item) for item in value.get("sources", [])],
            reproduction=dict(value.get("reproduction") or {}),
            integrity=dict(value.get("integrity") or {}),
            extensions=dict(value.get("extensions") or {}),
        )

    def to_json(self, *, indent: int | None = None) -> str:
        return deterministic_json(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, value: str | bytes) -> "FigureRecord":
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("Figure record JSON must contain one object")
        return cls.from_dict(parsed)

    def fingerprint(self) -> str:
        return sha256_bytes(self.to_json().encode("utf-8"))

    def validate(self, *, require_complete: bool = False) -> list[str]:
        errors: list[str] = []
        if self.schema not in SUPPORTED_SCHEMA_IDS:
            errors.append(f"unsupported schema: {self.schema}")
        if not self.figure_id:
            errors.append("figure_id is missing")
        if not self.created_at:
            errors.append("created_at is missing")
        names: set[str] = set()
        for table in self.data_tables:
            if table.name in names:
                errors.append(f"duplicate data table name: {table.name}")
            names.add(table.name)
            if not table.verify():
                errors.append(f"data table hash mismatch: {table.name}")
            if table.column_count != len(table.columns):
                errors.append(f"data table column metadata mismatch: {table.name}")
        if require_complete and self.distribution_profile == "master":
            if self.data_status == "incomplete":
                errors.append("master plotted/analysis data are incomplete")
            if self.statistics_status == "incomplete":
                errors.append("master statistics are incomplete")
            if self.data_status == "complete" and not self.data_tables:
                errors.append("complete master has no data tables")
            for table in self.data_tables:
                if table.contents is None:
                    errors.append(f"master data table is not embedded: {table.name}")
        return errors
