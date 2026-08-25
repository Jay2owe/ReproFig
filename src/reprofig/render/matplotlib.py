"""Explicit bindings and semantic capture for Matplotlib figures."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

from ..schema import sha256_bytes
from .schema import AnnotationSemantic, AxesSemantic, MarkSemantic, RenderManifest


def bind_artist(
    artist: Any,
    *,
    semantic_id: str,
    table_id: str | None = None,
    row_ids: Sequence[str] = (),
    columns: Sequence[str] = (),
    statistic_id: str | None = None,
    role: str | None = None,
    connected_mark_ids: Sequence[str] = (),
    formatter_id: str | None = None,
) -> Any:
    """Bind a live artist to scientific evidence and emit a stable vector identity."""

    binding = {
        "semantic_id": str(semantic_id), "table_id": table_id,
        "row_ids": [str(value) for value in row_ids], "columns": [str(value) for value in columns],
        "statistic_id": statistic_id, "role": role,
        "connected_mark_ids": [str(value) for value in connected_mark_ids],
        "formatter_id": formatter_id,
    }
    setattr(artist, "_reprofig_binding", binding)
    if hasattr(artist, "set_gid"):
        artist.set_gid(str(semantic_id))
    return artist


def _binding(artist: Any) -> dict[str, Any]:
    return dict(getattr(artist, "_reprofig_binding", {}) or {})


def capture_matplotlib(figure: Any) -> RenderManifest:
    """Capture supported scientific artists after layout and before save."""

    figure.canvas.draw()
    axes_values: list[AxesSemantic] = []
    marks: list[MarkSemantic] = []
    annotations: list[AnnotationSemantic] = []
    unsupported: list[dict[str, Any]] = []
    for axes_index, axes in enumerate(figure.axes):
        axes_id = str(axes.get_gid() or f"axes-{axes_index}")
        axes.set_gid(axes_id)
        bbox = axes.get_position().bounds
        axes_values.append(AxesSemantic(
            axes_id=axes_id, x_scale=axes.get_xscale(), y_scale=axes.get_yscale(),
            x_limits=tuple(map(float, axes.get_xlim())), y_limits=tuple(map(float, axes.get_ylim())),
            bbox_inches=tuple(map(float, bbox)),
            labels={"x": axes.get_xlabel(), "y": axes.get_ylabel(), "title": axes.get_title()},
        ))
        for index, line in enumerate(axes.lines):
            binding = _binding(line)
            mark_id = str(binding.get("semantic_id") or line.get_gid() or f"{axes_id}-line-{index}")
            line.set_gid(mark_id)
            marks.append(MarkSemantic(
                mark_id=mark_id, kind="line", axes_id=axes_id,
                geometry={"x": [float(value) for value in line.get_xdata()], "y": [float(value) for value in line.get_ydata()]},
                table_id=binding.get("table_id"), row_ids=binding.get("row_ids", []),
                columns=binding.get("columns", []), role=binding.get("role"),
            ))
        for index, collection in enumerate(axes.collections):
            binding = _binding(collection)
            mark_id = str(binding.get("semantic_id") or collection.get_gid() or f"{axes_id}-collection-{index}")
            collection.set_gid(mark_id)
            if hasattr(collection, "get_offsets") and len(collection.get_offsets()):
                offsets = [[float(a), float(b)] for a, b in collection.get_offsets()]
                kind, geometry = "points", {"points": offsets}
            elif hasattr(collection, "get_segments"):
                kind, geometry = "intervals", {"segments": [[[float(a), float(b)] for a, b in segment] for segment in collection.get_segments()]}
            elif hasattr(collection, "get_paths"):
                kind, geometry = "area", {"paths": [[[float(a), float(b)] for a, b in path.vertices] for path in collection.get_paths()]}
            else:
                unsupported.append({"axes_id": axes_id, "artist": type(collection).__name__, "semantic_id": mark_id})
                continue
            marks.append(MarkSemantic(
                mark_id=mark_id, kind=kind, axes_id=axes_id, geometry=geometry,
                table_id=binding.get("table_id"), row_ids=binding.get("row_ids", []),
                columns=binding.get("columns", []), role=binding.get("role"),
            ))
        for index, patch in enumerate(axes.patches):
            binding = _binding(patch)
            if not binding and patch is axes.patch:
                continue
            mark_id = str(binding.get("semantic_id") or patch.get_gid() or f"{axes_id}-patch-{index}")
            patch.set_gid(mark_id)
            if hasattr(patch, "get_x") and hasattr(patch, "get_width"):
                geometry = {"x": float(patch.get_x()), "y": float(patch.get_y()), "width": float(patch.get_width()), "height": float(patch.get_height())}
                kind = "bar"
            else:
                unsupported.append({"axes_id": axes_id, "artist": type(patch).__name__, "semantic_id": mark_id})
                continue
            marks.append(MarkSemantic(
                mark_id=mark_id, kind=kind, axes_id=axes_id, geometry=geometry,
                table_id=binding.get("table_id"), row_ids=binding.get("row_ids", []),
                columns=binding.get("columns", []), role=binding.get("role"),
            ))
        for index, image in enumerate(axes.images):
            binding = _binding(image)
            mark_id = str(
                binding.get("semantic_id")
                or image.get_gid()
                or f"{axes_id}-image-{index}"
            )
            image.set_gid(mark_id)
            array = image.get_array()
            raw = array.tobytes(order="C")
            marks.append(
                MarkSemantic(
                    mark_id=mark_id,
                    kind="image",
                    axes_id=axes_id,
                    geometry={
                        "extent": [float(value) for value in image.get_extent()],
                        "shape": [int(value) for value in array.shape],
                        "dtype": str(array.dtype),
                        "array_sha256": sha256_bytes(raw),
                    },
                    table_id=binding.get("table_id"),
                    row_ids=binding.get("row_ids", []),
                    columns=binding.get("columns", []),
                    role=binding.get("role"),
                )
            )
        for index, text in enumerate(axes.texts):
            if not text.get_visible() or not text.get_text():
                continue
            binding = _binding(text)
            annotation_id = str(binding.get("semantic_id") or text.get_gid() or f"{axes_id}-text-{index}")
            text.set_gid(annotation_id)
            annotations.append(AnnotationSemantic(
                annotation_id=annotation_id, text=text.get_text(), axes_id=axes_id,
                position=tuple(map(float, text.get_position())),
                coordinate_system="data" if text.get_transform() is axes.transData else "display",
                statistic_id=binding.get("statistic_id"), formatter_id=binding.get("formatter_id"),
                connected_mark_ids=binding.get("connected_mark_ids", []), role=binding.get("role") or "text",
            ))
    size = [float(value) for value in figure.get_size_inches()]
    return RenderManifest(
        axes=axes_values, marks=marks, annotations=annotations, unsupported=unsupported,
        environment={"backend": str(figure.canvas.__class__.__module__), "figure_inches": size, "dpi": float(figure.dpi)},
    )


__all__ = ["bind_artist", "capture_matplotlib"]
