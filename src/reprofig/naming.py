"""Human-readable, deterministic names for exported ReproFig files."""

from __future__ import annotations

import os
import re
import unicodedata
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Literal

from .tables import safe_filename_token

NamingMode = Literal["readable", "legacy"]

_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{number}" for number in range(1, 10)),
    *(f"lpt{number}" for number in range(1, 10)),
}


def normalize_naming_mode(value: str | None) -> NamingMode:
    """Return one supported naming mode or fail with an actionable message."""

    mode = str(value or "readable").strip().lower().replace("_", "-")
    if mode not in {"readable", "legacy"}:
        raise ValueError("naming must be 'readable' or 'legacy'")
    return mode  # type: ignore[return-value]


def readable_filename_token(
    value: Any,
    *,
    fallback: str = "figure",
    max_length: int = 80,
) -> str:
    """Convert a label to a short lowercase ASCII filename stem."""

    if max_length < 8:
        raise ValueError("max_length must be at least 8")
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.replace("&", " and ")
    token = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    if not token:
        token = re.sub(r"[^A-Za-z0-9]+", "-", fallback).strip("-").lower()
    token = token[:max_length].rstrip("-") or "figure"
    if token.casefold() in _WINDOWS_RESERVED:
        token = f"figure-{token}"
    return token


def short_figure_identity(figure_id: Any, *, length: int = 8) -> str:
    """Return the readable collision suffix from a permanent figure identity."""

    value = str(figure_id or "")
    if value.lower().startswith("rf-"):
        value = value[3:]
    token = readable_filename_token(value, fallback="identity", max_length=max(8, length))
    return token.replace("-", "")[:length] or "identity"


def export_stem(
    record: Any | None = None,
    artifact: str | os.PathLike[str] | None = None,
    *,
    export_name: str | None = None,
    naming: str = "readable",
) -> str:
    """Choose a human stem while keeping the permanent identity in metadata."""

    mode = normalize_naming_mode(naming)
    if mode == "legacy":
        identity = getattr(record, "figure_id", None)
        if identity:
            return safe_filename_token(identity)
        if artifact is not None:
            return safe_filename_token(Path(artifact).stem)
        return safe_filename_token(export_name or "figure")

    original_stem = getattr(record, "original_stem", None)
    title = getattr(record, "title", None)
    artifact_stem = Path(artifact).stem if artifact is not None else None
    chosen = export_name or original_stem or artifact_stem or title or "figure"
    return readable_filename_token(chosen)


def export_name_override(
    configured: str | Mapping[str, str] | None,
    path: Path,
    records: Sequence[Any],
    *,
    source_count: int,
) -> str | None:
    """Resolve a single-name shortcut or a deterministic batch-name mapping."""

    if configured is None:
        return None
    if isinstance(configured, str):
        if source_count != 1:
            raise ValueError(
                "a single export_name can only be used with one input; "
                "use a mapping for a batch"
            )
        return configured
    if not isinstance(configured, Mapping):
        raise TypeError("export_name must be a string, mapping, or None")
    keys = [str(path), path.name, path.stem]
    keys.extend(str(getattr(record, "figure_id", "")) for record in records)
    for key in keys:
        if key in configured:
            return str(configured[key])
    return None


def collision_safe_stems(
    stems: Sequence[str],
    figure_ids: Sequence[str],
    *,
    qualifiers: Sequence[str] | None = None,
) -> list[str]:
    """Append a short permanent identity only where readable stems collide."""

    if len(stems) != len(figure_ids):
        raise ValueError("stems and figure_ids must have the same length")
    if qualifiers is not None and len(qualifiers) != len(stems):
        raise ValueError("qualifiers and stems must have the same length")
    identities_by_stem: dict[str, set[str]] = {}
    for stem, figure_id in zip(stems, figure_ids):
        identities_by_stem.setdefault(stem.casefold(), set()).add(
            str(figure_id).casefold()
        )
    result = [
        (
            f"{stem}-{short_figure_identity(figure_id)}"
            if len(identities_by_stem[stem.casefold()]) > 1
            else stem
        )
        for stem, figure_id in zip(stems, figure_ids)
    ]
    folded = [
        f"{value.casefold()}\0{str(qualifier).casefold()}"
        for value, qualifier in zip(result, qualifiers)
    ] if qualifiers is not None else [value.casefold() for value in result]
    if len(folded) != len(set(folded)):
        raise ValueError("readable export names still collide after identity suffixes")
    return result


def role_filename(
    stem: str,
    role: str | None,
    extension: str,
    *,
    naming: str = "readable",
) -> str:
    """Join one export stem, semantic role, and real file extension."""

    mode = normalize_naming_mode(naming)
    suffix = extension if extension.startswith(".") else f".{extension}"
    if not role:
        return f"{stem}{suffix}"
    separator = "-" if mode == "readable" else "."
    return f"{stem}{separator}{role}{suffix}"


def unique_role_filenames(
    stem: str,
    roles: Sequence[str],
    extension: str,
    *,
    naming: str = "readable",
) -> list[str]:
    """Make repeated table-role filenames readable and deterministic."""

    names: list[str] = []
    used: set[str] = set()
    for role in roles:
        base_role = readable_filename_token(role, fallback="data")
        number = 1
        candidate_role = base_role
        candidate = role_filename(stem, candidate_role, extension, naming=naming)
        while candidate.casefold() in used:
            number += 1
            candidate_role = f"{base_role}-{number}"
            candidate = role_filename(stem, candidate_role, extension, naming=naming)
        used.add(candidate.casefold())
        names.append(candidate)
    return names


__all__ = [
    "NamingMode",
    "collision_safe_stems",
    "export_name_override",
    "export_stem",
    "normalize_naming_mode",
    "readable_filename_token",
    "role_filename",
    "short_figure_identity",
    "unique_role_filenames",
]
