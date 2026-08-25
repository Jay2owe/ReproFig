"""Refresh carrier-specific visual bindings after safe post-processing."""

from __future__ import annotations

import os
import xml.etree.ElementTree as ET
from pathlib import Path

from ..carriers.registry import identify_format
from ..schema import FigureRecord
from .canonical import capture_raster_reference
from .schema import RenderManifest
from .vector import element_visual_hash


def refresh_visual_reference(
    path: str | os.PathLike[str], record: FigureRecord
) -> FigureRecord:
    """Return a copied record bound to the artifact's current visible content."""

    result = FigureRecord.from_dict(record.to_dict())
    manifest_value = result.extensions.get("render_manifest")
    if not isinstance(manifest_value, dict):
        raise ValueError("visual-reference refresh requires a semantic render manifest")
    manifest = RenderManifest.from_dict(manifest_value)
    carrier_format = identify_format(path)
    if carrier_format == "svg":
        target = Path(path)
        raw = target.read_bytes()
        if b"<!ENTITY" in raw.upper():
            raise ValueError("unsafe SVG entity declaration")
        root = ET.fromstring(raw)
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
        by_id = {
            element.attrib.get("id"): element
            for element in root.iter()
            if element.attrib.get("id")
        }
        expected: dict[str, str] = {}
        for identity in [
            *(str(mark.mark_id) for mark in manifest.marks),
            *(str(annotation.annotation_id) for annotation in manifest.annotations),
        ]:
            element = by_id.get(identity)
            if element is None:
                continue
            digest = element_visual_hash(element)
            element.attrib["data-reprofig-visual-sha256"] = digest
            expected[identity] = digest
        ET.ElementTree(root).write(target, encoding="utf-8", xml_declaration=True)
        result.extensions["visual_reference"] = {
            "schema": "reprofig-visual-reference/1",
            "format": "svg",
            "vector_elements": dict(sorted(expected.items())),
        }
    elif carrier_format in {
        "png", "jpeg", "tiff", "webp", "avif", "heif"
    }:
        result.extensions["visual_reference"] = {
            "schema": "reprofig-visual-reference/1",
            "format": carrier_format,
            "raster_reference": capture_raster_reference(path, manifest=manifest),
        }
    elif carrier_format == "pdf":
        from .canonical import capture_pdf_reference

        result.extensions["visual_reference"] = {
            "schema": "reprofig-visual-reference/1",
            "format": "pdf",
            "raster_reference": capture_pdf_reference(path, manifest=manifest),
        }
    else:
        result.extensions.pop("visual_reference", None)
    return result


__all__ = ["refresh_visual_reference"]
