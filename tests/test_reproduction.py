from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

from reprofig import reproduce_figure, verify_proof
from reprofig.cli import main as cli_main
from reprofig.reproduction import FigureReproductionReport


PRODUCER = '''from __future__ import annotations

import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
matplotlib.rcParams["svg.hashsalt"] = "reprofig-reproduction-test"
import matplotlib.pyplot as plt

from reprofig import (
    attach_evidence_graph,
    bind_artist,
    build_record,
    save_figure,
    source_reference,
    table_from_data,
)


def main() -> None:
    bundle = Path(__file__).resolve().parents[1]
    source = bundle / "data" / "src" / "input.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    x = [float(row["x"]) for row in rows]
    y = [float(row["y"]) for row in rows]
    figure, axes = plt.subplots(figsize=(4, 3))
    line, = axes.plot(x, y, marker="o")
    bind_artist(line, semantic_id="observations", columns=["x", "y"])
    axes.set(xlabel="x", ylabel="y", title="Trusted producer")
    table = table_from_data(rows, name="plotted_data", purpose="plot_and_statistics")
    record = build_record(
        title="Trusted producer",
        producer={"package": "matplotlib", "function": "code/plot.py"},
        analysis={"claim": "Values are plotted without transformation."},
        data_tables=[table],
        statistics=[{"test_id": "mean-y", "n": len(y), "value": sum(y) / len(y)}],
        statistics_status="complete",
        sources=[source_reference(
            source,
            role="raw_user_input",
            project_root=bundle,
            source_id="input",
        )],
        reproduction={
            "command": "python code/plot.py",
            "script": Path(__file__).read_text(encoding="utf-8"),
            "working_directory": ".",
            "producer": "code/plot.py",
            "output": "fig/chart.svg",
        },
    )
    record = attach_evidence_graph(record)
    save_figure(figure, bundle / "fig" / "chart.svg", record=record, proof=True)
    plt.close(figure)


if __name__ == "__main__":
    main()
'''


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _bundle(tmp_path: Path) -> tuple[Path, Path]:
    bundle = tmp_path / "bundle"
    (bundle / "code").mkdir(parents=True)
    (bundle / "data" / "src").mkdir(parents=True)
    (bundle / "fig").mkdir()
    (bundle / "code" / "plot.py").write_text(PRODUCER, encoding="utf-8")
    (bundle / "data" / "src" / "input.csv").write_text(
        "x,y\n0,1\n1,3\n2,2\n", encoding="utf-8"
    )
    subprocess.run(
        [sys.executable, "code/plot.py"], cwd=bundle, check=True, capture_output=True
    )
    return bundle, bundle / "fig" / "chart.svg"


def test_reproduce_figure_requires_explicit_trust(tmp_path):
    bundle, master = _bundle(tmp_path)

    with pytest.raises(PermissionError, match="execute_trusted_producer"):
        reproduce_figure(master, bundle_root=bundle, output_dir=bundle / "verification")


def test_reproduce_figure_saves_and_passively_verifies_separate_carrier(tmp_path):
    bundle, master = _bundle(tmp_path)
    before = _sha256(master)
    report_path = bundle / "verification" / "reproduction-report.json"

    report = reproduce_figure(
        master,
        bundle_root=bundle,
        output_dir=bundle / "verification" / "reproduced",
        report_path=report_path,
        execute_trusted_producer=True,
    )

    assert report.valid, report.to_dict()
    assert report.command == ["python", "code/plot.py"]
    assert _sha256(master) == before
    reproduced = bundle / "verification" / "reproduced" / "chart.reproduced.svg"
    assert reproduced.is_file()
    assert FigureReproductionReport.from_json(report_path).valid
    proof = verify_proof(
        master,
        required=["figure_reproduced"],
        reproduction_report=report_path,
    )
    assert proof.valid, proof.to_dict()


def test_passive_verification_detects_reproduced_carrier_tampering(tmp_path):
    bundle, master = _bundle(tmp_path)
    report_path = bundle / "verification" / "reproduction-report.json"
    reproduce_figure(
        master,
        bundle_root=bundle,
        output_dir=bundle / "verification" / "reproduced",
        report_path=report_path,
        execute_trusted_producer=True,
    )
    reproduced = bundle / "verification" / "reproduced" / "chart.reproduced.svg"
    reproduced.write_bytes(reproduced.read_bytes() + b"\n<!-- changed -->\n")

    proof = verify_proof(
        master,
        required=["figure_reproduced"],
        reproduction_report=report_path,
    )

    assert not proof.valid
    assert proof.status_for("figure_reproduced") == "fail"


def test_passive_verification_recalculates_claimed_comparisons(tmp_path):
    bundle, master = _bundle(tmp_path)
    report_path = bundle / "verification" / "reproduction-report.json"
    reproduce_figure(
        master,
        bundle_root=bundle,
        output_dir=bundle / "verification" / "reproduced",
        report_path=report_path,
        execute_trusted_producer=True,
    )
    other_bundle, other_master = _bundle(tmp_path / "other")
    (other_bundle / "data" / "src" / "input.csv").write_text(
        "x,y\n0,9\n1,8\n2,7\n", encoding="utf-8"
    )
    subprocess.run(
        [sys.executable, "code/plot.py"],
        cwd=other_bundle,
        check=True,
        capture_output=True,
    )
    reproduced = bundle / "verification" / "reproduced" / "chart.reproduced.svg"
    reproduced.write_bytes(other_master.read_bytes())
    report = json.loads(report_path.read_text(encoding="utf-8"))
    report["reproduced_sha256"] = _sha256(reproduced)
    report_path.write_text(json.dumps(report), encoding="utf-8")

    proof = verify_proof(
        master,
        required=["figure_reproduced"],
        reproduction_report=report_path,
    )

    assert not proof.valid
    assert proof.status_for("figure_reproduced") == "fail"


def test_figure_reproduced_is_unavailable_without_saved_report(tmp_path):
    _, master = _bundle(tmp_path)

    proof = verify_proof(master, required=["figure_reproduced"])

    assert not proof.valid
    assert proof.status_for("figure_reproduced") == "unavailable"


def test_reproduce_and_verify_cli_round_trip(tmp_path, capsys):
    bundle, master = _bundle(tmp_path)
    report_path = bundle / "verification" / "reproduction-report.json"

    status = cli_main([
        "reproduce",
        str(master),
        "--bundle-root",
        str(bundle),
        "--output-dir",
        str(bundle / "verification" / "reproduced"),
        "--report",
        str(report_path),
        "--execute-trusted-producer",
    ])
    assert status == 0
    capsys.readouterr()

    status = cli_main([
        "verify",
        str(master),
        "--require",
        "figure_reproduced",
        "--reproduction-report",
        str(report_path),
    ])
    output = capsys.readouterr().out
    assert status == 0
    assert '"figure_reproduced":"pass"' in output.replace(" ", "").replace("\n", "")
