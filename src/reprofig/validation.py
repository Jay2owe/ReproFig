"""Integrity and publication-safety validation."""

from __future__ import annotations

import os
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Mapping

from .schema import FigureRecord, deterministic_json, sha256_bytes
from .svg import FigureRecordError, extract_record
from .tables import statistics_csv_bytes

_WINDOWS_ABSOLUTE = re.compile(
    r"(?i)(?<![A-Za-z0-9])(?:[A-Z]:[\\/](?:[^\s<>'\"|]+[\\/]?)+)"
)
_UNC_PATH = re.compile(r"\\\\[^\\\s]+\\[^\s<>'\"]+")
_FILE_URI = re.compile(r"(?i)file://[^\s<>'\"]+")
_TOKEN = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|authorization|password|passwd)"
    r"\s*[:=]\s*['\"]?[^\s,'\"}]+"
)
_POSIX_PRIVATE = re.compile(r"(?<![A-Za-z0-9])/(?:home|Users|mnt|media)/[^\s<>'\"]+")


@dataclass
class ValidationIssue:
    severity: str
    code: str
    message: str
    location: str | None = None

    def to_dict(self) -> dict[str, Any]:
        value = {"severity": self.severity, "code": self.code, "message": self.message}
        if self.location:
            value["location"] = self.location
        return value


@dataclass
class ValidationReport:
    path: str | None = None
    profile: str | None = None
    issues: list[ValidationIssue] = field(default_factory=list)
    checks: list[str] = field(default_factory=list)
    transformations: list[str] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not any(issue.severity == "error" for issue in self.issues)

    def add(self, severity: str, code: str, message: str, location: str | None = None) -> None:
        self.issues.append(ValidationIssue(severity, code, message, location))

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "profile": self.profile,
            "valid": self.valid,
            "checks": list(self.checks),
            "transformations": list(self.transformations),
            "issues": [issue.to_dict() for issue in self.issues],
        }


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].rsplit(":", 1)[-1].lower()


def privacy_leaks(value: str) -> list[tuple[str, str]]:
    leaks: list[tuple[str, str]] = []
    for code, pattern in (
        ("windows_absolute_path", _WINDOWS_ABSOLUTE),
        ("unc_path", _UNC_PATH),
        ("file_uri", _FILE_URI),
        ("private_posix_path", _POSIX_PRIVATE),
        ("credential", _TOKEN),
    ):
        for match in pattern.finditer(value):
            excerpt = match.group(0)
            if len(excerpt) > 120:
                excerpt = excerpt[:117] + "..."
            leaks.append((code, excerpt))
    return leaks


def scrub_private_strings(value: Any) -> Any:
    """Replace local paths and credential-shaped strings recursively."""

    if isinstance(value, str):
        scrubbed = _WINDOWS_ABSOLUTE.sub(
            lambda match: "${DATA_ROOT}/" + Path(match.group(0).replace("\\", "/")).name,
            value,
        )
        scrubbed = _UNC_PATH.sub(
            lambda match: "${DATA_ROOT}/" + match.group(0).replace("\\", "/").rsplit("/", 1)[-1],
            scrubbed,
        )
        scrubbed = _FILE_URI.sub("${DATA_ROOT}/source", scrubbed)
        scrubbed = _POSIX_PRIVATE.sub(
            lambda match: "${DATA_ROOT}/" + match.group(0).rsplit("/", 1)[-1], scrubbed
        )
        scrubbed = _TOKEN.sub("credential=[REDACTED]", scrubbed)
        return scrubbed
    if isinstance(value, Mapping):
        return {str(key): scrub_private_strings(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set, frozenset)):
        return [scrub_private_strings(item) for item in value]
    return value


def validate_record(record: FigureRecord, *, require_complete: bool = False) -> ValidationReport:
    report = ValidationReport(profile=record.distribution_profile)
    report.checks.extend(
        ["schema", "figure_identity", "data_table_integrity", "statistics_integrity"]
    )
    for error in record.validate(require_complete=require_complete):
        report.add("error", "record_invalid", error)
    expected = record.statistics_csv_sha256
    actual = sha256_bytes(statistics_csv_bytes(record.statistics))
    if expected and expected != actual:
        report.add("error", "statistics_hash_mismatch", "normalized statistics CSV hash differs")
    if record.statistics_status == "complete" and not expected:
        report.add("error", "statistics_hash_missing", "complete statistics have no CSV hash")
    return report


def validate_svg(
    path: str | os.PathLike[str],
    *,
    expected_profile: str | None = None,
    require_complete: bool = False,
    public_safety: bool | None = None,
) -> ValidationReport:
    svg_path = Path(path)
    report = ValidationReport(path=str(svg_path))
    report.checks.extend(
        [
            "well_formed_xml",
            "embedded_record",
            "record_integrity",
            "scripts_and_event_handlers",
            "linked_images",
        ]
    )
    try:
        record = extract_record(svg_path)
    except (OSError, FigureRecordError) as exc:
        report.add("error", "record_unreadable", str(exc))
        return report
    report.profile = record.distribution_profile
    nested = validate_record(record, require_complete=require_complete)
    report.issues.extend(nested.issues)
    if expected_profile and record.distribution_profile != expected_profile:
        report.add(
            "error",
            "profile_mismatch",
            f"expected {expected_profile}, found {record.distribution_profile}",
        )
    if public_safety is None:
        public_safety = record.distribution_profile in {"public", "minimal_public"}
    try:
        root = ET.parse(svg_path).getroot()
    except ET.ParseError as exc:
        report.add("error", "xml_invalid", str(exc))
        return report
    for element in root.iter():
        tag = _local_name(element.tag)
        if tag == "script":
            report.add("error", "script_element", "SVG contains a script element")
        if tag == "foreignobject":
            report.add("error", "foreign_object", "SVG contains embedded foreign content")
        if tag == "style" and element.text:
            css = element.text
            if "@import" in css.lower() or re.search(
                r"url\(\s*['\"]?(?!data:|#)[^)]+\)", css, flags=re.IGNORECASE
            ):
                report.add("error", "external_style", "SVG style loads external content")
        for attribute, value in element.attrib.items():
            local_attribute = _local_name(attribute)
            if local_attribute.startswith("on"):
                report.add(
                    "error",
                    "event_handler",
                    f"SVG contains event handler {local_attribute}",
                    tag,
                )
            if tag == "image" and local_attribute == "href":
                if not value.startswith(("data:", "#")):
                    report.add(
                        "error",
                        "linked_image",
                        "image content is externally linked rather than embedded",
                        value,
                    )
            if local_attribute == "style" and re.search(
                r"url\(\s*['\"]?(?!data:|#)[^)]+\)", value, flags=re.IGNORECASE
            ):
                report.add("error", "external_style", "SVG style loads external content", tag)
    if public_safety:
        report.checks.append("private_paths_and_credentials")
        text = svg_path.read_text(encoding="utf-8-sig")
        for code, excerpt in privacy_leaks(text):
            report.add("error", code, "public SVG contains private material", excerpt)
        for code, excerpt in record_has_private_strings(record):
            report.add(
                "error",
                "record_" + code,
                "public embedded record contains private material",
                excerpt,
            )
        if record.distribution_profile == "public":
            for table in record.data_tables:
                unsafe = [column.name for column in table.columns if column.public_state != "safe"]
                if unsafe:
                    report.add(
                        "error",
                        "unsafe_public_columns",
                        f"public table {table.name} contains unapproved columns: {unsafe}",
                    )
        if record.distribution_profile == "minimal_public":
            embedded = [table.name for table in record.data_tables if table.contents is not None]
            if embedded:
                report.add(
                    "error",
                    "minimal_data_embedded",
                    f"minimal_public SVG embeds row-level tables: {embedded}",
                )
    return report


def merge_reports(reports: Iterable[ValidationReport]) -> ValidationReport:
    combined = ValidationReport()
    for report in reports:
        combined.checks.extend(report.checks)
        combined.transformations.extend(report.transformations)
        combined.issues.extend(report.issues)
    combined.checks = list(dict.fromkeys(combined.checks))
    combined.transformations = list(dict.fromkeys(combined.transformations))
    return combined


def record_has_private_strings(record: FigureRecord) -> list[tuple[str, str]]:
    return privacy_leaks(deterministic_json(record.to_dict()))
