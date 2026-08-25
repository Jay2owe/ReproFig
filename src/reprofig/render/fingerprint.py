"""Normalized public visual fingerprints for stripped-carrier recovery."""

from __future__ import annotations

import os
import re
from pathlib import Path

from ..schema import sha256_bytes


def visual_fingerprint(path: str | os.PathLike[str]) -> dict[str, str]:
    source = Path(path)
    if source.suffix.lower() == ".svg":
        text = source.read_text(encoding="utf-8", errors="replace")
        text = re.sub(r"<metadata\b.*?</metadata>", "", text, flags=re.DOTALL | re.IGNORECASE)
        text = re.sub(r"\s+", " ", text).strip()
        text = re.sub(r"[-+]?(?:\d+\.\d+|\d+\.?)(?:[eE][-+]?\d+)?", lambda match: format(float(match.group(0)), ".6g"), text)
        return {"algorithm": "normalized-svg-sha256/v1", "value": sha256_bytes(text.encode("utf-8"))}
    try:
        from PIL import Image
        with Image.open(source) as image:
            sample = image.convert("L").resize((32, 32))
            flattened = getattr(sample, "get_flattened_data", sample.getdata)
            values = list(flattened())
    except Exception as exc:
        raise ValueError(f"no normalized visual fingerprint route for {source.suffix}") from exc
    average = sum(values) / len(values)
    bits = "".join("1" if value >= average else "0" for value in values)
    encoded = f"{int(bits, 2):0256x}"
    return {"algorithm": "average-hash-32/v1", "value": encoded}


__all__ = ["visual_fingerprint"]
