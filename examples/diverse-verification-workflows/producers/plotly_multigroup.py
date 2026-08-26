"""Draw and package one multigroup example with Plotly."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import shutil
from pathlib import Path
from statistics import mean

import plotly.graph_objects as go
from scipy.stats import f_oneway

from reprofig import (
    StatisticalSpecification,
    attach_evidence_graph,
    build_record,
    embed_file,
    refresh_visual_reference,
    source_reference,
    table_from_data,
)
from reprofig.render import AnnotationSemantic, AxesSemantic, MarkSemantic, RenderManifest

CLAIM = "Mean response differs across the three conditions in this synthetic dataset."
GRAMMAR = "box and raw-points plot"
STATISTIC_ID = "condition-one-way-anova"
FIGURE_NAME = "condition-response.png"
GROUPS = ("Control", "Low dose", "High dose")
COLORS = ("#4878A8", "#0e8f8f", "#d98a17")
OFFSETS = (-0.14, -0.10, -0.06, -0.02, 0.02, 0.06, 0.10, 0.14)


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["sample", "condition", "response"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    bundle = Path(__file__).resolve().parents[1]
    source = bundle / "data" / "src" / "multigroup.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    values = {
        group: [float(row["response"]) for row in rows if row["condition"] == group]
        for group in GROUPS
    }
    result = f_oneway(*(values[group] for group in GROUPS))
    p_value = float(result.pvalue)
    expected = {
        "statistic": float(result.statistic),
        "p_value": p_value,
        "df1": len(GROUPS) - 1,
        "df2": len(rows) - len(GROUPS),
        "group_sizes": [len(values[group]) for group in GROUPS],
        "group_means": [mean(values[group]) for group in GROUPS],
    }
    display_format = "p_threshold_0.001/v1" if p_value < 0.001 else "p_equals_4dp/v1"
    display_text = "p < 0.001" if p_value < 0.001 else f"p = {p_value:.4f}"
    specification = StatisticalSpecification(
        statistic_id=STATISTIC_ID,
        algorithm_id="one-way-anova/v1",
        inputs={"groups": [values[group] for group in GROUPS]},
        parameters={"producer_implementation": "scipy.stats.f_oneway/1"},
        expected=expected,
        display={"field": "p_value", "format": display_format, "text": display_text},
        tolerances={"*": {"absolute": 1e-12, "relative": 1e-10}},
    )
    statistic = {
        "statistic_id": STATISTIC_ID,
        "test_name": "one-way analysis of variance",
        "groups": " | ".join(GROUPS),
        "n_total": len(rows),
        "group_n": " | ".join(str(len(values[group])) for group in GROUPS),
        "statistic": float(result.statistic),
        "degrees_of_freedom_1": expected["df1"],
        "degrees_of_freedom_2": expected["df2"],
        "p_value": p_value,
        "tailedness": "upper-tail F test",
        "correction_method": "none",
        "alpha": 0.05,
        "algorithm_id": specification.algorithm_id,
        "inputs_json": _json(specification.inputs),
        "parameters_json": _json(specification.parameters),
        "expected_json": _json(specification.expected),
        "display_json": _json(specification.display),
        "tolerances_json": _json(specification.tolerances),
    }
    figure_data = bundle / "data" / "der" / "figure_data.csv"
    _write_csv(figure_data, rows)
    with (bundle / "data" / "der" / "statistics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(statistic), lineterminator="\n")
        writer.writeheader()
        writer.writerow(statistic)

    plotted_table = table_from_data(figure_data.read_bytes(), name="figure_data", purpose="plot_and_statistics")
    table_id = f"table:{plotted_table.sha256}"
    fig = go.Figure()
    marks = []
    for position, (group, color) in enumerate(zip(GROUPS, COLORS)):
        group_values = values[group]
        fig.add_trace(
            go.Box(
                x=[position] * len(group_values),
                y=group_values,
                width=0.48,
                boxpoints=False,
                fillcolor=color,
                opacity=0.30,
                line={"color": color, "width": 2},
                marker={"color": color},
                hoverinfo="skip",
                showlegend=False,
                name=group,
            )
        )
        fig.add_trace(
            go.Scatter(
                x=[position + offset for offset in OFFSETS],
                y=group_values,
                mode="markers",
                marker={"size": 10, "color": color, "line": {"color": "white", "width": 1}},
                hovertemplate="%{y:.1f}<extra></extra>",
                showlegend=False,
                name=f"{group} observations",
            )
        )
        members = [row for row in rows if row["condition"] == group]
        marks.append(
            MarkSemantic(
                mark_id=f"{group.lower().replace(' ', '-')}-observations",
                kind="points",
                axes_id="plotly-main",
                geometry={"points": [[position + offset, value] for offset, value in zip(OFFSETS, group_values)]},
                table_id=table_id,
                row_ids=[row["sample"] for row in members],
                columns=["condition", "response"],
                role="raw observations",
            )
        )
    fig.add_annotation(x=1, y=7.62, text=f"ANOVA {display_text}", showarrow=False, font={"size": 16, "color": "#303030"})
    fig.update_layout(
        title={"text": "Response differs across conditions", "x": 0.5, "xanchor": "center"},
        width=800,
        height=580,
        margin={"l": 90, "r": 35, "t": 85, "b": 80},
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"family": "Arial, Helvetica, sans-serif", "size": 17, "color": "#303030"},
        xaxis={"tickmode": "array", "tickvals": [0, 1, 2], "ticktext": list(GROUPS), "range": [-0.5, 2.5], "title": "", "showline": True, "linewidth": 2, "linecolor": "black", "ticks": ""},
        yaxis={"range": [4.5, 7.85], "title": "Response (arbitrary units)", "showline": True, "linewidth": 2, "linecolor": "black", "ticks": "outside", "tickwidth": 2, "gridcolor": "#eeeeee", "zeroline": False},
    )
    master = bundle / "fig" / FIGURE_NAME
    master.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(master, format="png", width=800, height=580, scale=2)

    manifest = RenderManifest(
        axes=[AxesSemantic(axes_id="plotly-main", x_limits=(-0.5, 2.5), y_limits=(4.5, 7.85), labels={"x": "condition", "y": "response"})],
        marks=marks,
        annotations=[AnnotationSemantic(annotation_id="anova-result", text=f"ANOVA {display_text}", axes_id="plotly-main", position=(1.0, 7.62), statistic_id=STATISTIC_ID, formatter_id=display_format, connected_mark_ids=[str(mark.mark_id) for mark in marks], role="statistical annotation")],
        environment={"renderer": "plotly+kaleido", "plotly": importlib.metadata.version("plotly")},
    )
    producer_source = Path(__file__).read_text(encoding="utf-8")
    record = build_record(
        title=CLAIM,
        original_stem="condition-response",
        producer={"package": "plotly", "package_version": importlib.metadata.version("plotly"), "function": "code/plot.py"},
        analysis={"claim": CLAIM, "grammar": GRAMMAR, "input_kind": "plain CSV"},
        data_tables=[plotted_table],
        statistics=[statistic],
        sources=[source_reference(source, role="raw_user_input", project_root=bundle, source_id="multigroup-source")],
        reproduction={
            "command": "python code/plot.py",
            "script": producer_source,
            "producer": "code/plot.py",
            "producer_language": "python",
            "producer_sha256": _sha256(Path(__file__)),
            "working_directory": ".",
            "output": f"fig/{FIGURE_NAME}",
            "input": "data/src/multigroup.csv",
            "exact_table": "data/der/figure_data.csv",
            "exact_table_sha256": _sha256(figure_data),
            "source_index": "data/sources.csv",
            "source_index_sha256": _sha256(bundle / "data" / "sources.csv"),
            "readme": "README.md",
            "readme_sha256": _sha256(bundle / "README.md"),
        },
        data_status="complete",
        statistics_status="complete",
        extensions={"render_manifest": manifest.to_dict(), "proof": {"statistical_specifications": [specification.to_dict()]}},
    )
    record = refresh_visual_reference(master, record)
    record = attach_evidence_graph(record)
    embed_file(master, record, output_path=master)
    shutil.copy2(master, bundle / "fig" / "preview.png")


if __name__ == "__main__":
    main()
