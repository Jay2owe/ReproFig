"""Explicit, bounded producer reruns with saved and compared figure outputs."""

from __future__ import annotations

import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from .artifacts import extract_record, validate_artifact
from .evidence import graph_from_record
from .naming import export_stem, normalize_naming_mode, role_filename
from .schema import deterministic_json, sha256_bytes
from .validation import scrub_private_strings
from .verification import ProofCheck

REPORT_SCHEMA = "reprofig/figure-reproduction-report/1"


def _sha256(path: Path) -> str:
    digest = __import__("hashlib").sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _safe_relative(value: str, *, label: str) -> Path:
    text = str(value).replace("\\", "/")
    pure = PurePosixPath(text)
    if not text or pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise ValueError(f"{label} must be a safe bundle-relative path")
    if pure.parts and ":" in pure.parts[0]:
        raise ValueError(f"{label} must be a safe bundle-relative path")
    return Path(*pure.parts)


def _bounded_text(path: Path, limit: int) -> str:
    data = path.read_bytes()
    if len(data) > limit:
        data = data[:limit] + b"\n[log truncated by ReproFig]\n"
    return str(scrub_private_strings(data.decode("utf-8", errors="replace")))


def _copy_tree_bounded(source: Path, destination: Path, *, byte_limit: int) -> None:
    total = 0
    if not source.exists():
        return
    for path in sorted(source.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"reproduction input tree contains a symlink: {path.name}")
        if not path.is_file():
            continue
        total += path.stat().st_size
        if total > byte_limit:
            raise ValueError("reproduction inputs exceed the configured byte limit")
        relative = path.relative_to(source)
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, target)


def _atomic_copy(source: Path, target: Path, *, overwrite: bool) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    descriptor, candidate_name = tempfile.mkstemp(
        dir=str(target.parent), prefix=f".{target.name}.", suffix=".candidate"
    )
    os.close(descriptor)
    candidate = Path(candidate_name)
    try:
        shutil.copy2(source, candidate)
        for attempt in range(12):
            try:
                os.replace(candidate, target)
                return
            except PermissionError:
                if attempt == 11:
                    raise
                time.sleep(0.25)
    finally:
        try:
            candidate.unlink()
        except OSError:
            pass


@dataclass(frozen=True)
class ReproductionPolicy:
    """Limits for an explicitly authorized trusted producer run."""

    timeout_seconds: float = 120.0
    max_input_bytes: int = 250_000_000
    max_output_bytes: int = 100_000_000
    max_log_bytes: int = 1_000_000
    allowed_executables: tuple[str, ...] = ("python", "python3", "py")
    require_data_match: bool = True
    require_statistics_match: bool = True
    require_display_match: bool = True

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be positive")
        for name in ("max_input_bytes", "max_output_bytes", "max_log_bytes"):
            if int(getattr(self, name)) <= 0:
                raise ValueError(f"{name} must be positive")
        if not self.allowed_executables:
            raise ValueError("allowed_executables must not be empty")


@dataclass
class FigureReproductionReport:
    """Portable evidence from one explicit figure-production rerun."""

    source_figure_id: str
    master_name: str
    master_sha256: str
    master_evidence_root: str
    reproduced_path: str | None = None
    reproduced_sha256: str | None = None
    command: list[str] = field(default_factory=list)
    return_code: int | None = None
    duration_seconds: float = 0.0
    stdout: str = ""
    stderr: str = ""
    execution_status: str = "unavailable"
    comparisons: dict[str, str] = field(default_factory=dict)
    messages: dict[str, str] = field(default_factory=dict)
    runtime: dict[str, Any] = field(default_factory=dict)
    schema: str = REPORT_SCHEMA

    @property
    def valid(self) -> bool:
        return (
            self.execution_status == "pass"
            and self.reproduced_sha256 is not None
            and bool(self.comparisons)
            and all(value == "pass" for value in self.comparisons.values())
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "source_figure_id": self.source_figure_id,
            "master_name": self.master_name,
            "master_sha256": self.master_sha256,
            "master_evidence_root": self.master_evidence_root,
            "reproduced_path": self.reproduced_path,
            "reproduced_sha256": self.reproduced_sha256,
            "command": list(self.command),
            "return_code": self.return_code,
            "duration_seconds": self.duration_seconds,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "execution_status": self.execution_status,
            "comparisons": dict(sorted(self.comparisons.items())),
            "messages": dict(sorted(self.messages.items())),
            "runtime": dict(sorted(self.runtime.items())),
            "valid": self.valid,
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return deterministic_json(self.to_dict(), indent=indent)

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "FigureReproductionReport":
        if value.get("schema") != REPORT_SCHEMA:
            raise ValueError("unsupported figure-reproduction report schema")
        return cls(
            schema=str(value["schema"]),
            source_figure_id=str(value.get("source_figure_id", "")),
            master_name=str(value.get("master_name", "")),
            master_sha256=str(value.get("master_sha256", "")),
            master_evidence_root=str(value.get("master_evidence_root", "")),
            reproduced_path=value.get("reproduced_path"),
            reproduced_sha256=value.get("reproduced_sha256"),
            command=[str(item) for item in value.get("command", [])],
            return_code=value.get("return_code"),
            duration_seconds=float(value.get("duration_seconds", 0.0)),
            stdout=str(value.get("stdout", "")),
            stderr=str(value.get("stderr", "")),
            execution_status=str(value.get("execution_status", "unavailable")),
            comparisons={str(key): str(item) for key, item in dict(value.get("comparisons") or {}).items()},
            messages={str(key): str(item) for key, item in dict(value.get("messages") or {}).items()},
            runtime=dict(value.get("runtime") or {}),
        )

    @classmethod
    def from_json(cls, path: str | os.PathLike[str]) -> "FigureReproductionReport":
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise ValueError("figure-reproduction report must contain a JSON object")
        return cls.from_dict(value)


def _semantic_manifest(record) -> dict[str, Any] | None:
    value = record.extensions.get("render_manifest")
    if not isinstance(value, Mapping):
        return None
    return {
        key: value.get(key)
        for key in ("schema", "axes", "marks", "annotations", "unsupported")
    }


def _compare_records(master, reproduced) -> tuple[dict[str, str], dict[str, str]]:
    master_tables = sorted(
        (table.name, table.purpose, table.sha256) for table in master.data_tables
    )
    reproduced_tables = sorted(
        (table.name, table.purpose, table.sha256) for table in reproduced.data_tables
    )
    data_status = "pass" if master_tables == reproduced_tables else "fail"
    statistics_status = (
        "pass"
        if deterministic_json(master.statistics) == deterministic_json(reproduced.statistics)
        else "fail"
    )
    master_manifest = _semantic_manifest(master)
    reproduced_manifest = _semantic_manifest(reproduced)
    if master_manifest is None or reproduced_manifest is None:
        display_status = "unavailable"
    else:
        master_visual = master.extensions.get("visual_reference")
        reproduced_visual = reproduced.extensions.get("visual_reference")
        display_status = (
            "pass"
            if deterministic_json(master_manifest) == deterministic_json(reproduced_manifest)
            and deterministic_json(master_visual) == deterministic_json(reproduced_visual)
            else "fail"
        )
    statuses = {
        "data_tables": data_status,
        "statistics": statistics_status,
        "display": display_status,
    }
    messages = {
        "data_tables": "Embedded table identities match." if data_status == "pass" else "Embedded table identities differ.",
        "statistics": "Normalized statistical records match." if statistics_status == "pass" else "Normalized statistical records differ.",
        "display": (
            "Semantic marks and carrier-specific visual bindings match."
            if display_status == "pass"
            else "A semantic render manifest is unavailable."
            if display_status == "unavailable"
            else "Semantic marks or visual bindings differ."
        ),
    }
    return statuses, messages


def _write_report(report: FigureReproductionReport, path: Path, *, overwrite: bool) -> None:
    if path.exists() and not overwrite:
        raise FileExistsError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    data = (report.to_json(indent=2) + "\n").encode("utf-8")
    descriptor, candidate_name = tempfile.mkstemp(
        dir=str(path.parent), prefix=f".{path.name}.", suffix=".candidate"
    )
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(data)
        os.replace(candidate_name, path)
    finally:
        try:
            Path(candidate_name).unlink()
        except OSError:
            pass


def reproduce_figure(
    artifact: str | os.PathLike[str],
    *,
    output_dir: str | os.PathLike[str],
    bundle_root: str | os.PathLike[str] | None = None,
    report_path: str | os.PathLike[str] | None = None,
    policy: ReproductionPolicy | None = None,
    execute_trusted_producer: bool = False,
    overwrite: bool = False,
    export_name: str | None = None,
    naming: str = "readable",
) -> FigureReproductionReport:
    """Explicitly rerun trusted producer code and preserve a compared carrier."""

    if not execute_trusted_producer:
        raise PermissionError(
            "figure reproduction executes embedded code; set "
            "execute_trusted_producer=True only after trusting the producer"
        )
    chosen = policy or ReproductionPolicy()
    mode = normalize_naming_mode(naming)
    master_path = Path(artifact).resolve()
    master = extract_record(master_path)
    reproduction = dict(master.reproduction)
    script = reproduction.get("script")
    command_value = reproduction.get("command")
    if not isinstance(script, str) or not script.strip():
        raise ValueError("the figure has no embedded producer script")
    if not isinstance(command_value, str) or not command_value.strip():
        raise ValueError("the figure has no declared reproduction command")
    declared_command = shlex.split(command_value, posix=True)
    if not declared_command:
        raise ValueError("the declared reproduction command is empty")
    executable = Path(declared_command[0]).name.lower()
    if executable not in {value.lower() for value in chosen.allowed_executables}:
        raise PermissionError(
            f"reproduction executable {declared_command[0]!r} is not allowlisted"
        )
    run_command = [sys.executable, *declared_command[1:]]

    root = Path(bundle_root).resolve() if bundle_root is not None else master_path.parent.parent
    if not root.is_dir():
        raise FileNotFoundError(f"bundle root does not exist: {root}")
    producer_relative = _safe_relative(
        str(reproduction.get("producer") or "code/plot.py"), label="producer"
    )
    expected_relative = _safe_relative(
        str(reproduction.get("output") or f"fig/{master_path.name}"),
        label="reproduction output",
    )
    destination_dir = Path(output_dir).resolve()
    stem = (
        export_stem(
            master,
            master_path,
            export_name=export_name,
            naming=mode,
        )
        if mode == "readable"
        else master_path.stem
    )
    destination = destination_dir / role_filename(
        stem,
        "reproduced",
        master_path.suffix,
        naming=mode,
    )
    report_destination = (
        Path(report_path).resolve()
        if report_path is not None
        else destination_dir.parent
        / role_filename(stem, "reproduction-report", "json", naming=mode)
    )
    report = FigureReproductionReport(
        source_figure_id=master.figure_id,
        master_name=master_path.name,
        master_sha256=_sha256(master_path),
        master_evidence_root=graph_from_record(master).root_sha256,
        command=list(declared_command),
        runtime={
            "python": sys.version.split()[0],
            "executable": Path(sys.executable).name,
            "isolated_workspace": True,
            "network_isolation": "not_enforced",
        },
    )

    started = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="reprofig-reproduce-") as temporary_name:
        temporary = Path(temporary_name)
        workspace = temporary / (root.name or "bundle")
        workspace.mkdir(parents=True)
        _copy_tree_bounded(
            root / "data", workspace / "data", byte_limit=chosen.max_input_bytes
        )
        readme = root / "README.md"
        if readme.is_file():
            shutil.copy2(readme, workspace / "README.md")
        producer_path = workspace / producer_relative
        producer_path.parent.mkdir(parents=True, exist_ok=True)
        producer_path.write_text(script, encoding="utf-8")
        for table in master.data_tables:
            if table.contents is None:
                continue
            table_path = workspace / "data" / "der" / f"{table.name}.csv"
            table_path.parent.mkdir(parents=True, exist_ok=True)
            if not table_path.exists():
                table_path.write_text(table.contents, encoding="utf-8", newline="")
        for source in master.sources:
            if not source.relative_path:
                continue
            relative = _safe_relative(source.relative_path, label="source input")
            source_path = workspace / relative
            if not source_path.is_file():
                report.execution_status = "unavailable"
                report.messages["execution"] = f"Required source input is missing: {relative.as_posix()}"
                report.duration_seconds = round(time.monotonic() - started, 6)
                _write_report(report, report_destination, overwrite=overwrite)
                return report
            if source.sha256 and _sha256(source_path) != source.sha256:
                report.execution_status = "fail"
                report.messages["execution"] = f"Required source hash differs: {relative.as_posix()}"
                report.duration_seconds = round(time.monotonic() - started, 6)
                _write_report(report, report_destination, overwrite=overwrite)
                return report

        stdout_path = temporary / "stdout.log"
        stderr_path = temporary / "stderr.log"
        environment = os.environ.copy()
        package_root = str(Path(__file__).resolve().parents[1])
        environment["PYTHONPATH"] = os.pathsep.join(
            value for value in (package_root, environment.get("PYTHONPATH", "")) if value
        )
        environment.update(
            {
                "MPLBACKEND": "Agg",
                "PYTHONDONTWRITEBYTECODE": "1",
                "PYTHONHASHSEED": "0",
            }
        )
        working_relative = reproduction.get("working_directory", ".")
        if working_relative in (None, "", "."):
            working_directory = workspace
        else:
            working_directory = workspace / _safe_relative(
                str(working_relative), label="working directory"
            )
        working_directory.mkdir(parents=True, exist_ok=True)
        try:
            with stdout_path.open("wb") as stdout_handle, stderr_path.open("wb") as stderr_handle:
                completed = subprocess.run(
                    run_command,
                    cwd=working_directory,
                    env=environment,
                    shell=False,
                    stdout=stdout_handle,
                    stderr=stderr_handle,
                    timeout=chosen.timeout_seconds,
                    check=False,
                )
            report.return_code = int(completed.returncode)
        except subprocess.TimeoutExpired:
            report.execution_status = "fail"
            report.messages["execution"] = "Producer exceeded the configured timeout."
            report.return_code = None
        report.stdout = _bounded_text(stdout_path, chosen.max_log_bytes)
        report.stderr = _bounded_text(stderr_path, chosen.max_log_bytes)
        candidate = workspace / expected_relative
        if report.execution_status != "fail" and report.return_code != 0:
            report.execution_status = "fail"
            report.messages["execution"] = f"Producer exited with code {report.return_code}."
        elif report.execution_status != "fail" and not candidate.is_file():
            report.execution_status = "fail"
            report.messages["execution"] = f"Producer did not create {expected_relative.as_posix()}."
        elif report.execution_status != "fail" and candidate.stat().st_size > chosen.max_output_bytes:
            report.execution_status = "fail"
            report.messages["execution"] = "Produced figure exceeds the configured byte limit."
        elif report.execution_status != "fail":
            integrity = validate_artifact(candidate)
            if not integrity.valid:
                report.execution_status = "fail"
                report.messages["execution"] = "Produced figure failed carrier validation."
            else:
                report.execution_status = "pass"
                report.messages["execution"] = "Trusted producer completed and wrote a valid carrier."
                reproduced = extract_record(candidate)
                statuses, messages = _compare_records(master, reproduced)
                if not chosen.require_data_match and statuses["data_tables"] != "pass":
                    statuses.pop("data_tables")
                    messages.pop("data_tables")
                if not chosen.require_statistics_match and statuses["statistics"] != "pass":
                    statuses.pop("statistics")
                    messages.pop("statistics")
                if not chosen.require_display_match and statuses["display"] != "pass":
                    statuses.pop("display")
                    messages.pop("display")
                report.comparisons = statuses
                report.messages.update(messages)
                _atomic_copy(candidate, destination, overwrite=overwrite)
                report.reproduced_sha256 = _sha256(destination)
                report.reproduced_path = os.path.relpath(
                    destination, report_destination.parent
                ).replace("\\", "/")
        report.duration_seconds = round(time.monotonic() - started, 6)
    _write_report(report, report_destination, overwrite=overwrite)
    return report


def verify_figure_reproduction(
    artifact: str | os.PathLike[str],
    report_path: str | os.PathLike[str],
) -> ProofCheck:
    """Validate a saved reproduction report and its reproduced carrier."""

    master_path = Path(artifact).resolve()
    report_file = Path(report_path).resolve()
    try:
        report = FigureReproductionReport.from_json(report_file)
        master = extract_record(master_path)
        if report.master_name != master_path.name:
            raise ValueError("reproduction report names a different master carrier")
        if report.source_figure_id != master.figure_id:
            raise ValueError("reproduction report names a different figure identity")
        if report.master_evidence_root != graph_from_record(master).root_sha256:
            raise ValueError("reproduction report names a different master evidence root")
        if not report.reproduced_path:
            raise ValueError("reproduction report has no saved carrier path")
        relative = _safe_relative(report.reproduced_path, label="reproduced path")
        reproduced_path = report_file.parent / relative
        if not reproduced_path.is_file():
            raise FileNotFoundError("saved reproduced carrier is missing")
        if report.reproduced_sha256 != _sha256(reproduced_path):
            raise ValueError("saved reproduced carrier hash differs from the report")
        if not report.valid:
            raise ValueError("reproduction execution or comparison did not pass")
        integrity = validate_artifact(reproduced_path)
        if not integrity.valid:
            raise ValueError("saved reproduced carrier failed carrier validation")
        reproduced = extract_record(reproduced_path)
        comparisons, _ = _compare_records(master, reproduced)
        required_comparisons = {"data_tables", "statistics", "display"}
        if set(report.comparisons) != required_comparisons:
            raise ValueError(
                "reproduction report does not cover data, statistics and display"
            )
        if comparisons != report.comparisons:
            raise ValueError(
                "saved reproduced carrier does not reproduce the reported comparisons"
            )
        if any(status != "pass" for status in comparisons.values()):
            raise ValueError("saved reproduced carrier does not match the master")
    except FileNotFoundError as exc:
        return ProofCheck(
            "figure-reproduction", "figure_reproduced", "unavailable", message=str(exc)
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError) as exc:
        return ProofCheck(
            "figure-reproduction", "figure_reproduced", "fail", message=str(exc)
        )
    return ProofCheck(
        "figure-reproduction",
        "figure_reproduced",
        "pass",
        master.figure_id,
        "A separately saved reproduced carrier matches the master data, statistics and display.",
        expected=report.master_evidence_root,
        actual={
            "reproduced_sha256": report.reproduced_sha256,
            "comparisons": comparisons,
        },
    )


__all__ = [
    "REPORT_SCHEMA",
    "FigureReproductionReport",
    "ReproductionPolicy",
    "reproduce_figure",
    "verify_figure_reproduction",
]
