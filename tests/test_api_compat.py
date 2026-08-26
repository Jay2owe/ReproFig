from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")

from reprofig import (
    StatisticalSpecification,
    attach,
    export_fsb,
    export_rocrate,
    extract_record,
    file_sha256,
    import_fsb,
    save_figure,
    save_svg,
)


class _UnhashableWriteImageFigure:
    __hash__ = None

    def write_image(self, path, *, format, **_kwargs):
        assert format == "svg"
        Path(path).write_text(
            '<svg xmlns="http://www.w3.org/2000/svg" width="20" height="20">'
            '<circle cx="10" cy="10" r="5"/></svg>',
            encoding="utf-8",
        )


def test_generic_matplotlib_adapter_works_for_non_pyflash_package(tmp_path):
    frame = pd.DataFrame({"time": [0, 1, 2], "signal": [2.0, 3.0, 5.0]})
    fig, ax = plt.subplots()
    ax.plot(frame["time"], frame["signal"])
    attach(
        fig,
        plotted_data=frame,
        statistics=[],
        statistics_status="not_applicable",
        column_classification={"time": "safe", "signal": "safe"},
        column_roles={"time": "x", "signal": "y"},
    )
    path = tmp_path / "other-package.svg"
    saved = save_svg(
        fig,
        path,
        producer={
            "package": "clock-analysis",
            "version": "2.0",
            "function": "plot_trace",
        },
    )
    plt.close(fig)
    loaded = extract_record(path)
    assert loaded.figure_id == saved.figure_id
    assert loaded.producer["package"] == "clock-analysis"
    assert loaded.data_tables[0].row_count == 3
    assert "<text" in path.read_text(encoding="utf-8")


def test_one_call_save_captures_expected_provenance_internally(tmp_path):
    source = tmp_path / "input.csv"
    source.write_text("time,signal\n0,2\n1,3\n2,5\n", encoding="utf-8")
    frame = pd.read_csv(source)
    figure, axes = plt.subplots()
    axes.plot(frame["time"], frame["signal"])
    specification = StatisticalSpecification(
        statistic_id="mean-signal",
        algorithm_id="descriptive/v1",
        inputs={"values": frame["signal"].tolist()},
        parameters={"confidence_level": 0.95, "missing_policy": "omit"},
        expected={"n": 3, "mean": 10 / 3},
    )
    output = tmp_path / "fig" / "minimal.svg"

    save_figure(
        figure,
        output,
        data=frame,
        sources=source,
        statistics=[{"test_name": "mean", "n": 3, "estimate": 10 / 3}],
        statistical_specifications=[specification],
        claim="Signal is summarized without hidden provenance code.",
        reproduction=True,
        proof=True,
    )
    plt.close(figure)

    record = extract_record(output)
    assert record.producer["package"] == "matplotlib"
    assert record.analysis["claim"].startswith("Signal is summarized")
    assert record.data_tables[0].name == "figure_data"
    assert record.data_tables[0].row_count == 3
    assert record.sources[0].relative_path == "input.csv"
    assert record.sources[0].sha256 == file_sha256(source)
    assert record.reproduction["producer"] == "test_api_compat.py"
    assert record.reproduction["producer_sha256"] == file_sha256(__file__)
    assert record.reproduction["exact_table_sha256"] == record.data_tables[0].sha256
    assert json.loads(record.statistics[0]["inputs_json"]) == {"values": [2, 3, 5]}
    assert json.loads(record.statistics[0]["expected_json"])["n"] == 3
    proof = record.extensions["proof"]
    assert proof["statistical_specifications"][0]["algorithm_id"] == "descriptive/v1"


def test_save_figure_does_not_require_a_hashable_plotly_style_figure(tmp_path):
    output = tmp_path / "unhashable.svg"

    save_figure(
        _UnhashableWriteImageFigure(),
        output,
        data=[{"x": 1, "y": 2}],
    )

    assert extract_record(output).data_tables[0].row_count == 1


def test_fsb_and_rocrate_interoperability(tmp_path):
    frame = pd.DataFrame({"group": ["a", "b"], "value": [1.0, 2.0]})
    fig, ax = plt.subplots()
    ax.scatter(frame["group"], frame["value"])
    svg = tmp_path / "probe.svg"
    save_svg(
        fig,
        svg,
        plotted_data=frame,
        statistics=[{"kind": "comparison", "p": 0.2}],
        producer={"package": "compat-probe"},
        column_classification={"group": "safe", "value": "safe"},
    )
    plt.close(fig)
    bundle = export_fsb(svg, tmp_path / "bundle", svg_path=svg)
    imported = import_fsb(bundle)
    assert (
        imported.data_tables[0].contents == extract_record(svg).data_tables[0].contents
    )
    assert imported.statistics[0]["p"] == 0.2
    crate = tmp_path / "crate"
    crate.mkdir()
    copied = crate / svg.name
    copied.write_bytes(svg.read_bytes())
    metadata = export_rocrate(crate, [copied])
    value = json.loads(metadata.read_text(encoding="utf-8"))
    assert value["@context"].endswith("/context")
    assert any(item.get("@id") == svg.name for item in value["@graph"])
