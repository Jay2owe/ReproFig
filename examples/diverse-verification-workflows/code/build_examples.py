"""Build three presentation-ready, single-figure verification workflows."""

from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter, SvgFormatter
from pygments.lexers import PythonLexer

from reprofig import (
    TransformationSpec,
    attach_evidence_graph,
    embed_file,
    extract_artifact,
    extract_record,
    reproduce_figure,
    table_from_data,
    verify_proof,
)

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "input"
PRODUCERS = ROOT / "producers"
SOURCE_ID = "source:raw-input"
REQUIRED = (
    "display_verified",
    "figure_reproduced",
    "internally_consistent",
    "source_linked",
    "statistics_independently_verified",
)


@dataclass(frozen=True)
class Example:
    folder: str
    title: str
    claim: str
    library: str
    grammar: str
    test: str
    input_name: str
    producer_name: str
    figure_name: str
    figure_id: str
    columns: tuple[str, ...]

    @property
    def export_stem(self) -> str:
        return Path(self.figure_name).stem


EXAMPLES = (
    Example(
        folder="matplotlib-paired-change",
        title="Paired change",
        claim="Paired responses are higher after the intervention in this synthetic dataset.",
        library="Matplotlib",
        grammar="paired slope plot",
        test="Wilcoxon signed-rank test",
        input_name="paired-change.csv",
        producer_name="matplotlib_paired.py",
        figure_name="paired-change.svg",
        figure_id="rf-8e6d99733d1044799d5d6f925b427db1",
        columns=("participant", "before", "after"),
    ),
    Example(
        folder="seaborn-regression",
        title="Continuous association",
        claim="Response increases with exposure in this synthetic dataset.",
        library="Seaborn",
        grammar="scatter regression plot",
        test="ordinary least-squares regression",
        input_name="regression.csv",
        producer_name="seaborn_regression.py",
        figure_name="exposure-response.svg",
        figure_id="rf-d13001a42c854d189991e887131b67a4",
        columns=("sample", "exposure", "response"),
    ),
    Example(
        folder="plotly-multigroup",
        title="Multiple-group comparison",
        claim="Mean response differs across the three conditions in this synthetic dataset.",
        library="Plotly",
        grammar="box and raw-points plot",
        test="one-way analysis of variance",
        input_name="multigroup.csv",
        producer_name="plotly_multigroup.py",
        figure_name="condition-response.png",
        figure_id="rf-594c5332dd8b44f28c8afe3eb1d5fb9f",
        columns=("sample", "condition", "response"),
    ),
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _remove_generated(path: Path) -> None:
    if not path.exists():
        return
    for attempt in range(20):
        try:
            shutil.rmtree(path)
            return
        except PermissionError:
            if attempt == 19:
                raise
            time.sleep(0.5)


def _write_sources(
    bundle: Path,
    copied: Path,
    original: Path,
) -> None:
    stat = copied.stat()
    source_index = bundle / "data" / "sources.csv"
    with source_index.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["original_path", "copied_path", "file_name", "modification_time", "byte_size", "sha256", "public_uri"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(
            {
                "original_path": f"input/{original.name}",
                "copied_path": f"data/src/{copied.name}",
                "file_name": copied.name,
                "modification_time": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(timespec="seconds"),
                "byte_size": stat.st_size,
                "sha256": _sha256(copied),
                "public_uri": "",
            }
        )
    (bundle / "data" / "sources.md").write_text(
        "# Source index\n\n"
        f"`data/src/{copied.name}` is an exact copy of the synthetic raw input "
        f"at `input/{original.name}`. Its byte size and SHA-256 digest are in "
        f"`{source_index.name}`.\n",
        encoding="utf-8",
    )


def _readme(example: Example) -> str:
    return (
        f"# {example.title}\n\n"
        f"Claim: {example.claim}\n\n"
        f"{example.library} draws one {example.grammar}. A {example.test} is "
        "calculated by the producer and independently recalculated by ReproFig.\n\n"
        "The workflow copies and hashes the raw comma-separated-value input, "
        "embeds the exact plotted table and statistical specification, verifies "
        "the visible carrier, reruns the trusted producer into a separate figure, "
        "and unpacks the recoverable evidence.\n\n"
        "Open `presentation/index.html` for the presentation view. The data are "
        "synthetic and are not evidence for a real scientific conclusion.\n"
    )


def _render_code(source: Path, presentation: Path, *, export_stem: str) -> None:
    code = source.read_text(encoding="utf-8")
    presentation.mkdir(parents=True, exist_ok=True)
    rendered = highlight(
        code,
        PythonLexer(),
        HtmlFormatter(full=True, linenos="table", style="friendly", title="Exact producer code"),
    )
    (presentation / f"{export_stem}-code.html").write_text(
        rendered,
        encoding="utf-8",
    )
    vector = highlight(
        code,
        PythonLexer(),
        SvgFormatter(font_size=12, linenos=True, style="friendly"),
    )
    (presentation / f"{export_stem}-code.svg").write_text(
        vector,
        encoding="utf-8",
    )


def _prepare(example: Example) -> Path:
    bundle = ROOT / example.folder
    _remove_generated(bundle)
    for relative in ("code", "data/der", "data/src", "fig", "presentation", "unpacked", "verification/reproduced"):
        (bundle / relative).mkdir(parents=True, exist_ok=True)
    original = INPUT / example.input_name
    copied = bundle / "data" / "src" / example.input_name
    producer = bundle / "code" / "plot.py"
    shutil.copy2(original, copied)
    shutil.copy2(PRODUCERS / example.producer_name, producer)
    _write_sources(bundle, copied, original)
    (bundle / "README.md").write_text(_readme(example), encoding="utf-8")
    _write_json(
        bundle / "verification" / "policy.json",
        {
            "required_meanings": [
                "display_verified",
                "internally_consistent",
                "statistics_independently_verified",
            ]
        },
    )
    _render_code(
        producer,
        bundle / "presentation",
        export_stem=example.export_stem,
    )
    return bundle


def _run_producer(bundle: Path) -> None:
    environment = os.environ.copy()
    environment.update({"MPLBACKEND": "Agg", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"})
    for attempt in range(12):
        result = subprocess.run(
            [sys.executable, "code/plot.py"],
            cwd=bundle,
            env=environment,
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            return
        output = f"{result.stdout}\n{result.stderr}"
        if "PermissionError" not in output or attempt == 11:
            raise RuntimeError(f"{bundle.name} producer failed:\n{output}")
        time.sleep(0.75)
    raise AssertionError("producer retry loop exhausted")


def _source_table(bundle: Path, example: Example):
    return table_from_data(
        (bundle / "data" / "src" / example.input_name).read_bytes(),
        name="raw_input",
        purpose="verification_source",
    )


def _attach_source_link(bundle: Path, example: Example) -> None:
    master = bundle / "fig" / example.figure_name
    record = extract_record(master)
    record.figure_id = example.figure_id
    target = next(table for table in record.data_tables if table.name == "figure_data")
    transformation = TransformationSpec(
        operation="select",
        input_table_ids=[SOURCE_ID],
        output_table_id=f"table:{target.sha256}",
        parameters={"columns": list(example.columns)},
    )
    proof = dict(record.extensions.get("proof") or {})
    proof["transformations"] = [transformation.to_dict()]
    for volatile in ("schema", "sections", "root_sha256", "signatures"):
        proof.pop(volatile, None)
    record.extensions["proof"] = proof
    record = attach_evidence_graph(record)
    for attempt in range(12):
        try:
            embed_file(master, record, output_path=master)
            return
        except PermissionError:
            if attempt == 11:
                raise
            time.sleep(0.75)


def _reproduce(bundle: Path, example: Example) -> None:
    report = reproduce_figure(
        bundle / "fig" / example.figure_name,
        bundle_root=bundle,
        output_dir=bundle / "verification" / "reproduced",
        report_path=bundle / "verification" / "reproduction-report.json",
        execute_trusted_producer=True,
        overwrite=True,
    )
    if not report.valid:
        raise RuntimeError(report.to_json(indent=2))


def _register_script() -> Path:
    explicit = os.environ.get("PLOT_THAT_REGISTER")
    if explicit:
        return Path(explicit)
    scripts = os.environ.get("PLOT_THAT_SCRIPTS")
    if scripts:
        return Path(scripts) / "register.py"
    return Path.home() / ".claude" / "skills" / "plot-that" / "scripts" / "register.py"


def _register(bundle: Path, example: Example) -> None:
    command = [
        sys.executable,
        str(_register_script()),
        "add",
        str(bundle),
        "--claim",
        example.claim,
        "--grammar",
        example.grammar,
        "--producer",
        "code/plot.py",
        "--statistics-status",
        "complete",
        "--figure",
        f"fig/{example.figure_name}",
        "--proof",
        "--proof-policy",
        str(bundle / "verification" / "policy.json"),
    ]
    for attempt in range(12):
        result = subprocess.run(command, text=True, capture_output=True)
        output = f"{result.stdout}{result.stderr}"
        if result.returncode == 0:
            print(output, end="")
            return
        if not any(marker in output for marker in ("PermissionError", "Access is denied")) or attempt == 11:
            raise RuntimeError(f"{bundle.name} registration failed:\n{output}")
        time.sleep(0.75)
    raise AssertionError("registration retry loop exhausted")


def _portable(report, example: Example):
    relative = f"fig/{example.figure_name}"
    report.path = relative
    if isinstance(report.integrity, dict):
        report.integrity = {**report.integrity, "path": relative}
    return report


def _verify(bundle: Path, example: Example):
    report = verify_proof(
        bundle / "fig" / example.figure_name,
        required=REQUIRED,
        source_tables={SOURCE_ID: _source_table(bundle, example)},
        reproduction_report=bundle / "verification" / "reproduction-report.json",
    )
    report = _portable(report, example)
    if not report.valid:
        raise RuntimeError(report.to_json(indent=2))
    _write_json(
        bundle
        / "verification"
        / f"{example.export_stem}-verification-report.json",
        report.to_dict(),
    )
    with (
        bundle
        / "verification"
        / f"{example.export_stem}-verification-summary.csv"
    ).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["meaning", "status"])
        writer.writerows((meaning, report.meanings[meaning]) for meaning in REQUIRED)
    return report


def _unpack(bundle: Path, example: Example) -> None:
    destination = bundle / "unpacked"
    with tempfile.TemporaryDirectory(prefix="reprofig-diverse-example-") as temporary:
        outputs = extract_artifact(bundle / "fig" / example.figure_name, temporary, overwrite=True)
        for source in outputs:
            for attempt in range(12):
                try:
                    shutil.copy2(source, destination / source.name)
                    break
                except PermissionError:
                    if attempt == 11:
                        raise
                    time.sleep(0.75)


def _presentation(bundle: Path, example: Example, report) -> None:
    presentation = bundle / "presentation"
    passed = "".join(f"<li><strong>{html.escape(meaning.replace('_', ' '))}</strong>: pass</li>" for meaning in REQUIRED)
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(example.title)} verification example</title>
<style>
body{{font-family:Arial,Helvetica,sans-serif;color:#303030;margin:0;background:#f4f6f8}}main{{max-width:1180px;margin:0 auto;padding:34px}}h1{{font-size:30px;margin:0 0 6px}}.lede{{font-size:18px;margin:0 0 26px;color:#555}}.card{{background:white;border:1px solid #dfe4ea;border-radius:12px;padding:24px;margin-bottom:22px}}.figure{{display:block;max-width:720px;width:100%;margin:0 auto}}.workflow{{display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap}}.step{{border:2px solid #4878A8;border-radius:8px;padding:10px 14px;background:#f7fbff;font-weight:700}}.arrow{{font-size:24px;color:#777}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:22px}}ul{{line-height:1.7}}iframe{{width:100%;height:680px;border:1px solid #dfe4ea;background:white}}code{{background:#eef1f4;padding:2px 5px;border-radius:4px}}@media(max-width:800px){{.grid{{grid-template-columns:1fr}}main{{padding:18px}}}}
</style>
</head>
<body><main>
<h1>{html.escape(example.title)}</h1>
<p class="lede">One {html.escape(example.library)} figure, one {html.escape(example.test)}, one verification workflow.</p>
<section class="card"><img class="figure" src="../fig/preview.png" alt="{html.escape(example.title)} figure"></section>
<section class="card"><div class="workflow"><span class="step">Raw CSV</span><span class="arrow">→</span><span class="step">Exact producer</span><span class="arrow">→</span><span class="step">ReproFig master</span><span class="arrow">→</span><span class="step">Independent checks</span><span class="arrow">→</span><span class="step">Saved reproduction</span></div></section>
<section class="grid"><div class="card"><h2>Claim</h2><p>{html.escape(example.claim)}</p><h2>Analysis</h2><p>{html.escape(example.test)}</p></div><div class="card"><h2>Verification</h2><ul>{passed}</ul><p>Complete machine report: <code>../verification/{example.export_stem}-verification-report.json</code></p></div></section>
<section class="card"><h2>Exact producer code</h2><p>This is a rendered copy of <code>../code/plot.py</code>, not a shortened illustration.</p><iframe src="{example.export_stem}-code.html" title="Exact syntax-highlighted producer code"></iframe></section>
</main></body></html>"""
    (presentation / "index.html").write_text(page, encoding="utf-8")


def _check_files(bundle: Path, example: Example) -> None:
    required = (
        bundle / "README.md",
        bundle / "code" / "plot.py",
        bundle / "data" / "sources.csv",
        bundle / "data" / "der" / "figure_data.csv",
        bundle / "data" / "der" / "statistics.csv",
        bundle / "fig" / example.figure_name,
        bundle / "fig" / "preview.png",
        bundle / "presentation" / "index.html",
        bundle / "presentation" / f"{example.export_stem}-code.html",
        bundle / "presentation" / f"{example.export_stem}-code.svg",
        bundle / "verification" / "reproduction-report.json",
        bundle
        / "verification"
        / f"{example.export_stem}-verification-report.json",
    )
    missing = [path.relative_to(bundle).as_posix() for path in required if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"{bundle.name} is incomplete: {missing}")


def build(*, register: bool) -> None:
    register_script = _register_script()
    if register and not register_script.is_file():
        raise FileNotFoundError(register_script)
    summary = {"schema": "reprofig/diverse-verification-examples/1", "examples": {}}
    for example in EXAMPLES:
        bundle = _prepare(example)
        _run_producer(bundle)
        _attach_source_link(bundle, example)
        _reproduce(bundle, example)
        if register:
            _register(bundle, example)
        report = _verify(bundle, example)
        _unpack(bundle, example)
        _presentation(bundle, example, report)
        _check_files(bundle, example)
        record = extract_record(bundle / "fig" / example.figure_name)
        summary["examples"][example.folder] = {
            "claim": example.claim,
            "figure": f"{example.folder}/fig/{example.figure_name}",
            "figure_id": record.figure_id,
            "library": example.library,
            "statistical_test": example.test,
            "valid": report.valid,
            "required_meanings": list(REQUIRED),
        }
    _write_json(ROOT / "build-summary.json", summary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--register", action="store_true", help="register the finished bundles with plot-that")
    args = parser.parse_args()
    build(register=args.register)


if __name__ == "__main__":
    main()
