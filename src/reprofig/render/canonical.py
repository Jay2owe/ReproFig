"""Canonical raster reference capture and environment facts."""

from __future__ import annotations

import base64
import gzip
import math
from pathlib import Path
from typing import Any, Mapping

from ..schema import sha256_bytes

MAX_REFERENCE_BYTES = 50 * 1024 * 1024


def _number_pairs(value: Any) -> list[tuple[float, float]]:
    pairs: list[tuple[float, float]] = []
    if isinstance(value, Mapping):
        for nested in value.values():
            pairs.extend(_number_pairs(nested))
    elif isinstance(value, (list, tuple)):
        if (
            len(value) == 2
            and all(isinstance(item, (int, float)) for item in value)
        ):
            pairs.append((float(value[0]), float(value[1])))
        else:
            for nested in value:
                pairs.extend(_number_pairs(nested))
    return pairs


def _scale(value: float, limits: tuple[float, float], mode: str) -> float:
    low, high = limits
    if mode == "log":
        if value <= 0 or low <= 0 or high <= 0:
            raise ValueError("log-scale visual coordinates must be positive")
        value, low, high = math.log10(value), math.log10(low), math.log10(high)
    if high == low:
        return 0.5
    return (value - low) / (high - low)


def _semantic_regions(
    manifest: Any | None, *, width: int, height: int
) -> list[dict[str, Any]]:
    if manifest is None:
        return []
    from .schema import RenderManifest

    value = manifest if isinstance(manifest, RenderManifest) else RenderManifest.from_dict(manifest)
    axes = {str(item.axes_id): item for item in value.axes}
    regions: list[dict[str, Any]] = []
    def mark_points(mark: Any) -> list[tuple[float, float]]:
        geometry = mark.geometry
        if mark.kind == "line":
            return [
                (float(x), float(y))
                for x, y in zip(geometry.get("x", []), geometry.get("y", []))
            ]
        if mark.kind == "points":
            return [tuple(map(float, point)) for point in geometry.get("points", [])]
        if mark.kind == "intervals":
            return _number_pairs(geometry.get("segments", []))
        if mark.kind == "bar":
            x, y = float(geometry.get("x", 0)), float(geometry.get("y", 0))
            width = float(geometry.get("width", 0))
            height_value = float(geometry.get("height", 0))
            return [(x, y), (x + width, y + height_value)]
        if mark.kind == "image":
            extent = geometry.get("extent", [])
            if len(extent) == 4:
                return [(float(extent[0]), float(extent[2])), (float(extent[1]), float(extent[3]))]
        return _number_pairs(geometry)

    items = [
        (str(mark.mark_id), mark.axes_id, mark_points(mark))
        for mark in value.marks
    ] + [
        (str(annotation.annotation_id), annotation.axes_id, [annotation.position])
        for annotation in value.annotations
    ]
    for identity, axes_id, points in items:
        axis = axes.get(str(axes_id))
        if axis is None or axis.bbox_inches is None or not points:
            continue
        x0, y0, span_x, span_y = axis.bbox_inches
        x_limits = axis.x_limits or (0.0, 1.0)
        y_limits = axis.y_limits or (0.0, 1.0)
        try:
            pixels = [
                (
                    (x0 + span_x * _scale(x, x_limits, axis.x_scale)) * width,
                    (1.0 - (y0 + span_y * _scale(y, y_limits, axis.y_scale))) * height,
                )
                for x, y in points
            ]
        except (TypeError, ValueError):
            continue
        padding = max(4, int(round(min(width, height) * 0.01)))
        left = max(0, int(math.floor(min(point[0] for point in pixels))) - padding)
        top = max(0, int(math.floor(min(point[1] for point in pixels))) - padding)
        right = min(width, int(math.ceil(max(point[0] for point in pixels))) + padding + 1)
        bottom = min(height, int(math.ceil(max(point[1] for point in pixels))) + padding + 1)
        if right > left and bottom > top:
            regions.append({"semantic_id": identity, "bbox": [left, top, right, bottom]})
    return regions


def capture_raster_reference(
    path: str | Path, *, manifest: Any | None = None
) -> dict[str, Any]:
    from PIL import Image
    with Image.open(path) as image:
        normalized = image.convert("RGBA")
        pixels = normalized.tobytes()
        if len(pixels) > MAX_REFERENCE_BYTES:
            raise ValueError("raster reference exceeds proof size limit")
        compressed = gzip.compress(pixels, mtime=0)
        result = {
            "schema": "reprofig-raster-reference/1",
            "mode": "RGBA",
            "width": normalized.width,
            "height": normalized.height,
            "pixel_sha256": sha256_bytes(pixels),
            "pixels": base64.b64encode(compressed).decode("ascii"),
            "encoding": "gzip+base64",
            "source_format": image.format,
        }
        regions = _semantic_regions(
            manifest, width=normalized.width, height=normalized.height
        )
        if regions:
            result["semantic_regions"] = regions
        return result


def render_pdf_page(path: str | Path, *, page_index: int = 0, scale: float = 2.0):
    """Render one PDF page with PDFium without importing it in base installs."""

    try:
        import pypdfium2 as pdfium
    except ImportError as exc:
        raise RuntimeError(
            "PDF display verification requires: pip install reprofig[pdf-render]"
        ) from exc
    document = pdfium.PdfDocument(str(path))
    try:
        if len(document) != 1:
            raise ValueError("direct ReproFig figure PDFs must contain exactly one page")
        page = document[page_index]
        try:
            return page.render(scale=scale).to_pil().convert("RGBA")
        finally:
            page.close()
    finally:
        document.close()


def capture_pdf_reference(
    path: str | Path, *, manifest: Any | None = None
) -> dict[str, Any]:
    image = render_pdf_page(path)
    pixels = image.tobytes()
    if len(pixels) > MAX_REFERENCE_BYTES:
        raise ValueError("rendered PDF reference exceeds proof size limit")
    result = {
        "schema": "reprofig-raster-reference/1",
        "mode": "RGBA",
        "width": image.width,
        "height": image.height,
        "pixel_sha256": sha256_bytes(pixels),
        "pixels": base64.b64encode(gzip.compress(pixels, mtime=0)).decode("ascii"),
        "encoding": "gzip+base64",
        "source_format": "PDF/page-1@144dpi",
    }
    regions = _semantic_regions(manifest, width=image.width, height=image.height)
    if regions:
        result["semantic_regions"] = regions
    return result


__all__ = ["capture_pdf_reference", "capture_raster_reference", "render_pdf_page"]
