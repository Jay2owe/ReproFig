"""Canonical, dependency-light publication workbook models."""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from typing import Any, Literal, Mapping

from ..schema import ColumnSpec, deterministic_json, json_safe, sha256_bytes

WORKBOOK_SCHEMA = "reprofig-publication-workbook/1"

CoverageStatus = Literal[
    "incomplete",
    "figure_complete",
    "analysis_complete",
    "not_applicable",
]
COVERAGE_STATUSES = frozenset(
    {"incomplete", "figure_complete", "analysis_complete", "not_applicable"}
)
PUBLICATION_PROFILES = frozenset({"master", "public", "minimal_public"})
STATISTIC_SOURCES = frozenset({"figure", "experiment_ledger", "both"})
_HEX_DIGITS = frozenset("0123456789abcdef")


def _is_sha256(value: str) -> bool:
    return len(value) == 64 and all(character in _HEX_DIGITS for character in value)


def _hash_mapping(value: Mapping[str, Any]) -> str:
    return sha256_bytes(deterministic_json(value).encode("utf-8"))


def _stable_json_sort_key(value: Any) -> str:
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        value = to_dict()
    return deterministic_json(value)


def _dict(value: Mapping[str, Any] | None) -> dict[str, Any]:
    return dict(json_safe(value or {}))


@dataclass
class TableOccurrence:
    """One appearance of a data table within one figure record."""

    figure_id: str
    figure_record_sha256: str
    table_name: str
    table_index: int
    occurrence_id: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.figure_id = str(self.figure_id)
        self.figure_record_sha256 = str(self.figure_record_sha256)
        self.table_name = str(self.table_name)
        self.table_index = int(self.table_index)
        if self.occurrence_id is None:
            self.occurrence_id = f"table-occurrence:{self.figure_id}:{self.table_index}"
        else:
            self.occurrence_id = str(self.occurrence_id)
        self.metadata = _dict(self.metadata)

    def sort_key(self) -> tuple[str, int, str, str]:
        return (
            self.figure_id,
            self.table_index,
            self.table_name,
            self.figure_record_sha256,
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "occurrence_id": self.occurrence_id,
            "figure_id": self.figure_id,
            "figure_record_sha256": self.figure_record_sha256,
            "table_name": self.table_name,
            "table_index": self.table_index,
        }
        if self.metadata:
            result["metadata"] = json_safe(self.metadata)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TableOccurrence":
        return cls(
            occurrence_id=value.get("occurrence_id"),
            figure_id=str(value.get("figure_id", "")),
            figure_record_sha256=str(value.get("figure_record_sha256", "")),
            table_name=str(value.get("table_name", "")),
            table_index=int(value.get("table_index", 0)),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class StatisticOccurrence:
    """One appearance of a statistical test in a figure or ledger."""

    figure_id: str
    figure_record_sha256: str
    statistic_index: int
    occurrence_id: str | None = None
    displayed: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.figure_id = str(self.figure_id)
        self.figure_record_sha256 = str(self.figure_record_sha256)
        self.statistic_index = int(self.statistic_index)
        if self.occurrence_id is None:
            self.occurrence_id = f"stat-occurrence:{self.figure_id}:{self.statistic_index}"
        else:
            self.occurrence_id = str(self.occurrence_id)
        self.displayed = bool(self.displayed)
        self.metadata = _dict(self.metadata)

    def sort_key(self) -> tuple[str, int, str]:
        return (self.figure_id, self.statistic_index, self.figure_record_sha256)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "occurrence_id": self.occurrence_id,
            "figure_id": self.figure_id,
            "figure_record_sha256": self.figure_record_sha256,
            "statistic_index": self.statistic_index,
            "displayed": self.displayed,
        }
        if self.metadata:
            result["metadata"] = json_safe(self.metadata)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "StatisticOccurrence":
        return cls(
            occurrence_id=value.get("occurrence_id"),
            figure_id=str(value.get("figure_id", "")),
            figure_record_sha256=str(value.get("figure_record_sha256", "")),
            statistic_index=int(value.get("statistic_index", 0)),
            displayed=bool(value.get("displayed", True)),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class PublicationFigure:
    """A source figure record represented in the publication dataset."""

    figure_id: str
    figure_record_sha256: str
    display_order: int = 0
    schema: str = "reprofig/1"
    profile: str = "master"
    title: str | None = None
    original_stem: str | None = None
    source_label: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.figure_id = str(self.figure_id)
        self.figure_record_sha256 = str(self.figure_record_sha256)
        self.display_order = int(self.display_order)
        self.schema = str(self.schema)
        self.profile = str(self.profile)
        if self.title is not None:
            self.title = str(self.title)
        if self.original_stem is not None:
            self.original_stem = str(self.original_stem)
        if self.source_label is not None:
            self.source_label = str(self.source_label)
        self.metadata = _dict(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "figure_id": self.figure_id,
            "figure_record_sha256": self.figure_record_sha256,
            "schema": self.schema,
            "profile": self.profile,
            "display_order": self.display_order,
        }
        for name in ("title", "original_stem", "source_label"):
            value = getattr(self, name)
            if value is not None:
                result[name] = value
        if self.metadata:
            result["metadata"] = json_safe(self.metadata)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PublicationFigure":
        return cls(
            figure_id=str(value.get("figure_id", "")),
            figure_record_sha256=str(value.get("figure_record_sha256", "")),
            schema=str(value.get("schema", "reprofig/1")),
            profile=str(value.get("profile", "master")),
            display_order=int(value.get("display_order", 0)),
            title=value.get("title"),
            original_stem=value.get("original_stem"),
            source_label=value.get("source_label"),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class PublicationTable:
    """A unique canonical source-data table and all its figure occurrences."""

    sha256: str
    name: str
    purpose: str
    row_count: int
    column_count: int
    columns: list[ColumnSpec | Mapping[str, Any]] = field(default_factory=list)
    occurrences: list[TableOccurrence | Mapping[str, Any]] = field(default_factory=list)
    table_id: str | None = None
    contents: str | None = None
    format: str = "text/csv; charset=utf-8"
    newline: str = "LF"
    display_order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.sha256 = str(self.sha256)
        self.name = str(self.name)
        self.purpose = str(self.purpose)
        self.row_count = int(self.row_count)
        self.column_count = int(self.column_count)
        self.table_id = str(self.table_id or f"table:{self.sha256}")
        if self.contents is not None:
            self.contents = str(self.contents)
        self.format = str(self.format)
        self.newline = str(self.newline)
        self.display_order = int(self.display_order)
        self.columns = [
            column if isinstance(column, ColumnSpec) else ColumnSpec.from_dict(column)
            for column in self.columns
        ]
        self.occurrences = sorted(
            [
                occurrence
                if isinstance(occurrence, TableOccurrence)
                else TableOccurrence.from_dict(occurrence)
                for occurrence in self.occurrences
            ],
            key=lambda occurrence: occurrence.sort_key(),
        )
        self.metadata = _dict(self.metadata)

    @property
    def embedded(self) -> bool:
        return self.contents is not None

    def verify(self) -> bool:
        return self.contents is None or sha256_bytes(self.contents.encode("utf-8")) == self.sha256

    def fingerprint(self) -> str:
        return _hash_mapping(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "table_id": self.table_id,
            "name": self.name,
            "purpose": self.purpose,
            "format": self.format,
            "newline": self.newline,
            "sha256": self.sha256,
            "row_count": self.row_count,
            "column_count": self.column_count,
            "columns": [column.to_dict() for column in self.columns],
            "occurrences": [occurrence.to_dict() for occurrence in self.occurrences],
            "embedded": self.embedded,
            "display_order": self.display_order,
        }
        if self.contents is not None:
            result["contents"] = self.contents
        if self.metadata:
            result["metadata"] = json_safe(self.metadata)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PublicationTable":
        return cls(
            table_id=value.get("table_id"),
            sha256=str(value.get("sha256", "")),
            name=str(value.get("name", "data")),
            purpose=str(value.get("purpose", "analysis")),
            format=str(value.get("format", "text/csv; charset=utf-8")),
            newline=str(value.get("newline", "LF")),
            row_count=int(value.get("row_count", 0)),
            column_count=int(value.get("column_count", 0)),
            columns=[ColumnSpec.from_dict(item) for item in value.get("columns", [])],
            occurrences=[
                TableOccurrence.from_dict(item) for item in value.get("occurrences", [])
            ],
            contents=value.get("contents"),
            display_order=int(value.get("display_order", 0)),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class PublicationStatistic:
    """A canonical statistical test record and all displayed occurrences."""

    raw_record: dict[str, Any]
    occurrences: list[StatisticOccurrence | Mapping[str, Any]] = field(default_factory=list)
    test_id: str | None = None
    displayed: bool = True
    source: str = "figure"
    normalized: dict[str, Any] = field(default_factory=dict)
    family_id: str | None = None
    display_order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.raw_record = _dict(self.raw_record)
        self.occurrences = sorted(
            [
                occurrence
                if isinstance(occurrence, StatisticOccurrence)
                else StatisticOccurrence.from_dict(occurrence)
                for occurrence in self.occurrences
            ],
            key=lambda occurrence: occurrence.sort_key(),
        )
        if self.test_id is None:
            if self.occurrences:
                first = self.occurrences[0]
                self.test_id = f"figure-stat:{first.figure_id}:{first.statistic_index}"
            else:
                self.test_id = ""
        else:
            self.test_id = str(self.test_id)
        self.displayed = bool(self.displayed)
        self.source = str(self.source)
        self.normalized = _dict(self.normalized)
        if self.family_id is not None:
            self.family_id = str(self.family_id)
        self.display_order = int(self.display_order)
        self.metadata = _dict(self.metadata)

    def fingerprint(self) -> str:
        return _hash_mapping(self.to_dict())

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "test_id": self.test_id,
            "raw_record": json_safe(self.raw_record),
            "occurrences": [occurrence.to_dict() for occurrence in self.occurrences],
            "displayed": self.displayed,
            "source": self.source,
            "normalized": json_safe(self.normalized),
            "display_order": self.display_order,
        }
        if self.family_id is not None:
            result["family_id"] = self.family_id
        if self.metadata:
            result["metadata"] = json_safe(self.metadata)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PublicationStatistic":
        return cls(
            test_id=value.get("test_id"),
            raw_record=dict(value.get("raw_record") or {}),
            occurrences=[
                StatisticOccurrence.from_dict(item) for item in value.get("occurrences", [])
            ],
            displayed=bool(value.get("displayed", True)),
            source=str(value.get("source", "figure")),
            normalized=dict(value.get("normalized") or {}),
            family_id=value.get("family_id"),
            display_order=int(value.get("display_order", 0)),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class TestFamily:
    """A stable grouping of related statistical tests."""

    label: str
    test_ids: list[str] = field(default_factory=list)
    family_id: str | None = None
    method: str | None = None
    display_order: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.label = str(self.label)
        self.test_ids = sorted(str(test_id) for test_id in self.test_ids)
        if self.family_id is None:
            payload = {"label": self.label, "test_ids": self.test_ids}
            self.family_id = "test-family:" + _hash_mapping(payload)[:24]
        else:
            self.family_id = str(self.family_id)
        if self.method is not None:
            self.method = str(self.method)
        self.display_order = int(self.display_order)
        self.metadata = _dict(self.metadata)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "family_id": self.family_id,
            "label": self.label,
            "test_ids": list(self.test_ids),
            "display_order": self.display_order,
        }
        if self.method is not None:
            result["method"] = self.method
        if self.metadata:
            result["metadata"] = json_safe(self.metadata)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TestFamily":
        return cls(
            family_id=value.get("family_id"),
            label=str(value.get("label", "")),
            test_ids=[str(item) for item in value.get("test_ids", [])],
            method=value.get("method"),
            display_order=int(value.get("display_order", 0)),
            metadata=dict(value.get("metadata") or {}),
        )


@dataclass
class VerificationRow:
    """One deterministic verification result row."""

    subject_id: str
    status: str
    message: str = ""
    verification_id: str | None = None
    check: str = ""
    display_order: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.subject_id = str(self.subject_id)
        self.status = str(self.status)
        self.message = str(self.message)
        self.check = str(self.check)
        self.display_order = int(self.display_order)
        self.details = _dict(self.details)
        if self.verification_id is None:
            payload = {
                "check": self.check,
                "details": self.details,
                "message": self.message,
                "status": self.status,
                "subject_id": self.subject_id,
            }
            self.verification_id = "verification:" + _hash_mapping(payload)[:24]
        else:
            self.verification_id = str(self.verification_id)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "verification_id": self.verification_id,
            "subject_id": self.subject_id,
            "status": self.status,
            "check": self.check,
            "message": self.message,
            "display_order": self.display_order,
            "details": json_safe(self.details),
        }
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "VerificationRow":
        return cls(
            verification_id=value.get("verification_id"),
            subject_id=str(value.get("subject_id", "")),
            status=str(value.get("status", "")),
            check=str(value.get("check", "")),
            message=str(value.get("message", "")),
            display_order=int(value.get("display_order", 0)),
            details=dict(value.get("details") or {}),
        )


@dataclass
class CoverageDeclaration:
    """Evidence behind a dataset-level statistics coverage claim."""

    figure_ids: list[str] = field(default_factory=list)
    test_ids: list[str] = field(default_factory=list)
    ledger_sha256: str | None = None
    declared_by: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.figure_ids = sorted(str(figure_id) for figure_id in self.figure_ids)
        self.test_ids = sorted(str(test_id) for test_id in self.test_ids)
        if self.ledger_sha256 is not None:
            self.ledger_sha256 = str(self.ledger_sha256)
        if self.declared_by is not None:
            self.declared_by = str(self.declared_by)
        self.details = _dict(self.details)

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "figure_ids": list(self.figure_ids),
            "test_ids": list(self.test_ids),
        }
        if self.ledger_sha256 is not None:
            result["ledger_sha256"] = self.ledger_sha256
        if self.declared_by is not None:
            result["declared_by"] = self.declared_by
        if self.details:
            result["details"] = json_safe(self.details)
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CoverageDeclaration":
        return cls(
            figure_ids=[str(item) for item in value.get("figure_ids", [])],
            test_ids=[str(item) for item in value.get("test_ids", [])],
            ledger_sha256=value.get("ledger_sha256"),
            declared_by=value.get("declared_by"),
            details=dict(value.get("details") or {}),
        )


@dataclass
class PublicationDataset:
    """Logical publication workbook evidence independent of Excel bytes."""

    publication_id: str | None = None
    profile: str = "master"
    figures: list[PublicationFigure | Mapping[str, Any]] = field(default_factory=list)
    tables: list[PublicationTable | Mapping[str, Any]] = field(default_factory=list)
    statistics: list[PublicationStatistic | Mapping[str, Any]] = field(default_factory=list)
    test_families: list[TestFamily | Mapping[str, Any]] = field(default_factory=list)
    verification: list[VerificationRow | Mapping[str, Any]] = field(default_factory=list)
    statistics_coverage: str = "incomplete"
    coverage: CoverageDeclaration | Mapping[str, Any] = field(default_factory=CoverageDeclaration)
    schema: str = WORKBOOK_SCHEMA
    metadata: dict[str, Any] = field(default_factory=dict)
    build_metadata: dict[str, Any] = field(default_factory=dict)
    output_path: str | None = None
    worksheet_style: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.profile = str(self.profile)
        self.schema = str(self.schema)
        self.statistics_coverage = str(self.statistics_coverage)
        self.figures = sorted(
            [
                figure
                if isinstance(figure, PublicationFigure)
                else PublicationFigure.from_dict(figure)
                for figure in self.figures
            ],
            key=lambda figure: (figure.figure_id, figure.figure_record_sha256),
        )
        self.tables = sorted(
            [
                table if isinstance(table, PublicationTable) else PublicationTable.from_dict(table)
                for table in self.tables
            ],
            key=lambda table: (table.table_id or "", table.sha256),
        )
        self.statistics = sorted(
            [
                statistic
                if isinstance(statistic, PublicationStatistic)
                else PublicationStatistic.from_dict(statistic)
                for statistic in self.statistics
            ],
            key=lambda statistic: (statistic.test_id or "", _stable_json_sort_key(statistic)),
        )
        self.test_families = sorted(
            [
                family if isinstance(family, TestFamily) else TestFamily.from_dict(family)
                for family in self.test_families
            ],
            key=lambda family: (family.family_id or "", family.label),
        )
        self.verification = sorted(
            [
                row if isinstance(row, VerificationRow) else VerificationRow.from_dict(row)
                for row in self.verification
            ],
            key=lambda row: (row.verification_id or "", row.subject_id),
        )
        self.coverage = (
            self.coverage
            if isinstance(self.coverage, CoverageDeclaration)
            else CoverageDeclaration.from_dict(self.coverage)
        )
        self.metadata = _dict(self.metadata)
        self.build_metadata = _dict(self.build_metadata)
        if self.output_path is not None:
            self.output_path = str(self.output_path)
        self.worksheet_style = _dict(self.worksheet_style)
        if not self.publication_id:
            self.publication_id = self.default_publication_id()
        else:
            self.publication_id = str(self.publication_id)

    def _dict(
        self,
        *,
        include_publication_id: bool,
        include_convenience: bool,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "schema": self.schema,
            "profile": self.profile,
            "figures": [figure.to_dict() for figure in self.figures],
            "tables": [table.to_dict() for table in self.tables],
            "statistics": [statistic.to_dict() for statistic in self.statistics],
            "test_families": [family.to_dict() for family in self.test_families],
            "verification": [row.to_dict() for row in self.verification],
            "statistics_coverage": self.statistics_coverage,
            "coverage": self.coverage.to_dict(),
        }
        if include_publication_id:
            result["publication_id"] = self.publication_id
        if self.metadata:
            result["metadata"] = json_safe(self.metadata)
        if include_convenience:
            if self.build_metadata:
                result["build_metadata"] = json_safe(self.build_metadata)
            if self.output_path is not None:
                result["output_path"] = self.output_path
            if self.worksheet_style:
                result["worksheet_style"] = json_safe(self.worksheet_style)
        return result

    def default_publication_id(self) -> str:
        evidence = self._dict(include_publication_id=False, include_convenience=False)
        return "publication:" + _hash_mapping(evidence)[:24]

    def evidence_dict(self) -> dict[str, Any]:
        """Return canonical logical evidence, excluding Excel/build conveniences."""

        return self._dict(include_publication_id=True, include_convenience=False)

    def fingerprint(self) -> str:
        return _hash_mapping(self.evidence_dict())

    def to_dict(self) -> dict[str, Any]:
        return self._dict(include_publication_id=True, include_convenience=True)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PublicationDataset":
        return cls(
            publication_id=value.get("publication_id"),
            profile=str(value.get("profile", "master")),
            figures=[PublicationFigure.from_dict(item) for item in value.get("figures", [])],
            tables=[PublicationTable.from_dict(item) for item in value.get("tables", [])],
            statistics=[
                PublicationStatistic.from_dict(item) for item in value.get("statistics", [])
            ],
            test_families=[TestFamily.from_dict(item) for item in value.get("test_families", [])],
            verification=[VerificationRow.from_dict(item) for item in value.get("verification", [])],
            statistics_coverage=str(value.get("statistics_coverage", "incomplete")),
            coverage=CoverageDeclaration.from_dict(value.get("coverage") or {}),
            schema=str(value.get("schema", WORKBOOK_SCHEMA)),
            metadata=dict(value.get("metadata") or {}),
            build_metadata=dict(value.get("build_metadata") or {}),
            output_path=value.get("output_path"),
            worksheet_style=dict(value.get("worksheet_style") or {}),
        )

    def to_json(self, *, indent: int | None = None) -> str:
        return deterministic_json(self.to_dict(), indent=indent)

    @classmethod
    def from_json(cls, value: str | bytes) -> "PublicationDataset":
        if isinstance(value, bytes):
            value = value.decode("utf-8")
        parsed = json.loads(value)
        if not isinstance(parsed, dict):
            raise ValueError("PublicationDataset JSON must contain one object")
        return cls.from_dict(parsed)

    def validate(self) -> list[str]:
        errors: list[str] = []
        if self.schema != WORKBOOK_SCHEMA:
            errors.append(f"unsupported workbook schema: {self.schema}")
        if self.profile not in PUBLICATION_PROFILES:
            errors.append(
                f"profile must be one of {sorted(PUBLICATION_PROFILES)}, not {self.profile!r}"
            )
        if self.statistics_coverage not in COVERAGE_STATUSES:
            errors.append(
                "statistics_coverage must be one of "
                f"{sorted(COVERAGE_STATUSES)}, not {self.statistics_coverage!r}"
            )
        if not self.publication_id:
            errors.append("publication_id is missing")
        elif not self.publication_id.startswith("publication:"):
            errors.append("publication_id must start with 'publication:'")

        figure_sha_by_id: dict[str, str] = {}
        for figure in self.figures:
            previous = figure_sha_by_id.get(figure.figure_id)
            if not figure.figure_id:
                errors.append("figure_id is missing")
            elif previous is None:
                figure_sha_by_id[figure.figure_id] = figure.figure_record_sha256
            elif previous != figure.figure_record_sha256:
                errors.append(
                    "conflicting figures share figure_id "
                    f"{figure.figure_id!r} with different figure_record_sha256 values"
                )
            else:
                errors.append(f"duplicate figure_id: {figure.figure_id}")
            if not figure.figure_record_sha256:
                errors.append(f"figure_record_sha256 is missing for {figure.figure_id}")
            elif not _is_sha256(figure.figure_record_sha256):
                errors.append(f"figure_record_sha256 is not a SHA-256 hex digest: {figure.figure_id}")
            if figure.profile not in PUBLICATION_PROFILES:
                errors.append(
                    f"figure profile must be one of {sorted(PUBLICATION_PROFILES)}: {figure.figure_id}"
                )

        table_ids: set[str] = set()
        table_contents_by_hash: dict[str, str | None] = {}
        occurrence_ids: set[str] = set()
        for table in self.tables:
            expected_table_id = f"table:{table.sha256}"
            if not table.table_id:
                errors.append("table_id is missing")
            elif table.table_id in table_ids:
                errors.append(f"duplicate table_id: {table.table_id}")
            else:
                table_ids.add(table.table_id)
            if table.table_id and table.table_id != expected_table_id:
                errors.append(
                    f"table_id must be {expected_table_id!r} for table hash {table.sha256}"
                )
            if not table.sha256:
                errors.append(f"table sha256 is missing: {table.table_id}")
            elif not _is_sha256(table.sha256):
                errors.append(f"table sha256 is not a SHA-256 hex digest: {table.table_id}")
            if table.column_count != len(table.columns):
                errors.append(f"table column metadata mismatch: {table.table_id}")
            if table.row_count < 0:
                errors.append(f"table row_count cannot be negative: {table.table_id}")
            if table.column_count < 0:
                errors.append(f"table column_count cannot be negative: {table.table_id}")
            if not table.verify():
                errors.append(f"table hash mismatch: {table.table_id}")
            previous_contents = table_contents_by_hash.get(table.sha256)
            if table.sha256 in table_contents_by_hash and previous_contents != table.contents:
                errors.append(f"conflicting table bytes share sha256 {table.sha256}")
            else:
                table_contents_by_hash[table.sha256] = table.contents
            for occurrence in table.occurrences:
                if occurrence.occurrence_id in occurrence_ids:
                    errors.append(f"duplicate table occurrence_id: {occurrence.occurrence_id}")
                else:
                    occurrence_ids.add(str(occurrence.occurrence_id))
                if occurrence.table_index < 0:
                    errors.append(
                        f"table occurrence index cannot be negative: {occurrence.occurrence_id}"
                    )
                if occurrence.figure_id not in figure_sha_by_id:
                    errors.append(
                        f"table occurrence references unknown figure_id: {occurrence.figure_id}"
                    )
                elif (
                    occurrence.figure_record_sha256
                    and occurrence.figure_record_sha256 != figure_sha_by_id[occurrence.figure_id]
                ):
                    errors.append(
                        "table occurrence figure_record_sha256 does not match figure "
                        f"{occurrence.figure_id}"
                    )

        statistic_ids: set[str] = set()
        statistic_occurrence_ids: set[str] = set()
        for statistic in self.statistics:
            if not statistic.test_id:
                errors.append("test_id is missing")
            elif statistic.test_id in statistic_ids:
                errors.append(f"duplicate test_id: {statistic.test_id}")
            else:
                statistic_ids.add(statistic.test_id)
            if statistic.source not in STATISTIC_SOURCES:
                errors.append(
                    f"statistic source must be one of {sorted(STATISTIC_SOURCES)}: {statistic.test_id}"
                )
            for occurrence in statistic.occurrences:
                if occurrence.occurrence_id in statistic_occurrence_ids:
                    errors.append(
                        f"duplicate statistic occurrence_id: {occurrence.occurrence_id}"
                    )
                else:
                    statistic_occurrence_ids.add(str(occurrence.occurrence_id))
                if occurrence.statistic_index < 0:
                    errors.append(
                        "statistic occurrence index cannot be negative: "
                        f"{occurrence.occurrence_id}"
                    )
                if occurrence.figure_id not in figure_sha_by_id:
                    errors.append(
                        f"statistic occurrence references unknown figure_id: {occurrence.figure_id}"
                    )
                elif (
                    occurrence.figure_record_sha256
                    and occurrence.figure_record_sha256 != figure_sha_by_id[occurrence.figure_id]
                ):
                    errors.append(
                        "statistic occurrence figure_record_sha256 does not match figure "
                        f"{occurrence.figure_id}"
                    )

        family_ids: set[str] = set()
        for family in self.test_families:
            if not family.family_id:
                errors.append("family_id is missing")
            elif family.family_id in family_ids:
                errors.append(f"duplicate family_id: {family.family_id}")
            else:
                family_ids.add(family.family_id)
            for test_id in family.test_ids:
                if test_id not in statistic_ids:
                    errors.append(f"test family references unknown test_id: {test_id}")

        verification_ids: set[str] = set()
        for row in self.verification:
            if not row.verification_id:
                errors.append("verification_id is missing")
            elif row.verification_id in verification_ids:
                errors.append(f"duplicate verification_id: {row.verification_id}")
            else:
                verification_ids.add(row.verification_id)

        for figure_id in self.coverage.figure_ids:
            if figure_id not in figure_sha_by_id:
                errors.append(f"coverage references unknown figure_id: {figure_id}")
        for test_id in self.coverage.test_ids:
            if test_id not in statistic_ids:
                errors.append(f"coverage references unknown test_id: {test_id}")
        if self.coverage.ledger_sha256 and not _is_sha256(self.coverage.ledger_sha256):
            errors.append("coverage ledger_sha256 is not a SHA-256 hex digest")
        return errors


__all__ = [
    "COVERAGE_STATUSES",
    "WORKBOOK_SCHEMA",
    "CoverageDeclaration",
    "CoverageStatus",
    "PublicationDataset",
    "PublicationFigure",
    "PublicationStatistic",
    "PublicationTable",
    "StatisticOccurrence",
    "TableOccurrence",
    "TestFamily",
    "VerificationRow",
]
