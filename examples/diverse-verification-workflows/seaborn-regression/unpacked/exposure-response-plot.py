"""Draw and package one regression example with Seaborn."""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import linregress, t

from reprofig import (
    StatisticalSpecification,
    attach_evidence_graph,
    bind_artist,
    build_record,
    save_figure,
    source_reference,
    table_from_data,
)

CLAIM = "Response increases with exposure in this synthetic dataset."
GRAMMAR = "scatter regression plot"
STATISTIC_ID = "exposure-response-ols"
FIGURE_NAME = "exposure-response.svg"
BLUE = "#4878A8"
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
        writer = csv.DictWriter(handle, fieldnames=["sample", "exposure", "response"], lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    bundle = Path(__file__).resolve().parents[1]
    source = bundle / "data" / "src" / "regression.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    exposure = [float(row["exposure"]) for row in rows]
    response = [float(row["response"]) for row in rows]
    fitted = linregress(exposure, response)
    degrees_of_freedom = len(rows) - 2
    critical = float(t.ppf(0.975, degrees_of_freedom))
    intercept_t = float(fitted.intercept / fitted.intercept_stderr)
    intercept_p = float(2 * t.sf(abs(intercept_t), degrees_of_freedom))
    expected = {
        "n": len(rows),
        "df_residual": degrees_of_freedom,
        "coefficients": {
            "intercept": {
                "estimate": float(fitted.intercept),
                "standard_error": float(fitted.intercept_stderr),
                "statistic": intercept_t,
                "p_value": intercept_p,
                "ci_low": float(fitted.intercept - critical * fitted.intercept_stderr),
                "ci_high": float(fitted.intercept + critical * fitted.intercept_stderr),
            },
            "slope": {
                "estimate": float(fitted.slope),
                "standard_error": float(fitted.stderr),
                "statistic": float(fitted.slope / fitted.stderr),
                "p_value": float(fitted.pvalue),
                "ci_low": float(fitted.slope - critical * fitted.stderr),
                "ci_high": float(fitted.slope + critical * fitted.stderr),
            },
        },
    }
    display_format = "p_threshold_0.001/v1" if fitted.pvalue < 0.001 else "p_equals_4dp/v1"
    display_text = "p < 0.001" if fitted.pvalue < 0.001 else f"p = {fitted.pvalue:.4f}"
    specification = StatisticalSpecification(
        statistic_id=STATISTIC_ID,
        algorithm_id="ols/v1",
        inputs={"design_matrix": [[1.0, value] for value in exposure], "outcome": response},
        parameters={
            "coefficient_names": ["intercept", "slope"],
            "confidence_level": 0.95,
            "covariance": "classical",
            "missing_policy": "complete_rows",
            "rank_tolerance": 1e-12,
            "producer_implementation": "scipy.stats.linregress/1",
        },
        expected=expected,
        display={},
        tolerances={"*": {"absolute": 1e-10, "relative": 1e-9}},
    )
    statistic = {
        "statistic_id": STATISTIC_ID,
        "test_name": "ordinary least-squares regression",
        "coefficient": "exposure slope",
        "n": len(rows),
        "estimate": float(fitted.slope),
        "standard_error": float(fitted.stderr),
        "confidence_interval_low": expected["coefficients"]["slope"]["ci_low"],
        "confidence_interval_high": expected["coefficients"]["slope"]["ci_high"],
        "statistic": expected["coefficients"]["slope"]["statistic"],
        "degrees_of_freedom": degrees_of_freedom,
        "p_value": float(fitted.pvalue),
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
    sns.set_theme(
        context="notebook",
        style="ticks",
        rc={
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
            "font.size": 13,
            "svg.fonttype": "none",
            "axes.linewidth": 1.8,
            "axes.labelsize": 15,
            "axes.titlesize": 17,
            "axes.titleweight": "bold",
            "xtick.labelsize": 12,
            "ytick.labelsize": 12,
        },
    )
    plt.rcParams["svg.hashsalt"] = "reprofig-seaborn-regression-example"
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    sns.regplot(
        x=exposure,
        y=response,
        ci=None,
        color=BLUE,
        scatter_kws={"s": 58, "alpha": 0.85, "edgecolor": "white"},
        line_kws={"linewidth": 2.8},
        ax=ax,
    )
    points = ax.collections[0]
    line = ax.lines[0]
    bind_artist(points, semantic_id="observations", table_id=table_id, row_ids=[row["sample"] for row in rows], columns=["exposure", "response"], role="raw observations")
    bind_artist(line, semantic_id="ols-fit", table_id=table_id, row_ids=[row["sample"] for row in rows], columns=["exposure", "response"], statistic_id=STATISTIC_ID, role="fitted regression")
    label = ax.text(1.25, 10.2, f"Slope = {fitted.slope:.2f}\n{display_text}", ha="left", va="top", fontsize=11, color=INK)
    bind_artist(label, semantic_id="ols-result", statistic_id=STATISTIC_ID, formatter_id=display_format, connected_mark_ids=["ols-fit"], role="statistical annotation")
    ax.set_title("Exposure predicts response", pad=12)
    ax.set_xlabel("Exposure (arbitrary units)")
    ax.set_ylabel("Response (arbitrary units)")
    ax.set_xlim(0.6, 8.4)
    ax.set_ylim(1.6, 11.0)
    sns.despine(ax=ax)
    ax.tick_params(width=1.8)
    fig.tight_layout()

    producer_source = Path(__file__).read_text(encoding="utf-8")
    record = build_record(
        title=CLAIM,
        original_stem="exposure-response",
        producer={"package": "seaborn", "package_version": importlib.metadata.version("seaborn"), "function": "code/plot.py"},
        analysis={"claim": CLAIM, "grammar": GRAMMAR, "input_kind": "plain CSV"},
        data_tables=[plotted_table],
        statistics=[statistic],
        sources=[source_reference(source, role="raw_user_input", project_root=bundle, source_id="regression-source")],
        reproduction={
            "command": "python code/plot.py",
            "script": producer_source,
            "producer": "code/plot.py",
            "producer_language": "python",
            "producer_sha256": _sha256(Path(__file__)),
            "working_directory": ".",
            "output": f"fig/{FIGURE_NAME}",
            "input": "data/src/regression.csv",
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
