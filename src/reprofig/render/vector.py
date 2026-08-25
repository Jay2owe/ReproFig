"""Normalized vector subtrees bound to semantic identities."""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from typing import Any

from ..schema import deterministic_json, sha256_bytes
from .schema import RenderManifest

_FLOAT = re.compile(r"(?<![A-Za-z])[-+]?(?:\d+\.\d+|\d+\.?)(?:[eE][-+]?\d+)?")


def _normalized_number(match: re.Match[str]) -> str:
    return format(float(match.group(0)), ".10g")


def normalized_element(element: ET.Element) -> dict[str, Any]:
    attributes = {
        key: _FLOAT.sub(_normalized_number, value)
        for key, value in element.attrib.items()
        if key not in {"data-reprofig-visual-sha256"} and not key.endswith("}id") and key != "id"
    }
    return {
        "tag": element.tag.rsplit("}", 1)[-1],
        "attributes": dict(sorted(attributes.items())),
        "text": (element.text or "").strip(),
        "children": [normalized_element(child) for child in element if child.tag.rsplit("}", 1)[-1] != "metadata"],
    }


def element_visual_hash(element: ET.Element) -> str:
    return sha256_bytes(deterministic_json(normalized_element(element)).encode("utf-8"))


def bind_svg_semantics(path: str, manifest: RenderManifest) -> RenderManifest:
    raw = open(path, "rb").read()
    if b"<!ENTITY" in raw.upper():
        raise ValueError("unsafe SVG entity declaration")
    root = ET.fromstring(raw)
    ET.register_namespace("", "http://www.w3.org/2000/svg")
    ET.register_namespace("xlink", "http://www.w3.org/1999/xlink")
    by_id = {element.attrib.get("id"): element for element in root.iter() if element.attrib.get("id")}
    expected: dict[str, str] = {}
    annotations = {str(item.annotation_id): item for item in manifest.annotations}
    marks = {str(item.mark_id): item for item in manifest.marks}
    for identity in list(marks) + list(annotations):
        element = by_id.get(identity)
        if element is None:
            continue
        if identity in annotations:
            element.attrib["data-reprofig-text"] = annotations[identity].text
            if annotations[identity].statistic_id:
                element.attrib["data-reprofig-statistic-id"] = str(annotations[identity].statistic_id)
        else:
            element.attrib["data-reprofig-kind"] = marks[identity].kind
        digest = element_visual_hash(element)
        element.attrib["data-reprofig-visual-sha256"] = digest
        expected[identity] = digest
    manifest.environment["vector_elements"] = dict(sorted(expected.items()))
    ET.ElementTree(root).write(path, encoding="utf-8", xml_declaration=True)
    return manifest


__all__ = ["bind_svg_semantics", "element_visual_hash", "normalized_element"]
