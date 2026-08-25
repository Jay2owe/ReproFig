"""Bounded candidate workspace layout and path containment."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GuardWorkspace:
    root: Path
    inputs: Path
    scratch: Path
    candidates: Path
    quarantine: Path

    @classmethod
    def create(cls, root: str | Path) -> "GuardWorkspace":
        requested = Path(root)
        if requested.exists() and requested.is_symlink():
            raise ValueError("guard workspace root must not be a symlink")
        base = requested.resolve()
        base.mkdir(parents=True, exist_ok=True)
        values = cls(base, base / "inputs", base / "scratch", base / "candidates", base / "quarantine")
        for path in (values.inputs, values.scratch, values.candidates, values.quarantine):
            path.mkdir(exist_ok=True)
            if path.is_symlink():
                raise ValueError(f"guard workspace component is a symlink: {path}")
        return values

    def require_candidate(self, value: str | Path) -> Path:
        path = Path(value)
        if path.is_symlink():
            raise ValueError("candidate output must not be a symlink")
        resolved = path.resolve(strict=True)
        if self.candidates != resolved and self.candidates not in resolved.parents:
            raise ValueError("candidate is outside the controlled candidate directory")
        if not resolved.is_file():
            raise ValueError("candidate is not a regular file")
        return resolved


__all__ = ["GuardWorkspace"]
