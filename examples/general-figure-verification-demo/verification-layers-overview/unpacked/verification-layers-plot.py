"""Render the ReproFig verification-layer overview from a plain CSV file."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
from pathlib import Path

import matplotlib.pyplot as plt

from reprofig import build_record, save_figure, source_reference, table_from_data

try:
    from plot_style import COLORS, apply
except ImportError:
    COLORS = {
        "blue": "#4878A8",
        "orange": "#d98a17",
        "teal": "#0e8f8f",
        "dark": "#303030",
    }

    def apply() -> None:
        plt.rcParams.update(
            {
                "font.family": "sans-serif",
                "font.sans-serif": ["Arial", "DejaVu Sans"],
                "svg.fonttype": "none",
            }
        )


CLAIM = (
    "ReproFig separates traceability from nine verification meanings so each "
    "claim can be checked and reported explicitly."
)
GRAMMAR = "timeline"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    bundle = Path(__file__).resolve().parents[1]
    source = bundle / "data" / "src" / "verification-layers.csv"
    derived = bundle / "data" / "der" / "figure_data.csv"
    derived.write_bytes(source.read_bytes())
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))

    apply()
    fig, ax = plt.subplots(figsize=(12.4, 10.1))
    ax.set_xlim(0, 1)
    ax.set_ylim(-0.3, 9.8)
    ax.axis("off")

    ax.text(
        0.0,
        9.65,
        "What each ReproFig verification layer establishes",
        fontsize=20,
        fontweight="bold",
        color=COLORS["dark"],
    )
    ax.text(
        0.0,
        9.28,
        "Each check is explicit and opt-in; statistical and complete-figure reproduction are separate claims.",
        fontsize=10.5,
        color="#5a5a5a",
    )
    ax.text(0.14, 8.86, "Layer", fontsize=10, fontweight="bold", color="#555555")
    ax.text(0.36, 8.86, "What a pass establishes", fontsize=10, fontweight="bold", color="#555555")
    ax.text(0.70, 8.86, "What it does not establish", fontsize=10, fontweight="bold", color="#555555")

    colors = [
        "#777777",
        COLORS["blue"],
        COLORS["teal"],
        COLORS["teal"],
        COLORS["blue"],
        COLORS["orange"],
        "#7b61a8",
        "#c05a47",
        "#a33e56",
        COLORS["dark"],
    ]
    y_positions = [8.35 - index * 0.88 for index in range(len(rows))]
    ax.plot(
        [0.065, 0.065],
        [y_positions[-1], y_positions[0]],
        color="#c7c7c7",
        linewidth=3,
        zorder=0,
    )
    for row, y, color in zip(rows, y_positions, colors):
        ax.scatter([0.065], [y], s=640, color=color, edgecolor="white", linewidth=2, zorder=2)
        ax.text(
            0.065,
            y,
            row["layer"],
            ha="center",
            va="center",
            color="white",
            fontsize=12,
            fontweight="bold",
            zorder=3,
        )
        ax.text(0.14, y, row["label"], va="center", fontsize=11.2, fontweight="bold")
        ax.text(0.36, y, row["check"], va="center", fontsize=9.4, wrap=True)
        ax.text(0.70, y, row["limit"], va="center", fontsize=9.2, color="#555555", wrap=True)
        ax.plot([0.12, 0.98], [y - 0.43, y - 0.43], color="#e5e5e5", linewidth=0.8)

    fig.tight_layout()

    plotted_table = table_from_data(
        derived.read_bytes(), name="figure_data", purpose="verification_layer_overview"
    )
    producer = Path(__file__)
    record = build_record(
        title=CLAIM,
        original_stem="verification-layers",
        producer={
            "package": "matplotlib",
            "package_version": importlib.metadata.version("matplotlib"),
            "function": "code/plot.py",
        },
        analysis={"claim": CLAIM, "grammar": GRAMMAR, "input_kind": "plain CSV"},
        data_tables=[plotted_table],
        sources=[
            source_reference(
                source,
                role="verification_layer_definitions",
                project_root=bundle,
                source_id="verification-layers",
            )
        ],
        reproduction={
            "command": "python code/plot.py",
            "script": producer.read_text(encoding="utf-8"),
            "working_directory": ".",
            "input": "data/src/verification-layers.csv",
            "bundle_layout": "plot-that/2",
            "producer": "code/plot.py",
            "producer_language": "py",
            "producer_sha256": _sha256(producer),
            "exact_table": "data/der/figure_data.csv",
            "exact_table_sha256": _sha256(derived),
            "source_index": "data/sources.csv",
            "source_index_sha256": _sha256(bundle / "data" / "sources.csv"),
            "readme": "README.md",
            "readme_sha256": _sha256(bundle / "README.md"),
        },
        data_status="complete",
        statistics_status="not_applicable",
    )
    record = save_figure(
        fig,
        bundle / "fig" / "verification-layers.svg",
        record=record,
        savefig_kwargs={"transparent": True, "bbox_inches": "tight"},
    )
    save_figure(
        fig,
        bundle / "fig" / "preview.png",
        record=record,
        dpi=180,
        savefig_kwargs={"transparent": False, "facecolor": "white", "bbox_inches": "tight"},
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
