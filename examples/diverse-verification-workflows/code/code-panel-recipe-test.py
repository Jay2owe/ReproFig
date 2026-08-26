"""Compatibility check for a candidate plot-that code-panel recipe."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def main() -> int:
    candidate = Path(sys.argv[1]).resolve()
    spec = importlib.util.spec_from_file_location("candidate_code_figure", candidate)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot import {candidate}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    panel = module.Panel(
        label="EXACT PRODUCER",
        code='value = 3\nprint(value)  # exact output',
        accent="blue",
    )
    svg = module.render([panel])
    rows = module.line_table([panel])
    assert svg.startswith("<svg")
    assert "EXACT PRODUCER" in svg
    assert [row["text"] for row in rows] == [
        "value = 3",
        "print(value)  # exact output",
    ]
    assert set(rows[0]) == {
        "panel",
        "panel_label",
        "accent",
        "line",
        "x",
        "y",
        "characters",
        "n_spans",
        "classes",
        "text",
    }
    print("code-panel recipe contract passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
