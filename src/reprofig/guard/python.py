"""Scoped Python save interception; importing this module patches nothing."""

from __future__ import annotations

import contextlib
import os
import runpy
import subprocess
import sys
from pathlib import Path
from typing import Any, Iterator

from ..artifacts import save_figure
from ..verification import verify_artifact
from .policy import OutputPolicy


@contextlib.contextmanager
def guarded_python(policy: OutputPolicy, *, audit_log: list[dict[str, Any]] | None = None) -> Iterator[None]:
    """Intercept common Matplotlib routes only inside this explicit context."""

    import matplotlib.figure
    import matplotlib.pyplot as pyplot
    original_figure_savefig = matplotlib.figure.Figure.savefig
    original_pyplot_savefig = pyplot.savefig
    log = audit_log if audit_log is not None else []

    def guarded_savefig(figure: Any, filename: Any, *args: Any, **kwargs: Any) -> None:
        if getattr(figure, "_reprofig_guard_rendering", False):
            return original_figure_savefig(figure, filename, *args, **kwargs)
        target = Path(filename)
        format_name = (kwargs.pop("format", None) or target.suffix.lstrip(".")).lower()
        if format_name == "jpg":
            format_name = "jpeg"
        if format_name not in policy.permitted_formats:
            raise PermissionError(f"output format {format_name!r} is forbidden by ReproFig policy")
        if policy.destination:
            destination = Path(policy.destination).resolve()
            resolved = target.resolve()
            if destination != resolved and destination not in resolved.parents:
                raise PermissionError(f"output {target} is outside the controlled destination")
        record = kwargs.pop("reprofig_record", None)
        savefig_kwargs = dict(kwargs)
        setattr(figure, "_reprofig_guard_rendering", True)
        try:
            final_record = save_figure(
                figure, target, record=record, figure_profile=policy.profile,
                proof=True,
                proof_policy=policy.to_artifact_policy(),
                savefig_kwargs=savefig_kwargs,
            )
        finally:
            delattr(figure, "_reprofig_guard_rendering")
        report = verify_artifact(target, required=policy.required_meanings, trust_store=policy.trust_store)
        log.append({"path": str(target), "format": format_name, "valid": report.valid, "meanings": report.meanings})
        if policy.strict and not report.valid:
            try:
                target.unlink()
            except OSError:
                pass
            raise RuntimeError("saved plot did not satisfy required ReproFig verification meanings")

    def guarded_pyplot_savefig(filename: Any, *args: Any, **kwargs: Any) -> None:
        return pyplot.gcf().savefig(filename, *args, **kwargs)

    matplotlib.figure.Figure.savefig = guarded_savefig
    pyplot.savefig = guarded_pyplot_savefig
    try:
        yield
    finally:
        matplotlib.figure.Figure.savefig = original_figure_savefig
        pyplot.savefig = original_pyplot_savefig


def launch_guarded_python(
    script: str | os.PathLike[str],
    *,
    policy_path: str | os.PathLike[str],
    arguments: list[str] | None = None,
) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, "-m", "reprofig.guard.python", "--policy", str(policy_path), str(script), *(arguments or [])]
    return subprocess.run(command, text=True, check=False)


def _main(argv: list[str]) -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--policy", required=True)
    parser.add_argument("script")
    parser.add_argument("arguments", nargs="*")
    args = parser.parse_args(argv)
    policy = OutputPolicy.from_json(args.policy)
    old_argv = sys.argv
    sys.argv = [args.script, *args.arguments]
    try:
        with guarded_python(policy):
            runpy.run_path(args.script, run_name="__main__")
    finally:
        sys.argv = old_argv
    return 0


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))


__all__ = ["guarded_python", "launch_guarded_python"]
