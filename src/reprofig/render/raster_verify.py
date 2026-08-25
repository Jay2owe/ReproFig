"""Pixel and region-aware raster comparison against an embedded canonical reference."""

from __future__ import annotations

import base64
import gzip
import math
import os
from pathlib import Path

from ..schema import FigureRecord, sha256_bytes
from ..verification import ProofCheck


def verify_raster_carrier(path: str | os.PathLike[str], record: FigureRecord) -> list[ProofCheck]:
    manifest = record.extensions.get("render_manifest")
    visual = record.extensions.get("visual_reference")
    reference = (
        visual.get("raster_reference")
        if isinstance(visual, dict)
        else manifest.get("environment", {}).get("raster_reference")
        if isinstance(manifest, dict)
        else None
    )
    if not isinstance(reference, dict):
        return [ProofCheck("raster-reference", "display_verified", "unavailable", record.figure_id, "No canonical raster reference is embedded.")]
    suffix = Path(path).suffix.lower()
    if suffix not in {".pdf", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".avif", ".heif", ".heic"}:
        return [ProofCheck("raster-renderer", "display_verified", "unsupported", record.figure_id, "No deterministic page renderer is configured for this carrier.")]
    if suffix == ".pdf":
        try:
            from .canonical import render_pdf_page

            actual_image = render_pdf_page(path)
        except RuntimeError as exc:
            return [ProofCheck(
                "raster-renderer", "display_verified", "unavailable",
                record.figure_id, str(exc),
            )]
        actual = actual_image.tobytes()
        actual_size = (actual_image.width, actual_image.height)
    else:
        from PIL import Image
        with Image.open(path) as image:
            actual_image = image.convert("RGBA")
            actual = actual_image.tobytes()
            actual_size = (actual_image.width, actual_image.height)
    expected = gzip.decompress(base64.b64decode(reference["pixels"], validate=True))
    expected_size = (int(reference["width"]), int(reference["height"]))
    if actual_size != expected_size or len(actual) != len(expected):
        return [ProofCheck("raster-size", "display_verified", "fail", record.figure_id, "Raster canvas dimensions changed.", expected=expected_size, actual=actual_size)]
    squared = sum((left - right) ** 2 for left, right in zip(expected, actual))
    rms = math.sqrt(squared / len(expected)) if expected else 0.0
    maximum = max((abs(left - right) for left, right in zip(expected, actual)), default=0)
    rms_limit = 4.0 if suffix in {".jpg", ".jpeg", ".webp", ".avif", ".heif", ".heic"} else 0.0
    max_limit = 32 if rms_limit else 0
    status = "pass" if rms <= rms_limit and maximum <= max_limit else "fail"
    checks = [ProofCheck(
        "raster-pixels", "display_verified", status, record.figure_id,
        "Raster is visually equivalent within declared thresholds." if status == "pass" else "Raster pixels differ beyond declared thresholds.",
        expected={"pixel_sha256": reference.get("pixel_sha256"), "rms_limit": rms_limit, "max_limit": max_limit},
        actual={"pixel_sha256": sha256_bytes(actual), "rms": rms, "max": maximum},
        tolerance={"rms": rms_limit, "absolute_channel": max_limit},
    )]
    channels = 4
    width, _height = expected_size
    for region in reference.get("semantic_regions", []):
        try:
            left, top, right, bottom = [int(value) for value in region["bbox"]]
            identity = str(region["semantic_id"])
            if not (0 <= left < right <= actual_size[0] and 0 <= top < bottom <= actual_size[1]):
                raise ValueError("region is outside the raster canvas")
            expected_region = bytearray()
            actual_region = bytearray()
            for row in range(top, bottom):
                start = (row * width + left) * channels
                end = (row * width + right) * channels
                expected_region.extend(expected[start:end])
                actual_region.extend(actual[start:end])
            exact = expected_region == actual_region
            checks.append(ProofCheck(
                f"raster-region:{identity}", "display_verified",
                "pass" if exact else "fail", identity,
                "Declared scientific-mark pixels are unchanged."
                if exact else "Pixels in a declared scientific-mark region changed.",
                expected=sha256_bytes(bytes(expected_region)),
                actual=sha256_bytes(bytes(actual_region)),
                tolerance={"absolute_channel": 0},
            ))
        except (KeyError, TypeError, ValueError) as exc:
            checks.append(ProofCheck(
                "raster-region", "display_verified", "fail", record.figure_id,
                f"Invalid semantic raster region: {exc}",
            ))
    return checks


__all__ = ["verify_raster_carrier"]
