from __future__ import annotations

import json

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

matplotlib.use("Agg")

from reprofig import (
    attach,
    export_fsb,
    export_rocrate,
    extract_record,
    import_fsb,
    save_svg,
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
        producer={"package": "clock-analysis", "version": "2.0", "function": "plot_trace"},
    )
    plt.close(fig)
    loaded = extract_record(path)
    assert loaded.figure_id == saved.figure_id
    assert loaded.producer["package"] == "clock-analysis"
    assert loaded.data_tables[0].row_count == 3
    assert "<text" in path.read_text(encoding="utf-8")


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
    assert imported.data_tables[0].contents == extract_record(svg).data_tables[0].contents
    assert imported.statistics[0]["p"] == 0.2
    crate = tmp_path / "crate"
    crate.mkdir()
    copied = crate / svg.name
    copied.write_bytes(svg.read_bytes())
    metadata = export_rocrate(crate, [copied])
    value = json.loads(metadata.read_text(encoding="utf-8"))
    assert value["@context"].endswith("/context")
    assert any(item.get("@id") == svg.name for item in value["@graph"])

