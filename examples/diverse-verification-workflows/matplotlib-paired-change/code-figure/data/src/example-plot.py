"""Draw one proof-carrying paired-change figure with Matplotlib."""

from __future__ import annotations

import csv
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt
from scipy.stats import wilcoxon

from reprofig import StatisticalSpecification, bind_artist, save_figure

CLAIM = "Paired responses are higher after the intervention in this synthetic dataset."
STATISTIC_ID = "paired-change-wilcoxon"
BLUE, ORANGE, GREY, INK = "#4878A8", "#d98a17", "#c7c7c7", "#303030"


def main() -> None:
    bundle = Path(__file__).resolve().parents[1]
    source = bundle / "data" / "src" / "paired-change.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    before = [float(row["before"]) for row in rows]
    after = [float(row["after"]) for row in rows]
    differences = [right - left for left, right in zip(before, after)]
    result = wilcoxon(differences, alternative="two-sided", method="auto")
    p_value = float(result.pvalue)
    display_text = f"Wilcoxon p = {p_value:.4f}"
    specification = StatisticalSpecification(
        statistic_id=STATISTIC_ID,
        algorithm_id="wilcoxon/v1",
        inputs={"values_a": differences},
        parameters={
            "alternative": "two_sided",
            "zero_method": "wilcox",
            "correction": False,
            "method": "auto",
        },
        expected={"statistic": float(result.statistic), "p_value": p_value},
        display={
            "field": "p_value",
            "format": "p_equals_4dp/v1",
            "text": f"p = {p_value:.4f}",
        },
        tolerances={"*": {"absolute": 1e-12, "relative": 1e-10}},
    )
    statistic = {
        "statistic_id": STATISTIC_ID,
        "test_name": "Wilcoxon signed-rank test",
        "n": len(rows),
        "estimate": median(differences),
        "estimate_name": "median paired change",
        "statistic": float(result.statistic),
        "p_value": p_value,
        "tailedness": "two-sided",
        "correction_method": "none",
        "alpha": 0.05,
        "algorithm_id": specification.algorithm_id,
    }

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.size": 13,
            "svg.fonttype": "none",
            "svg.hashsalt": "reprofig-paired-change-example",
            "axes.linewidth": 1.8,
            "axes.labelsize": 15,
            "axes.titlesize": 17,
            "axes.titleweight": "bold",
        }
    )
    figure, axes = plt.subplots(figsize=(5.2, 5.0))
    for row, left, right in zip(rows, before, after):
        pair = axes.plot([0, 1], [left, right], color=GREY, linewidth=1.5)[0]
        bind_artist(
            pair,
            semantic_id=f"pair-{row['participant']}",
            row_ids=[row["participant"]],
            columns=["before", "after"],
            role="paired trajectory",
        )
    before_points = axes.scatter([0] * len(before), before, s=58, color=BLUE, zorder=3)
    after_points = axes.scatter([1] * len(after), after, s=58, color=ORANGE, zorder=3)
    for artist, name, column in (
        (before_points, "before-observations", "before"),
        (after_points, "after-observations", "after"),
    ):
        bind_artist(
            artist,
            semantic_id=name,
            row_ids=[row["participant"] for row in rows],
            columns=[column],
            role="raw observations",
        )
    for position, value, name in (
        (0, median(before), "before-median"),
        (1, median(after), "after-median"),
    ):
        marker = axes.plot(
            [position - 0.13, position + 0.13],
            [value, value],
            color=INK,
            linewidth=3.2,
        )[0]
        bind_artist(marker, semantic_id=name, role="median")
    label = axes.text(0.5, 65.2, display_text, ha="center", va="bottom", fontsize=11)
    bind_artist(
        label,
        semantic_id="wilcoxon-p-value",
        statistic_id=STATISTIC_ID,
        formatter_id="p_equals_4dp/v1",
        role="statistical annotation",
    )
    axes.set(
        title="Paired improvement after intervention",
        ylabel="Response (arbitrary units)",
        xlim=(-0.35, 1.35),
        ylim=(39, 67),
    )
    axes.set_xticks([0, 1], ["Before", "After"])
    axes.spines[["top", "right", "bottom"]].set_visible(False)
    axes.tick_params(axis="x", length=0)
    figure.tight_layout()

    record = save_figure(
        figure,
        bundle / "fig" / "paired-change.svg",
        data=rows,
        sources=source,
        statistics=[statistic],
        statistical_specifications=[specification],
        title=CLAIM,
        claim=CLAIM,
        grammar="paired slope plot",
        analysis={"input_kind": "plain CSV"},
        reproduction=True,
        proof=True,
        savefig_kwargs={"transparent": True, "bbox_inches": "tight"},
    )
    save_figure(
        figure,
        bundle / "fig" / "preview.png",
        record=record,
        proof=True,
        dpi=200,
        savefig_kwargs={"facecolor": "white", "bbox_inches": "tight"},
    )
    plt.close(figure)


if __name__ == "__main__":
    main()
