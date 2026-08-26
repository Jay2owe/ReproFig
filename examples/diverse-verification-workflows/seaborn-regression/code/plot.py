"""Draw one proof-carrying regression figure with Seaborn."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import seaborn as sns
from scipy.stats import linregress, t

from reprofig import StatisticalSpecification, bind_artist, save_figure

CLAIM = "Response increases with exposure in this synthetic dataset."
STATISTIC_ID = "exposure-ordinary-least-squares"
BLUE, INK = "#4878A8", "#303030"


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
    display_format = (
        "p_threshold_0.001/v1" if fitted.pvalue < 0.001 else "p_equals_4dp/v1"
    )
    display_text = "p < 0.001" if fitted.pvalue < 0.001 else f"p = {fitted.pvalue:.4f}"
    specification = StatisticalSpecification(
        statistic_id=STATISTIC_ID,
        algorithm_id="ols/v1",
        inputs={
            "design_matrix": [[1.0, value] for value in exposure],
            "outcome": response,
        },
        parameters={
            "coefficient_names": ["intercept", "slope"],
            "confidence_level": 0.95,
            "covariance": "classical",
            "missing_policy": "complete_rows",
            "rank_tolerance": 1e-12,
        },
        expected=expected,
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
    }

    sns.set_theme(context="notebook", style="ticks", font_scale=1.15)
    plt.rcParams.update(
        {
            "svg.fonttype": "none",
            "svg.hashsalt": "reprofig-seaborn-regression-example",
            "axes.linewidth": 1.8,
            "axes.titlesize": 17,
            "axes.titleweight": "bold",
        }
    )
    figure, axes = plt.subplots(figsize=(5.6, 4.8))
    sns.regplot(
        x=exposure,
        y=response,
        ci=None,
        color=BLUE,
        scatter_kws={"s": 58, "alpha": 0.85, "edgecolor": "white"},
        line_kws={"linewidth": 2.8},
        ax=axes,
    )
    bind_artist(
        axes.collections[0],
        semantic_id="observations",
        row_ids=[row["sample"] for row in rows],
        columns=["exposure", "response"],
        role="raw observations",
    )
    bind_artist(
        axes.lines[0],
        semantic_id="ordinary-least-squares-fit",
        columns=["exposure", "response"],
        statistic_id=STATISTIC_ID,
        role="fitted regression",
    )
    label = axes.text(
        1.25,
        10.2,
        f"Slope = {fitted.slope:.2f}\n{display_text}",
        va="top",
        fontsize=11,
        color=INK,
    )
    bind_artist(
        label,
        semantic_id="ordinary-least-squares-result",
        statistic_id=STATISTIC_ID,
        formatter_id=display_format,
        connected_mark_ids=["ordinary-least-squares-fit"],
        role="statistical annotation",
    )
    axes.set(
        title="Exposure predicts response",
        xlabel="Exposure (arbitrary units)",
        ylabel="Response (arbitrary units)",
        xlim=(0.6, 8.4),
        ylim=(1.6, 11.0),
    )
    sns.despine(ax=axes)
    figure.tight_layout()

    record = save_figure(
        figure,
        bundle / "fig" / "exposure-response.svg",
        data=rows,
        sources=source,
        statistics=[statistic],
        statistical_specifications=[specification],
        title=CLAIM,
        claim=CLAIM,
        grammar="scatter regression plot",
        producer="seaborn",
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
