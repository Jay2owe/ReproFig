"""Automatic producer, source, script, and checksum provenance for saves."""

from __future__ import annotations

import importlib.metadata
import inspect
import os
import shlex
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from .schema import FigureRecord
from .sources import file_sha256


def infer_project_root(
    target: str | os.PathLike[str],
    project_root: str | os.PathLike[str] | None = None,
) -> Path:
    """Choose the portable root used for source and reproduction paths."""

    if project_root is not None:
        return Path(project_root).resolve()
    resolved = Path(target).resolve()
    if resolved.parent.name.lower() in {"fig", "figures"}:
        return resolved.parent.parent
    return resolved.parent


def _caller_script() -> Path:
    package_root = Path(__file__).resolve().parent
    for frame in inspect.stack()[2:]:
        candidate = Path(frame.filename).resolve()
        if candidate.is_file() and not candidate.is_relative_to(package_root):
            return candidate
    raise ValueError(
        "automatic reproduction needs a Python script; pass a reproduction "
        "mapping when saving from an interactive session"
    )


def _relative_or_name(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.name


def automatic_reproduction(
    target: str | os.PathLike[str],
    *,
    project_root: str | os.PathLike[str],
) -> dict[str, Any]:
    """Capture the calling script and conventional bundle files automatically."""

    root = Path(project_root).resolve()
    output = Path(target).resolve()
    script = _caller_script()
    producer = _relative_or_name(script, root)
    reproduction: dict[str, Any] = {
        "command": f"python {shlex.quote(producer)}",
        "script": script.read_text(encoding="utf-8"),
        "producer": producer,
        "producer_language": "python",
        "producer_sha256": file_sha256(script),
        "working_directory": ".",
        "output": _relative_or_name(output, root),
    }
    conventional = (
        ("source_index", root / "data" / "sources.csv"),
        ("readme", root / "README.md"),
    )
    for field, path in conventional:
        if path.is_file():
            reproduction[field] = path.relative_to(root).as_posix()
            reproduction[f"{field}_sha256"] = file_sha256(path)
    return reproduction


def infer_producer(
    figure: Any,
    producer: Mapping[str, Any] | str | None,
    *,
    function: str | None = None,
) -> dict[str, Any]:
    """Normalize a short package name or infer it from the live figure."""

    if isinstance(producer, Mapping):
        result = dict(producer)
    else:
        package = (
            str(producer) if producer else type(figure).__module__.split(".", 1)[0]
        )
        result = {"package": package}
    package = result.get("package")
    if package and not (result.get("package_version") or result.get("version")):
        try:
            result["package_version"] = importlib.metadata.version(str(package))
        except importlib.metadata.PackageNotFoundError:
            pass
    if function and "function" not in result:
        result["function"] = function
    return result


def complete_reproduction(record: FigureRecord, *, root: Path) -> None:
    """Add table and source identities after record construction."""

    reproduction = record.reproduction
    if record.data_tables:
        table = record.data_tables[0]
        reproduction.setdefault("exact_table", f"data/der/{table.name}.csv")
        reproduction.setdefault("exact_table_sha256", table.sha256)
    relative_sources = [
        source.relative_path for source in record.sources if source.relative_path
    ]
    if len(relative_sources) == 1:
        reproduction.setdefault("input", relative_sources[0])
    record.reproduction = reproduction


__all__ = [
    "automatic_reproduction",
    "complete_reproduction",
    "infer_producer",
    "infer_project_root",
]
