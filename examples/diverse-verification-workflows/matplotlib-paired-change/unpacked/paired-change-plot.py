"""Draw and package one paired-change example with Matplotlib."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
from statistics import median

import matplotlib.pyplot as plt
from scipy.stats import wilcoxon

from reprofig import (
    StatisticalSpecification,
    attach_evidence_graph,
    bind_artist,
    build_record,
    save_figure,
    source_reference,
    table_from_data,
)

CLAIM = "Paired responses are higher after the intervention in this synthetic dataset."
GRAMMAR = "paired slope plot"
STATISTIC_ID = "paired-change-wilcoxon"
FIGURE_NAME = "paired-change.svg"
BLUE = "#4878A8"
ORANGE = "#d98a17"
GREY = "#c7c7c7"
INK = "#303030"


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
        writer = csv.DictWriter(handle, fieldnames=["participant", "before", "after"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def _style() -> None:
    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
            "font.size": 13,
            "svg.fonttype": "none",
            "axes.linewidth": 1.8,
            "axes.labelsize": 15,
            "axes.titlesize": 17,
            "axes.titleweight": "bold",
            "xtick.labelsize": 13,
            "ytick.labelsize": 12,
            "xtick.major.width": 1.8,
            "ytick.major.width": 1.8,
            "legend.frameon": False,
            "figure.dpi": 110,
        }
    )


def main() -> None:
    bundle = Path(__file__).resolve().parents[1]
    source = bundle / "data" / "src" / "paired-change.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    before = [float(row["before"]) for row in rows]
    after = [float(row["after"]) for row in rows]
    differences = [right - left for left, right in zip(before, after)]
    result = wilcoxon(
        differences,
        alternative="two-sided",
        zero_method="wilcox",
        correction=False,
        method="auto",
    )
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
            "producer_implementation": "scipy.stats.wilcoxon/1",
        },
        expected={"statistic": float(result.statistic), "p_value": p_value},
        display={"field": "p_value", "format": "p_equals_4dp/v1", "text": f"p = {p_value:.4f}"},
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
    _style()
    plt.rcParams["svg.hashsalt"] = "reprofig-paired-change-example"
    fig, ax = plt.subplots(figsize=(5.2, 5.0))
    for row, left, right in zip(rows, before, after):
        pair = ax.plot([0, 1], [left, right], color=GREY, linewidth=1.5, zorder=1)[0]
        bind_artist(
            pair,
            semantic_id=f"pair-{row['participant']}",
            table_id=table_id,
            row_ids=[row["participant"]],
            columns=["before", "after"],
            role="paired trajectory",
        )
    before_points = ax.scatter([0] * len(before), before, s=58, color=BLUE, edgecolor="white", linewidth=0.8, zorder=3)
    after_points = ax.scatter([1] * len(after), after, s=58, color=ORANGE, edgecolor="white", linewidth=0.8, zorder=3)
    bind_artist(before_points, semantic_id="before-observations", table_id=table_id, row_ids=[row["participant"] for row in rows], columns=["before"], role="raw observations")
    bind_artist(after_points, semantic_id="after-observations", table_id=table_id, row_ids=[row["participant"] for row in rows], columns=["after"], role="raw observations")
    for position, value, name in ((0, median(before), "before-median"), (1, median(after), "after-median")):
        marker = ax.plot([position - 0.13, position + 0.13], [value, value], color=INK, linewidth=3.2, solid_capstyle="round", zorder=4)[0]
        bind_artist(marker, semantic_id=name, table_id=table_id, columns=[name.split("-")[0]], role="median")
    label = ax.text(0.5, 65.2, display_text, ha="center", va="bottom", fontsize=11, color=INK)
    bind_artist(label, semantic_id="wilcoxon-p-value", statistic_id=STATISTIC_ID, formatter_id="p_equals_4dp/v1", role="statistical annotation")
    ax.set_title("Paired improvement after intervention", pad=12)
    ax.set_ylabel("Response (arbitrary units)")
    ax.set_xticks([0, 1], ["Before", "After"])
    ax.set_xlim(-0.35, 1.35)
    ax.set_ylim(39, 67)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)
    ax.spines["bottom"].set_visible(False)
    ax.tick_params(axis="x", length=0)
    fig.tight_layout()

    producer_source = Path(__file__).read_text(encoding="utf-8")
    record = build_record(
        title=CLAIM,
        original_stem="paired-change",
        producer={"package": "matplotlib", "package_version": importlib.metadata.version("matplotlib"), "function": "code/plot.py"},
        analysis={"claim": CLAIM, "grammar": GRAMMAR, "input_kind": "plain CSV"},
        data_tables=[plotted_table],
        statistics=[statistic],
        sources=[source_reference(source, role="raw_user_input", project_root=bundle, source_id="paired-change-source")],
        reproduction={
            "command": "python code/plot.py",
            "script": producer_source,
            "producer": "code/plot.py",
            "producer_language": "python",
            "producer_sha256": _sha256(Path(__file__)),
            "working_directory": ".",
            "output": f"fig/{FIGURE_NAME}",
            "input": "data/src/paired-change.csv",
            "exact_table": "data/der/figure_data.csv",
            "exact_table_sha256": _sha256(figure_data),
            "source_index": "data/sources.csv",
            "source_index_sha256": _sha256(bundle / "data" / "sources.csv"),
            "readme": "README.md",
            "readme_sha256": _sha256(bundle / "README.md"),
        },
        data_status="complete",
        statistics_status="complete",
        extensions={"proof": {"statistical_specifications": [specification.to_dict()]}},
    )
    record = attach_evidence_graph(record)
    record = save_figure(fig, bundle / "fig" / FIGURE_NAME, record=record, proof=True, savefig_kwargs={"transparent": True, "bbox_inches": "tight"})
    save_figure(fig, bundle / "fig" / "preview.png", record=record, proof=True, dpi=200, savefig_kwargs={"transparent": False, "facecolor": "white", "bbox_inches": "tight"})
    plt.close(fig)


if __name__ == "__main__":
    main()
