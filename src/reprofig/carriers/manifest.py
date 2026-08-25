"""Format-neutral manifest connecting carrier files to figure records."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from ..schema import FigureRecord, deterministic_json, json_safe, sha256_bytes
from .base import CarrierError
from .payload import decode_record, encode_record

CARRIER_SCHEMA = "reprofig-carrier/1"


@dataclass
class CarrierRecordEntry:
    figure_id: str
    profile: str
    record_sha256: str
    payload: str
    encoding: str = "gzip+base64"
    schema: str = "reprofig/1"
    target: dict[str, Any] = field(default_factory=dict)
    render: dict[str, Any] = field(default_factory=dict)
    record_path: str | None = None

    @classmethod
    def from_record(
        cls,
        record: FigureRecord,
        *,
        target: Mapping[str, Any] | None = None,
        render: Mapping[str, Any] | None = None,
    ) -> "CarrierRecordEntry":
        raw = record.to_json().encode("utf-8")
        return cls(
            figure_id=record.figure_id,
            profile=record.distribution_profile,
            record_sha256=sha256_bytes(raw),
            payload=encode_record(record),
            schema=record.schema,
            target=dict(json_safe(target or {})),
            render=dict(json_safe(render or {})),
        )

    def record(
        self,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> FigureRecord:
        if self.encoding != "gzip+base64":
            raise CarrierError(f"unsupported record encoding {self.encoding!r}")
        record = decode_record(
            self.payload,
            max_compressed=max_compressed,
            max_decompressed=max_decompressed,
        )
        if record.figure_id != self.figure_id:
            raise CarrierError("carrier figure identifier disagrees with record")
        if record.schema != self.schema:
            raise CarrierError("carrier schema disagrees with record")
        if sha256_bytes(record.to_json().encode("utf-8")) != self.record_sha256:
            raise CarrierError("embedded record hash mismatch")
        return record

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "figure_id": self.figure_id,
            "profile": self.profile,
            "record_sha256": self.record_sha256,
            "encoding": self.encoding,
            "schema": self.schema,
            "payload": self.payload,
        }
        if self.target:
            result["target"] = json_safe(self.target)
        if self.render:
            result["render"] = json_safe(self.render)
        if self.record_path:
            result["record_path"] = self.record_path
        return result

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CarrierRecordEntry":
        return cls(
            figure_id=str(value.get("figure_id", "")),
            profile=str(value.get("profile", "master")),
            record_sha256=str(value.get("record_sha256", "")),
            encoding=str(value.get("encoding", "gzip+base64")),
            schema=str(value.get("schema", "reprofig/1")),
            payload=str(value.get("payload", "")),
            target=dict(value.get("target") or {}),
            render=dict(value.get("render") or {}),
            record_path=value.get("record_path"),
        )


@dataclass
class CarrierManifest:
    format: str
    records: list[CarrierRecordEntry]
    media_type: str | None = None
    carrier: dict[str, Any] = field(default_factory=dict)
    created_by: dict[str, Any] = field(
        default_factory=lambda: {"package": "reprofig", "version": "0.2.0"}
    )
    schema: str = CARRIER_SCHEMA

    @classmethod
    def for_records(
        cls,
        format: str,
        records: Sequence[FigureRecord],
        *,
        media_type: str | None = None,
        targets: Sequence[Mapping[str, Any] | None] | None = None,
        renders: Sequence[Mapping[str, Any] | None] | None = None,
        carrier: Mapping[str, Any] | None = None,
    ) -> "CarrierManifest":
        targets = list(targets or [None] * len(records))
        renders = list(renders or [None] * len(records))
        if len(targets) != len(records) or len(renders) != len(records):
            raise ValueError("targets and renders must match the record count")
        return cls(
            format=format,
            media_type=media_type,
            records=[
                CarrierRecordEntry.from_record(record, target=target, render=render)
                for record, target, render in zip(records, targets, renders)
            ],
            carrier=dict(json_safe(carrier or {})),
        )

    def to_dict(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "carrier_schema": self.schema,
            "created_by": json_safe(self.created_by),
            "format": self.format,
            "records": [record.to_dict() for record in self.records],
        }
        if self.media_type:
            result["media_type"] = self.media_type
        if self.carrier:
            result["carrier"] = json_safe(self.carrier)
        return result

    def to_json(self, *, indent: int | None = None) -> str:
        return deterministic_json(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "CarrierManifest":
        schema = value.get("carrier_schema", value.get("schema"))
        if schema != CARRIER_SCHEMA:
            raise CarrierError(f"unsupported carrier schema {schema!r}")
        records = [CarrierRecordEntry.from_dict(item) for item in value.get("records", [])]
        if not records:
            raise CarrierError("carrier manifest has no records")
        return cls(
            schema=CARRIER_SCHEMA,
            format=str(value.get("format", "")),
            media_type=value.get("media_type"),
            records=records,
            carrier=dict(value.get("carrier") or {}),
            created_by=dict(value.get("created_by") or {}),
        )

    @classmethod
    def from_json(cls, value: str | bytes) -> "CarrierManifest":
        try:
            parsed = json.loads(value)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise CarrierError("carrier manifest JSON is invalid") from exc
        if not isinstance(parsed, dict):
            raise CarrierError("carrier manifest must contain one object")
        return cls.from_dict(parsed)

    def extract_records(
        self,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> list[FigureRecord]:
        return [
            entry.record(
                max_compressed=max_compressed,
                max_decompressed=max_decompressed,
            )
            for entry in self.records
        ]
