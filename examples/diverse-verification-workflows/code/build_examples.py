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
import textwrap
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from reprofig import (
    TransformationSpec,
    attach_evidence_graph,
    embed_file,
    extract_artifact,
    extract_record,
    reproduce_figure,
    statistics_csv_bytes,
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
    code_figure_id: str
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
        code_figure_id="rf-e68703100be94378affc542e7c7eb32b",
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
        code_figure_id="rf-c841205641e6497ea9f3a16c23e72961",
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
        code_figure_id="rf-16450315b13940c6be000aaf0c94b9d0",
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
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


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
            fieldnames=[
                "original_path",
                "copied_path",
                "file_name",
                "modification_time",
                "byte_size",
                "sha256",
                "public_uri",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(
            {
                "original_path": f"input/{original.name}",
                "copied_path": f"data/src/{copied.name}",
                "file_name": copied.name,
                "modification_time": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(timespec="seconds"),
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


def _plot_that_scripts() -> Path:
    configured = os.environ.get("PLOT_THAT_SCRIPTS")
    if configured:
        return Path(configured)
    return Path.home() / ".claude" / "skills" / "plot-that" / "scripts"


def _code_figure_claim(example: Example) -> str:
    return (
        f"This is the complete {example.library} producer used to create the "
        f"neighboring {example.title.lower()} example plot."
    )


def _code_figure_producer(example: Example) -> str:
    return textwrap.dedent(f'''\
        """Render the example's exact plotting script as a traceable code figure."""

        from __future__ import annotations

        import csv
        import sys
        from pathlib import Path

        from reprofig import build_record, embed_file

        BUNDLE = Path(__file__).resolve().parent.parent
        sys.path.insert(0, str(BUNDLE / "data" / "src"))
        from code_figure import Panel, line_table, save  # noqa: E402

        SOURCE = BUNDLE / "data" / "src" / "example-plot.py"
        PANELS = [
            Panel(
                label={f"EXACT {example.library.upper()} PRODUCER"!r},
                code=SOURCE.read_text(encoding="utf-8"),
                accent="blue",
            )
        ]


        def main() -> None:
            result = save(
                PANELS,
                BUNDLE / "fig" / {f"{example.export_stem}-code.svg"!r},
                png=str(BUNDLE / "fig" / {f"{example.export_stem}-code.png"!r}),
                png_scale=2.0,
            )
            rows = line_table(PANELS)
            table = BUNDLE / "data" / "der" / "figure_data.csv"
            with table.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            record = build_record(
                title={f"{example.title} producer code"!r},
                original_stem={f"{example.export_stem}-code"!r},
                producer={{"package": "plot-that", "grammar": "code-panel"}},
                plotted_data=table.read_bytes(),
                data_status="incomplete",
                statistics_status="complete",
                reproduction={{
                    "script": Path(__file__).read_text(encoding="utf-8"),
                    "command": "python code/plot.py",
                }},
            )
            record.figure_id = {example.code_figure_id!r}
            for target in (
                BUNDLE / "fig" / {f"{example.export_stem}-code.svg"!r},
                BUNDLE / "fig" / {f"{example.export_stem}-code.png"!r},
            ):
                embed_file(target, record, output_path=target)
            print(
                f"{{result['width']:g}} x {{result['height']:g}}, "
                f"{{result['lines']}} source lines; {{result['rasteriser']}}"
            )


        if __name__ == "__main__":
            main()
        ''')


def _prepare_code_figure(bundle: Path, example: Example) -> Path:
    code_bundle = bundle / "code-figure"
    for relative in ("code", "data/der", "data/src", "fig"):
        (code_bundle / relative).mkdir(parents=True, exist_ok=True)

    source = bundle / "code" / "plot.py"
    copied_source = code_bundle / "data" / "src" / "example-plot.py"
    helper = _plot_that_scripts() / "code_figure.py"
    copied_helper = code_bundle / "data" / "src" / "code_figure.py"
    if not helper.is_file():
        raise FileNotFoundError(helper)
    shutil.copy2(source, copied_source)
    shutil.copy2(helper, copied_helper)
    (code_bundle / "code" / "plot.py").write_text(
        _code_figure_producer(example),
        encoding="utf-8",
    )

    source_rows = []
    for copied, original_path in (
        (copied_source, "../code/plot.py"),
        (copied_helper, "plot-that/scripts/code_figure.py"),
    ):
        stat = copied.stat()
        source_rows.append(
            {
                "original_path": original_path,
                "copied_path": f"data/src/{copied.name}",
                "file_name": copied.name,
                "modification_time": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(timespec="seconds"),
                "byte_size": stat.st_size,
                "sha256": _sha256(copied),
                "public_uri": "",
            }
        )
    with (code_bundle / "data" / "sources.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=list(source_rows[0]),
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(source_rows)
    (code_bundle / "data" / "sources.md").write_text(
        "# Source index\n\n"
        "`data/src/example-plot.py` is the complete script shown in the figure. "
        "`data/src/code_figure.py` is the copied renderer needed to reproduce it. "
        "Their SHA-256 digests are recorded in `sources.csv`.\n",
        encoding="utf-8",
    )
    (code_bundle / "README.md").write_text(
        f"# {example.title} producer code\n\n"
        f"Claim: {_code_figure_claim(example)}\n\n"
        "The editable SVG and 2x PNG are two carriers of one ReproFig figure "
        "identity. The plotted data are a per-line table of the exact source "
        "text, token classes, and rendered coordinates. No inferential "
        "statistics apply to this code figure.\n",
        encoding="utf-8",
    )
    return code_bundle


def _prepare(example: Example) -> Path:
    bundle = ROOT / example.folder
    _remove_generated(bundle)
    for relative in (
        "code",
        "data/der",
        "data/src",
        "fig",
        "presentation",
        "unpacked",
        "verification/reproduced",
    ):
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
    _prepare_code_figure(bundle, example)
    return bundle


def _run_producer(bundle: Path) -> None:
    environment = os.environ.copy()
    environment.update(
        {"MPLBACKEND": "Agg", "PYTHONDONTWRITEBYTECODE": "1", "PYTHONHASHSEED": "0"}
    )
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


def _materialize_embedded_tables(bundle: Path, example: Example) -> None:
    """Keep presentation CSVs outside the user-facing producer code."""

    record = extract_record(bundle / "fig" / example.figure_name)
    table = record.data_tables[0]
    (bundle / "data" / "der" / "figure_data.csv").write_text(
        table.contents or "",
        encoding="utf-8",
        newline="",
    )
    (bundle / "data" / "der" / "statistics.csv").write_bytes(
        statistics_csv_bytes(record.statistics)
    )


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
    target = record.data_tables[0]
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
    return _plot_that_scripts() / "register.py"


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
        if (
            not any(
                marker in output for marker in ("PermissionError", "Access is denied")
            )
            or attempt == 11
        ):
            raise RuntimeError(f"{bundle.name} registration failed:\n{output}")
        time.sleep(0.75)
    raise AssertionError("registration retry loop exhausted")


def _register_code_figure(bundle: Path, example: Example) -> None:
    code_bundle = bundle / "code-figure"
    command = [
        sys.executable,
        str(_register_script()),
        "add",
        str(code_bundle),
        "--claim",
        _code_figure_claim(example),
        "--grammar",
        "code-panel",
        "--producer",
        "code/plot.py",
        "--statistics-status",
        "not_applicable",
        "--figure",
        f"fig/{example.export_stem}-code.svg",
    ]
    for attempt in range(12):
        result = subprocess.run(command, text=True, capture_output=True)
        output = f"{result.stdout}{result.stderr}"
        if result.returncode == 0:
            print(output, end="")
            return
        if (
            not any(
                marker in output for marker in ("PermissionError", "Access is denied")
            )
            or attempt == 11
        ):
            raise RuntimeError(f"{code_bundle.name} registration failed:\n{output}")
        time.sleep(0.75)
    raise AssertionError("code-figure registration retry loop exhausted")


def _copy_code_figures(bundle: Path, example: Example) -> None:
    presentation = bundle / "presentation"
    presentation.mkdir(parents=True, exist_ok=True)
    for suffix in ("svg", "png"):
        name = f"{example.export_stem}-code.{suffix}"
        shutil.copy2(bundle / "code-figure" / "fig" / name, presentation / name)


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
        bundle / "verification" / f"{example.export_stem}-verification-report.json",
        report.to_dict(),
    )
    with (
        bundle / "verification" / f"{example.export_stem}-verification-summary.csv"
    ).open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["meaning", "status"])
        writer.writerows((meaning, report.meanings[meaning]) for meaning in REQUIRED)
    return report


def _unpack(bundle: Path, example: Example) -> None:
    destination = bundle / "unpacked"
    with tempfile.TemporaryDirectory(prefix="reprofig-diverse-example-") as temporary:
        outputs = extract_artifact(
            bundle / "fig" / example.figure_name, temporary, overwrite=True
        )
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
    passed = "".join(
        f"<li><strong>{html.escape(meaning.replace('_', ' '))}</strong>: pass</li>"
        for meaning in REQUIRED
    )
    page = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(example.title)} verification example</title>
<style>
body{{font-family:Arial,Helvetica,sans-serif;color:#303030;margin:0;background:#f4f6f8}}main{{max-width:1320px;margin:0 auto;padding:34px}}h1{{font-size:30px;margin:0 0 6px}}.lede{{font-size:18px;margin:0 0 26px;color:#555}}.card{{background:white;border:1px solid #dfe4ea;border-radius:12px;padding:24px;margin-bottom:22px}}.figure,.code-figure{{display:block;width:100%;height:auto;margin:0 auto}}.figure{{max-width:720px}}.code-figure{{border:1px solid #dfe4ea}}.showcase{{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:22px;align-items:start}}.workflow{{display:flex;align-items:center;justify-content:center;gap:10px;flex-wrap:wrap}}.step{{border:2px solid #4878A8;border-radius:8px;padding:10px 14px;background:#f7fbff;font-weight:700}}.arrow{{font-size:24px;color:#777}}.grid{{display:grid;grid-template-columns:1fr 1fr;gap:22px;align-items:start}}ul{{line-height:1.7}}code{{background:#eef1f4;padding:2px 5px;border-radius:4px}}@media(max-width:900px){{.grid,.showcase{{grid-template-columns:1fr}}main{{padding:18px}}}}
</style>
</head>
<body><main>
<h1>{html.escape(example.title)}</h1>
<p class="lede">One {html.escape(example.library)} figure, one {html.escape(example.test)}, one verification workflow.</p>
<section class="showcase"><div class="card"><h2>Result</h2><img class="figure" src="../fig/preview.png" alt="{html.escape(example.title)} figure"></div><div class="card"><h2>Exact producer code</h2><p>The PNG is generated from <code>../code/plot.py</code> by the audited code-panel workflow. ReproFig creates the hashes and JSON internally. Open the <a href="{example.export_stem}-code.svg">editable SVG</a> for selectable text.</p><img class="code-figure" src="{example.export_stem}-code.png" alt="Exact syntax-highlighted producer code"></div></section>
<section class="card"><div class="workflow"><span class="step">Raw CSV</span><span class="arrow">→</span><span class="step">Exact producer</span><span class="arrow">→</span><span class="step">ReproFig master</span><span class="arrow">→</span><span class="step">Independent checks</span><span class="arrow">→</span><span class="step">Saved reproduction</span></div></section>
<section class="grid"><div class="card"><h2>Claim</h2><p>{html.escape(example.claim)}</p><h2>Analysis</h2><p>{html.escape(example.test)}</p></div><div class="card"><h2>Verification</h2><ul>{passed}</ul><p>Complete machine report: <code>../verification/{example.export_stem}-verification-report.json</code></p></div></section>
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
        bundle / "presentation" / f"{example.export_stem}-code.svg",
        bundle / "presentation" / f"{example.export_stem}-code.png",
        bundle / "code-figure" / "README.md",
        bundle / "code-figure" / "code" / "plot.py",
        bundle / "code-figure" / "data" / "sources.csv",
        bundle / "code-figure" / "data" / "der" / "figure_data.csv",
        bundle / "code-figure" / "fig" / f"{example.export_stem}-code.svg",
        bundle / "code-figure" / "fig" / f"{example.export_stem}-code.png",
        bundle / "verification" / "reproduction-report.json",
        bundle / "verification" / f"{example.export_stem}-verification-report.json",
    )
    missing = [
        path.relative_to(bundle).as_posix() for path in required if not path.is_file()
    ]
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
        _materialize_embedded_tables(bundle, example)
        _run_producer(bundle / "code-figure")
        _attach_source_link(bundle, example)
        _reproduce(bundle, example)
        if register:
            _register(bundle, example)
            _register_code_figure(bundle, example)
        report = _verify(bundle, example)
        _unpack(bundle, example)
        _copy_code_figures(bundle, example)
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
            "code_figure": f"{example.folder}/presentation/{example.export_stem}-code.png",
            "code_figure_bundle": f"{example.folder}/code-figure",
            "code_figure_id": example.code_figure_id,
        }
    _write_json(ROOT / "build-summary.json", summary)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--register",
        action="store_true",
        help="register the finished bundles with plot-that",
    )
    args = parser.parse_args()
    build(register=args.register)


if __name__ == "__main__":
    main()
