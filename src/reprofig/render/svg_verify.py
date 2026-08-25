"""Safe SVG semantic identity, geometry and annotation verification."""

from __future__ import annotations

import html
import os
import xml.etree.ElementTree as ET
from pathlib import Path

from ..schema import FigureRecord
from ..verification import ProofCheck
from .schema import RenderManifest
from .vector import element_visual_hash


def verify_svg(path: str | os.PathLike[str], record: FigureRecord) -> list[ProofCheck]:
    value = record.extensions.get("render_manifest")
    if not isinstance(value, dict):
        return [ProofCheck("svg-render-manifest", "display_verified", "unavailable", record.figure_id, "No semantic render manifest is embedded.")]
    manifest = RenderManifest.from_dict(value)
    raw = Path(path).read_bytes()
    if b"<!ENTITY" in raw.upper():
        return [ProofCheck("svg-safe-xml", "display_verified", "fail", record.figure_id, "SVG contains an entity declaration.")]
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return [ProofCheck("svg-xml", "display_verified", "fail", record.figure_id, str(exc))]
    by_id = {element.attrib.get("id"): element for element in root.iter() if element.attrib.get("id")}
    visual = record.extensions.get("visual_reference")
    expected_hashes = (
        visual.get("vector_elements")
        if isinstance(visual, dict)
        else manifest.environment.get("vector_elements")
    ) or {}
    checks: list[ProofCheck] = []
    for mark in manifest.marks:
        identity = str(mark.mark_id)
        element = by_id.get(identity)
        if element is None:
            checks.append(ProofCheck(f"svg:{identity}", "display_verified", "fail", identity, "Bound visual mark is missing."))
            continue
        expected = expected_hashes.get(identity)
        actual = element_visual_hash(element)
        status = "pass" if expected and actual == expected else ("unavailable" if not expected else "fail")
        checks.append(ProofCheck(f"svg:{identity}", "display_verified", status, identity, "Vector geometry matches the signed semantic capture." if status == "pass" else "Vector geometry hash is absent or changed.", expected=expected, actual=actual))
    raw_text = raw.decode("utf-8", errors="replace")
    for annotation in manifest.annotations:
        identity = str(annotation.annotation_id)
        element = by_id.get(identity)
        expected = expected_hashes.get(identity)
        actual = element_visual_hash(element) if element is not None else None
        text_present = (
            element is not None
            and (
                element.attrib.get("data-reprofig-text") == annotation.text
                or annotation.text in "".join(element.itertext())
            )
        )
        if not text_present:
            text_present = annotation.text in raw_text or html.escape(annotation.text) in raw_text
        status = "pass" if element is not None and text_present and expected and actual == expected else "fail"
        checks.append(ProofCheck(f"svg:{identity}", "display_verified", status, identity, "Annotation text and vector geometry match." if status == "pass" else "Annotation is missing, relabelled or moved.", expected={"text": annotation.text, "hash": expected}, actual={"text_present": text_present, "hash": actual}))
    if manifest.unsupported:
        checks.append(ProofCheck("svg-unsupported-artists", "display_verified", "unsupported", record.figure_id, f"{len(manifest.unsupported)} artist types were not semantically captured."))
    if not checks:
        checks.append(ProofCheck("svg-semantic-elements", "display_verified", "unavailable", record.figure_id, "Render manifest has no proof-relevant marks or annotations."))
    return checks


__all__ = ["verify_svg"]
