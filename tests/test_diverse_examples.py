from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import pytest

from reprofig import extract_record
from reprofig.stats.engine import specifications_from_record


ROOT = Path(__file__).resolve().parents[1] / "examples" / "diverse-verification-workflows"
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
    masters = [path for path in (bundle / "fig").iterdir() if path.name != "preview.png"]
    assert len(masters) == 1
    master = masters[0]
    assert master.suffix == suffix

    report = json.loads((bundle / "verification" / "report.json").read_text(encoding="utf-8"))
    assert report["valid"] is True
    assert all(report["meanings"][meaning] == "pass" for meaning in report["required"])
    reproduction = json.loads(
        (bundle / "verification" / "reproduction-report.json").read_text(encoding="utf-8")
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
    record = extract_record(master)
    assert record.producer["package"] == package
    assert record.reproduction["script"] == producer.read_text(encoding="utf-8")
    assert [item.algorithm_id for item in specifications_from_record(record)] == [algorithm_id]
    with (bundle / "data" / "der" / "statistics.csv").open(newline="", encoding="utf-8") as handle:
        assert len(list(csv.DictReader(handle))) == 1

    source = next(csv.DictReader((bundle / "data" / "sources.csv").open(newline="", encoding="utf-8")))
    copied = bundle / Path(source["copied_path"])
    assert _sha256(copied) == source["sha256"]
    presentation = (bundle / "presentation" / "index.html").read_text(encoding="utf-8")
    rendered_code = (bundle / "presentation" / "plot.py.html").read_text(encoding="utf-8")
    assert 'src="plot.py.html"' in presentation
    assert "Exact producer code" in rendered_code
    assert (bundle / "presentation" / "plot.py.svg").stat().st_size > producer.stat().st_size


def test_diverse_example_summary_lists_only_the_three_workflows() -> None:
    summary = json.loads((ROOT / "build-summary.json").read_text(encoding="utf-8"))
    assert set(summary["examples"]) == set(EXPECTED)
    assert all(value["valid"] for value in summary["examples"].values())
