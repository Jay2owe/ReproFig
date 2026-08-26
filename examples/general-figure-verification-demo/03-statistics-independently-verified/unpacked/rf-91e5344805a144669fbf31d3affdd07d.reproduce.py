"""Plot raw user observations and hand them directly to ReproFig.

Run this file from any verification-layer folder. It performs no prerequisite
analysis and uses no analysis dependency beyond ReproFig itself. For the
independent layer, a small Python-standard-library Welch calculation supplies
the declared result and ReproFig checks it through its reference route.
"""

from __future__ import annotations

import csv
import hashlib
import importlib.metadata
import json
import math
from pathlib import Path

import matplotlib.pyplot as plt

from reprofig import (
    StatisticalSpecification,
    attach_evidence_graph,
    bind_artist,
    build_record,
    save_figure,
    source_reference,
    table_from_data,
)
from reprofig.stats.engine import calculate_specification
from reprofig.stats.engine import VERIFIER_IMPLEMENTATION

COLORS = {"blue": "#4878A8", "orange": "#d98a17", "dark": "#303030"}


def apply() -> None:
    """Apply the complete local style so the embedded producer is standalone."""

    plt.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": ["Arial", "Helvetica", "Liberation Sans", "DejaVu Sans"],
            "font.size": 16,
            "svg.fonttype": "none",
            "axes.linewidth": 2,
            "axes.labelsize": 22,
            "axes.titlesize": 20,
            "axes.titleweight": "bold",
            "xtick.major.width": 2,
            "ytick.major.width": 2,
            "xtick.major.size": 11,
            "ytick.major.size": 11,
            "xtick.labelsize": 20,
            "ytick.labelsize": 20,
            "figure.titlesize": 22,
            "figure.titleweight": "bold",
            "figure.dpi": 110,
            "legend.frameon": False,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.1,
        }
    )


def finish(*axes) -> None:
    for axis in axes:
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        axis.tick_params(width=2)


CLAIM = "In a small synthetic dataset, treatment observations are higher than control observations."
GRAMMAR = "dot/interval plot"
STATISTIC_ID = "welch-treatment-vs-control"
LAYER_LABELS = {
    "00-traceable-carrier": (0, "Traceable carrier"),
    "01-internally-consistent": (1, "Internally consistent"),
    "02-statistics-reproduced": (2, "Statistics reproduced"),
    "03-statistics-independently-verified": (3, "Statistics independently verified"),
    "04-figure-reproduced": (4, "Figure reproduced"),
    "05-display-verified": (5, "Display verified"),
    "06-source-linked": (6, "Source linked"),
    "07-signature-valid": (7, "Signature valid"),
    "08-signer-trusted": (8, "Signer trusted"),
    "09-attested": (9, "Attested full stack"),
}


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_table(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["observation_id", "group", "response"],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerows(rows)


def _beta_continued_fraction(a: float, b: float, x: float) -> float:
    """Evaluate the incomplete-beta continued fraction without SciPy."""

    maximum_iterations = 300
    epsilon = 3e-14
    minimum = 1e-300
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    d = minimum if abs(d) < minimum else d
    d = 1.0 / d
    result = d
    for iteration in range(1, maximum_iterations + 1):
        twice = 2 * iteration
        coefficient = iteration * (b - iteration) * x / (
            (qam + twice) * (a + twice)
        )
        d = 1.0 + coefficient * d
        d = minimum if abs(d) < minimum else d
        c = 1.0 + coefficient / c
        c = minimum if abs(c) < minimum else c
        d = 1.0 / d
        result *= d * c
        coefficient = -(
            (a + iteration)
            * (qab + iteration)
            * x
            / ((a + twice) * (qap + twice))
        )
        d = 1.0 + coefficient * d
        d = minimum if abs(d) < minimum else d
        c = 1.0 + coefficient / c
        c = minimum if abs(c) < minimum else c
        d = 1.0 / d
        change = d * c
        result *= change
        if abs(change - 1.0) < epsilon:
            return result
    raise ArithmeticError("incomplete-beta continued fraction did not converge")


def _regularized_beta(x: float, a: float, b: float) -> float:
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    front = math.exp(
        math.lgamma(a + b)
        - math.lgamma(a)
        - math.lgamma(b)
        + a * math.log(x)
        + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return front * _beta_continued_fraction(a, b, x) / a
    return 1.0 - front * _beta_continued_fraction(b, a, 1.0 - x) / b


def _student_t_cdf(value: float, degrees_of_freedom: float) -> float:
    beta = _regularized_beta(
        degrees_of_freedom / (degrees_of_freedom + value * value),
        degrees_of_freedom / 2.0,
        0.5,
    )
    return 1.0 - beta / 2.0 if value >= 0.0 else beta / 2.0


def _student_t_quantile(probability: float, degrees_of_freedom: float) -> float:
    lower, upper = -50.0, 50.0
    for _ in range(180):
        midpoint = (lower + upper) / 2.0
        if _student_t_cdf(midpoint, degrees_of_freedom) < probability:
            lower = midpoint
        else:
            upper = midpoint
    return (lower + upper) / 2.0


def _standalone_welch(values_a: list[float], values_b: list[float]) -> dict[str, object]:
    """A dependency-free producer calculation, separate from ReproFig's route."""

    n_a, n_b = len(values_a), len(values_b)
    mean_a = math.fsum(values_a) / n_a
    mean_b = math.fsum(values_b) / n_b
    variance_a = math.fsum((value - mean_a) ** 2 for value in values_a) / (n_a - 1)
    variance_b = math.fsum((value - mean_b) ** 2 for value in values_b) / (n_b - 1)
    component_a = variance_a / n_a
    component_b = variance_b / n_b
    standard_error = math.sqrt(component_a + component_b)
    degrees_of_freedom = (component_a + component_b) ** 2 / (
        component_a**2 / (n_a - 1) + component_b**2 / (n_b - 1)
    )
    difference = mean_a - mean_b
    statistic = difference / standard_error
    p_value = 2.0 * min(
        _student_t_cdf(statistic, degrees_of_freedom),
        1.0 - _student_t_cdf(statistic, degrees_of_freedom),
    )
    critical = _student_t_quantile(0.975, degrees_of_freedom)
    return {
        "n_a": n_a,
        "n_b": n_b,
        "mean_a": mean_a,
        "mean_b": mean_b,
        "variance_a": variance_a,
        "variance_b": variance_b,
        "mean_difference": difference,
        "standard_error": standard_error,
        "pooled_variance": None,
        "statistic": statistic,
        "df": degrees_of_freedom,
        "p_value": p_value,
        "alternative": "two_sided",
        "confidence_level": 0.95,
        "ci_low": difference - critical * standard_error,
        "ci_high": difference + critical * standard_error,
    }


def _statistics(
    rows: list[dict[str, str]], *, verification_route: str | None
) -> tuple[dict[str, object], StatisticalSpecification]:
    values = {
        group: [float(row["response"]) for row in rows if row["group"] == group]
        for group in ("Control", "Treatment")
    }
    parameters = {
        "alternative": "two_sided",
        "missing_policy": "omit",
        "confidence_level": 0.95,
    }
    producer_implementation = (
        VERIFIER_IMPLEMENTATION
        if verification_route == "reproduced"
        else "python-stdlib-welch/1"
    )
    draft = StatisticalSpecification(
        statistic_id=STATISTIC_ID,
        algorithm_id="welch-t/v1",
        inputs={"values_a": values["Control"], "values_b": values["Treatment"]},
        parameters={**parameters, "producer_implementation": producer_implementation},
        expected={},
    )
    expected = (
        calculate_specification(draft)
        if verification_route == "reproduced"
        else _standalone_welch(values["Control"], values["Treatment"])
    )
    if expected["p_value"] < 0.001:
        display_format = "p_threshold_0.001/v1"
        display_text = "p < 0.001"
    else:
        display_format = "p_equals_4dp/v1"
        display_text = f"p = {expected['p_value']:.4f}"
    specification = StatisticalSpecification(
        statistic_id=STATISTIC_ID,
        algorithm_id="welch-t/v1",
        inputs=draft.inputs,
        parameters=draft.parameters,
        expected=expected,
        display={
            "field": "p_value",
            "format": display_format,
            "text": display_text,
        },
        tolerances={"*": {"absolute": 1e-12, "relative": 1e-10}},
    )
    record = {
        "statistic_id": STATISTIC_ID,
        "test_name": "Welch independent-samples t-test",
        "group_a": "Control",
        "group_b": "Treatment",
        "n_a": expected["n_a"],
        "n_b": expected["n_b"],
        "mean_a": expected["mean_a"],
        "mean_b": expected["mean_b"],
        "estimate": expected["mean_difference"],
        "confidence_interval_low": expected["ci_low"],
        "confidence_interval_high": expected["ci_high"],
        "statistic": expected["statistic"],
        "degrees_of_freedom": expected["df"],
        "p_value": expected["p_value"],
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
    return record, specification


def _write_statistics(path: Path, record: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(record), lineterminator="\n")
        writer.writeheader()
        writer.writerow(record)


def main() -> None:
    bundle = Path(__file__).resolve().parents[1]
    level = bundle.name
    if level not in LAYER_LABELS:
        raise ValueError(f"unrecognized verification layer: {level}")
    layer_number, layer_label = LAYER_LABELS[level]
    proof = level != "00-traceable-carrier"
    verification_route = None
    if level == "02-statistics-reproduced":
        verification_route = "reproduced"
    elif level in {"03-statistics-independently-verified", "09-attested"}:
        verification_route = "independent"
    source = bundle / "data" / "src" / "raw-observations.csv"
    with source.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if {row["group"] for row in rows} != {"Control", "Treatment"}:
        raise ValueError("raw input must contain Control and Treatment groups")

    figure_data = bundle / "data" / "der" / "figure_data.csv"
    _write_table(figure_data, rows)
    statistic, specification = _statistics(
        rows, verification_route=verification_route
    )
    _write_statistics(bundle / "data" / "der" / "statistics.csv", statistic)
    plotted_table = table_from_data(
        figure_data.read_bytes(), name="figure_data", purpose="plot_and_statistics"
    )
    table_id = f"table:{plotted_table.sha256}"

    apply()
    plt.rcParams["svg.hashsalt"] = "reprofig-general-verification-demo"
    fig, ax = plt.subplots(figsize=(5.6, 5.2))
    groups = ("Control", "Treatment")
    colors = (COLORS["blue"], COLORS["orange"])
    for position, (group, color) in enumerate(zip(groups, colors)):
        members = [row for row in rows if row["group"] == group]
        offsets = [-0.16, -0.10, -0.04, 0.04, 0.10, 0.16]
        points = ax.scatter(
            [position + offset for offset in offsets],
            [float(row["response"]) for row in members],
            s=62,
            color=color,
            edgecolor="black",
            linewidth=0.8,
            zorder=3,
        )
        bind_artist(
            points,
            semantic_id=f"{group.lower()}-observations",
            table_id=table_id,
            row_ids=[row["observation_id"] for row in members],
            columns=["group", "response"],
            role="raw observations",
        )
        mean = sum(float(row["response"]) for row in members) / len(members)
        mean_line = ax.plot(
            [position - 0.22, position + 0.22],
            [mean, mean],
            color="black",
            linewidth=3,
            solid_capstyle="round",
            zorder=4,
        )[0]
        bind_artist(
            mean_line,
            semantic_id=f"{group.lower()}-mean",
            table_id=table_id,
            row_ids=[row["observation_id"] for row in members],
            columns=["response"],
            role="arithmetic mean",
        )

    bracket = ax.plot([0, 0, 1, 1], [6.72, 6.82, 6.82, 6.72], color="black", linewidth=1.8)[0]
    bind_artist(
        bracket,
        semantic_id="group-comparison-bracket",
        statistic_id=STATISTIC_ID,
        connected_mark_ids=["control-observations", "treatment-observations"],
        role="comparison",
    )
    label = ax.text(
        0.5,
        6.87,
        specification.display["text"],
        ha="center",
        va="bottom",
        fontsize=11,
    )
    bind_artist(
        label,
        semantic_id="welch-p-value",
        statistic_id=STATISTIC_ID,
        connected_mark_ids=["group-comparison-bracket"],
        formatter_id=specification.display["format"],
        role="statistical annotation",
    )
    ax.set_xticks([0, 1], groups)
    ax.set_ylabel("Response (arbitrary units)")
    ax.set_title("Raw user input carried with the figure", pad=14)
    ax.set_xlim(-0.45, 1.45)
    ax.set_ylim(4.5, 7.08)
    ax.text(
        0.02,
        0.02,
        "Dots: entered values   Black lines: means",
        transform=ax.transAxes,
        fontsize=9,
        color=COLORS["dark"],
    )
    finish(ax)
    fig.suptitle(
        f"Layer {layer_number} of 9 · {layer_label}",
        y=0.995,
        fontsize=14,
        fontweight="bold",
    )
    fig.tight_layout(rect=(0, 0, 1, 0.95))

    producer_source = Path(__file__).read_text(encoding="utf-8")
    record = build_record(
        title=CLAIM,
        original_stem="raw-user-input-comparison",
        producer={
            "package": "matplotlib",
            "package_version": importlib.metadata.version("matplotlib"),
            "function": "code/plot.py",
        },
        analysis={"claim": CLAIM, "grammar": GRAMMAR, "input_kind": "plain CSV"},
        data_tables=[plotted_table],
        statistics=[statistic],
        sources=[
            source_reference(
                source,
                role="raw_user_input",
                project_root=bundle,
                source_id="raw-observations",
            )
        ],
        reproduction={
            "command": "python code/plot.py",
            "script": producer_source,
            "working_directory": ".",
            "input": "data/src/raw-observations.csv",
            "bundle_layout": "plot-that/2",
            "producer": "code/plot.py",
            "producer_language": "py",
            "producer_sha256": _sha256(Path(__file__)),
            "exact_table": "data/der/figure_data.csv",
            "exact_table_sha256": _sha256(figure_data),
            "source_index": "data/sources.csv",
            "source_index_sha256": _sha256(bundle / "data" / "sources.csv"),
            "readme": "README.md",
            "readme_sha256": _sha256(bundle / "README.md"),
        },
        data_status="complete",
        statistics_status="complete",
    )
    if proof:
        record.extensions["proof"] = {
            "statistical_specifications": [specification.to_dict()]
        }
    record = attach_evidence_graph(record)
    record = save_figure(
        fig,
        bundle / "fig" / "raw-user-input-comparison.svg",
        record=record,
        proof=proof,
        savefig_kwargs={"transparent": True, "bbox_inches": "tight"},
    )
    save_figure(
        fig,
        bundle / "fig" / "preview.png",
        record=record,
        proof=proof,
        dpi=200,
        savefig_kwargs={"transparent": False, "facecolor": "white", "bbox_inches": "tight"},
    )
    plt.close(fig)


if __name__ == "__main__":
    main()
