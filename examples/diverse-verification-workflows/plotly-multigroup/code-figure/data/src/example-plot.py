"""Draw one proof-carrying multigroup figure with Plotly."""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import mean

import plotly.graph_objects as go
from scipy.stats import f_oneway

from reprofig import StatisticalSpecification, save_figure
from reprofig.render import (
    AnnotationSemantic,
    AxesSemantic,
    MarkSemantic,
    RenderManifest,
)

CLAIM = "Mean response differs across the three conditions in this synthetic dataset."
STATISTIC_ID = "condition-one-way-anova"
GROUPS = ("Control", "Low dose", "High dose")
COLORS = ("#4878A8", "#0e8f8f", "#d98a17")
OFFSETS = (-0.14, -0.10, -0.06, -0.02, 0.02, 0.06, 0.10, 0.14)


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
    }

    figure = go.Figure()
    marks = []
    for position, (group, color) in enumerate(zip(GROUPS, COLORS)):
        group_values = values[group]
        figure.add_trace(
            go.Box(
                x=[position] * len(group_values),
                y=group_values,
                width=0.48,
                boxpoints=False,
                fillcolor=color,
                opacity=0.30,
                line={"color": color, "width": 2},
                hoverinfo="skip",
                showlegend=False,
            )
        )
        figure.add_trace(
            go.Scatter(
                x=[position + offset for offset in OFFSETS],
                y=group_values,
                mode="markers",
                marker={
                    "size": 10,
                    "color": color,
                    "line": {"color": "white", "width": 1},
                },
                hovertemplate="%{y:.1f}<extra></extra>",
                showlegend=False,
            )
        )
        members = [row for row in rows if row["condition"] == group]
        marks.append(
            MarkSemantic(
                mark_id=f"{group.lower().replace(' ', '-')}-observations",
                kind="points",
                axes_id="plotly-main",
                geometry={
                    "points": [
                        [position + offset, value]
                        for offset, value in zip(OFFSETS, group_values)
                    ]
                },
                row_ids=[row["sample"] for row in members],
                columns=["condition", "response"],
                role="raw observations",
            )
        )
    figure.add_annotation(x=1, y=7.62, text=f"ANOVA {display_text}", showarrow=False)
    figure.update_layout(
        title={"text": "Response differs across conditions", "x": 0.5},
        width=800,
        height=580,
        margin={"l": 90, "r": 35, "t": 85, "b": 80},
        paper_bgcolor="white",
        plot_bgcolor="white",
        font={"family": "Arial, Helvetica, sans-serif", "size": 17, "color": "#303030"},
        xaxis={
            "tickmode": "array",
            "tickvals": [0, 1, 2],
            "ticktext": list(GROUPS),
            "range": [-0.5, 2.5],
            "showline": True,
            "linewidth": 2,
            "linecolor": "black",
        },
        yaxis={
            "range": [4.5, 7.85],
            "title": "Response (arbitrary units)",
            "showline": True,
            "linewidth": 2,
            "linecolor": "black",
            "gridcolor": "#eeeeee",
            "zeroline": False,
        },
    )
    manifest = RenderManifest(
        axes=[
            AxesSemantic(
                axes_id="plotly-main",
                x_limits=(-0.5, 2.5),
                y_limits=(4.5, 7.85),
                labels={"x": "condition", "y": "response"},
            )
        ],
        marks=marks,
        annotations=[
            AnnotationSemantic(
                annotation_id="anova-result",
                text=f"ANOVA {display_text}",
                axes_id="plotly-main",
                position=(1.0, 7.62),
                statistic_id=STATISTIC_ID,
                formatter_id=display_format,
                connected_mark_ids=[str(mark.mark_id) for mark in marks],
                role="statistical annotation",
            )
        ],
        environment={"renderer": "plotly+kaleido"},
    )

    record = save_figure(
        figure,
        bundle / "fig" / "condition-response.png",
        data=rows,
        sources=source,
        statistics=[statistic],
        statistical_specifications=[specification],
        title=CLAIM,
        claim=CLAIM,
        grammar="box and raw-points plot",
        analysis={"input_kind": "plain CSV"},
        extensions={"render_manifest": manifest.to_dict()},
        reproduction=True,
        proof=True,
        dpi=192,
        savefig_kwargs={"width": 800, "height": 580},
    )
    save_figure(
        figure,
        bundle / "fig" / "preview.png",
        record=record,
        proof=True,
        dpi=192,
        savefig_kwargs={"width": 800, "height": 580},
    )


if __name__ == "__main__":
    main()
