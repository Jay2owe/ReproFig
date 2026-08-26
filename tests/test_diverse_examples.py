from __future__ import annotations

import csv
import hashlib
import json
import runpy
import subprocess
from pathlib import Path

import pytest

from reprofig import extract_record
from reprofig.stats.engine import specifications_from_record

ROOT = (
    Path(__file__).resolve().parents[1] / "examples" / "diverse-verification-workflows"
)
EXPECTED = {
    "matplotlib-paired-change": ("matplotlib", "wilcoxon/v1", ".svg"),
    "seaborn-regression": ("seaborn", "ols/v1", ".svg"),
    "plotly-multigroup": ("plotly", "one-way-anova/v1", ".png"),
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.parametrize("folder", EXPECTED)
def test_diverse_example_is_one_complete_reproducible_figure(folder: str) -> None:
    bundle = ROOT / folder
    package, algorithm_id, suffix = EXPECTED[folder]
    masters = [
        path for path in (bundle / "fig").iterdir() if path.name != "preview.png"
    ]
    assert len(masters) == 1
    master = masters[0]
    assert master.suffix == suffix
    stem = master.stem

    report = json.loads(
        (bundle / "verification" / f"{stem}-verification-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert report["valid"] is True
    assert all(report["meanings"][meaning] == "pass" for meaning in report["required"])
    reproduction = json.loads(
        (bundle / "verification" / "reproduction-report.json").read_text(
            encoding="utf-8"
        )
    )
    assert reproduction["valid"] is True
    assert reproduction["comparisons"] == {
        "data_tables": "pass",
        "display": "pass",
        "statistics": "pass",
    }
    reproduced = bundle / "verification" / reproduction["reproduced_path"]
    assert reproduced.is_file()
    assert _sha256(reproduced) == reproduction["reproduced_sha256"]

    producer = bundle / "code" / "plot.py"
    producer_text = producer.read_text(encoding="utf-8")
    assert "import hashlib" not in producer_text
    assert "import json" not in producer_text
    assert "build_record" not in producer_text
    record = extract_record(master)
    assert record.producer["package"] == package
    assert record.reproduction["script"] == producer_text
    assert record.reproduction["producer_sha256"] == _sha256(producer)
    assert [item.algorithm_id for item in specifications_from_record(record)] == [
        algorithm_id
    ]
    with (bundle / "data" / "der" / "statistics.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        statistics = list(csv.DictReader(handle))
    assert len(statistics) == 1
    for field in ("inputs_json", "parameters_json", "expected_json", "tolerances_json"):
        assert isinstance(json.loads(statistics[0][field]), dict)

    source = next(
        csv.DictReader(
            (bundle / "data" / "sources.csv").open(newline="", encoding="utf-8")
        )
    )
    copied = bundle / Path(source["copied_path"])
    assert _sha256(copied) == source["sha256"]
    presentation = (bundle / "presentation" / "index.html").read_text(encoding="utf-8")
    code_bundle = bundle / "code-figure"
    code_svg = code_bundle / "fig" / f"{stem}-code.svg"
    code_png = code_bundle / "fig" / f"{stem}-code.png"
    presentation_svg = bundle / "presentation" / f"{stem}-code.svg"
    presentation_png = bundle / "presentation" / f"{stem}-code.png"
    assert f'src="{stem}-code.png"' in presentation
    assert f'href="{stem}-code.svg"' in presentation
    assert "Exact producer code" in presentation
    assert code_svg.stat().st_size > producer.stat().st_size
    assert code_png.stat().st_size > 10_000
    assert presentation_svg.read_bytes() == code_svg.read_bytes()
    assert presentation_png.read_bytes() == code_png.read_bytes()

    svg_record = extract_record(code_svg)
    png_record = extract_record(code_png)
    assert svg_record.figure_id == png_record.figure_id
    figure_table = next(
        table for table in svg_record.data_tables if table.name == "figure_data"
    )
    assert figure_table.contents == (
        code_bundle / "data" / "der" / "figure_data.csv"
    ).read_text(encoding="utf-8")
    assert svg_record.reproduction["script"] == (
        code_bundle / "code" / "plot.py"
    ).read_text(encoding="utf-8")
    assert svg_record.reproduction["producer_sha256"] == _sha256(
        code_bundle / "code" / "plot.py"
    )
    assert svg_record.reproduction["source_index_sha256"] == _sha256(
        code_bundle / "data" / "sources.csv"
    )
    assert svg_record.reproduction["readme_sha256"] == _sha256(
        code_bundle / "README.md"
    )
    assert not (code_bundle / "data" / "der" / "statistics.csv").exists()
    with (code_bundle / "data" / "der" / "figure_data.csv").open(
        newline="", encoding="utf-8"
    ) as handle:
        lines = list(csv.DictReader(handle))
    source_lines = [
        line.replace("\t", "    ")
        for line in producer.read_text(encoding="utf-8").splitlines()
        if line
    ]
    assert [row["text"] for row in lines] == source_lines
    for source_row in csv.DictReader(
        (code_bundle / "data" / "sources.csv").open(newline="", encoding="utf-8")
    ):
        assert _sha256(code_bundle / source_row["copied_path"]) == source_row["sha256"]


def test_diverse_example_summary_lists_only_the_three_workflows() -> None:
    summary = json.loads((ROOT / "build-summary.json").read_text(encoding="utf-8"))
    assert set(summary["examples"]) == set(EXPECTED)
    assert all(value["valid"] for value in summary["examples"].values())


def test_code_figure_registration_retries_a_transient_dropbox_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    namespace = runpy.run_path(str(ROOT / "code" / "build_examples.py"))
    attempts = iter(
        (
            subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="",
                stderr="Access is denied while replacing the SVG",
            ),
            subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="registered\n",
                stderr="",
            ),
        )
    )
    calls = []

    def fake_run(*args, **kwargs):
        calls.append((args, kwargs))
        return next(attempts)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("time.sleep", lambda _seconds: None)

    namespace["_register_code_figure"](tmp_path, namespace["EXAMPLES"][0])

    assert len(calls) == 2
