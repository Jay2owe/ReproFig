"""Compatibility check used by the plot-that recipe review."""

from __future__ import annotations

import ast
import sys
from pathlib import Path


candidate = Path(sys.argv[1])
tree = ast.parse(candidate.read_text(encoding="utf-8"), filename=str(candidate))
functions = {
    node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
}
required = {"main", "render", "_statistics", "_standalone_welch"}
missing = sorted(required - functions)
if missing:
    raise SystemExit("missing required producer functions: " + ", ".join(missing))
