"""Package-neutral semantic description of visible scientific marks."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

from ..schema import deterministic_json, json_safe, sha256_bytes


def _identity(prefix: str, value: Mapping[str, Any]) -> str:
    return prefix + ":" + sha256_bytes(deterministic_json(value).encode("utf-8"))[:24]


@dataclass
class AxesSemantic:
    axes_id: str
    x_scale: str = "linear"
    y_scale: str = "linear"
    x_limits: tuple[float, float] | None = None
    y_limits: tuple[float, float] | None = None
    bbox_inches: tuple[float, float, float, float] | None = None
    labels: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {key: json_safe(value) for key, value in vars(self).items() if value not in (None, {})}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AxesSemantic":
        return cls(
            axes_id=str(value.get("axes_id", "")), x_scale=str(value.get("x_scale", "linear")),
            y_scale=str(value.get("y_scale", "linear")),
            x_limits=tuple(value["x_limits"]) if value.get("x_limits") is not None else None,
            y_limits=tuple(value["y_limits"]) if value.get("y_limits") is not None else None,
            bbox_inches=tuple(value["bbox_inches"]) if value.get("bbox_inches") is not None else None,
            labels=dict(value.get("labels") or {}),
        )


@dataclass
class MarkSemantic:
    kind: str
    axes_id: str
    geometry: dict[str, Any]
    mark_id: str | None = None
    coordinate_system: str = "data"
    table_id: str | None = None
    row_ids: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    role: str | None = None
    style: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.geometry = dict(json_safe(self.geometry))
        if not self.mark_id:
            self.mark_id = _identity("mark", {"kind": self.kind, "axes_id": self.axes_id, "geometry": self.geometry})

    def to_dict(self) -> dict[str, Any]:
        return {key: json_safe(value) for key, value in vars(self).items() if value not in (None, [], {})}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "MarkSemantic":
        return cls(
            mark_id=value.get("mark_id"), kind=str(value.get("kind", "unknown")),
            axes_id=str(value.get("axes_id", "")), geometry=dict(value.get("geometry") or {}),
            coordinate_system=str(value.get("coordinate_system", "data")),
            table_id=value.get("table_id"), row_ids=[str(item) for item in value.get("row_ids", [])],
            columns=[str(item) for item in value.get("columns", [])], role=value.get("role"),
            style=dict(value.get("style") or {}),
        )


@dataclass
class AnnotationSemantic:
    text: str
    axes_id: str
    position: tuple[float, float]
    annotation_id: str | None = None
    coordinate_system: str = "data"
    statistic_id: str | None = None
    formatter_id: str | None = None
    connected_mark_ids: list[str] = field(default_factory=list)
    role: str = "text"

    def __post_init__(self) -> None:
        if not self.annotation_id:
            self.annotation_id = _identity("annotation", {"text": self.text, "axes_id": self.axes_id, "position": self.position, "statistic_id": self.statistic_id})

    def to_dict(self) -> dict[str, Any]:
        return {key: json_safe(value) for key, value in vars(self).items() if value not in (None, [], {})}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "AnnotationSemantic":
        return cls(
            annotation_id=value.get("annotation_id"), text=str(value.get("text", "")),
            axes_id=str(value.get("axes_id", "")), position=tuple(value.get("position", (0, 0))),
            coordinate_system=str(value.get("coordinate_system", "data")),
            statistic_id=value.get("statistic_id"), formatter_id=value.get("formatter_id"),
            connected_mark_ids=[str(item) for item in value.get("connected_mark_ids", [])],
            role=str(value.get("role", "text")),
        )


@dataclass
class RenderManifest:
    axes: list[AxesSemantic | Mapping[str, Any]] = field(default_factory=list)
    marks: list[MarkSemantic | Mapping[str, Any]] = field(default_factory=list)
    annotations: list[AnnotationSemantic | Mapping[str, Any]] = field(default_factory=list)
    unsupported: list[dict[str, Any]] = field(default_factory=list)
    environment: dict[str, Any] = field(default_factory=dict)
    schema: str = "reprofig-render-manifest/1"

    def __post_init__(self) -> None:
        self.axes = [value if isinstance(value, AxesSemantic) else AxesSemantic.from_dict(value) for value in self.axes]
        self.marks = [value if isinstance(value, MarkSemantic) else MarkSemantic.from_dict(value) for value in self.marks]
        self.annotations = [value if isinstance(value, AnnotationSemantic) else AnnotationSemantic.from_dict(value) for value in self.annotations]
        identities = [value.axes_id for value in self.axes] + [str(value.mark_id) for value in self.marks] + [str(value.annotation_id) for value in self.annotations]
        if len(identities) != len(set(identities)):
            raise ValueError("render manifest contains duplicate semantic identities")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "axes": [value.to_dict() for value in self.axes],
            "marks": [value.to_dict() for value in self.marks],
            "annotations": [value.to_dict() for value in self.annotations],
            "unsupported": json_safe(self.unsupported),
            "environment": json_safe(self.environment),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RenderManifest":
        if value.get("schema") not in (None, "reprofig-render-manifest/1"):
            raise ValueError(f"unsupported render manifest schema {value.get('schema')!r}")
        return cls(
            axes=list(value.get("axes", [])), marks=list(value.get("marks", [])),
            annotations=list(value.get("annotations", [])), unsupported=list(value.get("unsupported", [])),
            environment=dict(value.get("environment") or {}),
        )


__all__ = ["AnnotationSemantic", "AxesSemantic", "MarkSemantic", "RenderManifest"]
