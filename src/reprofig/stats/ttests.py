"""Reference one-sample, paired, Student and Welch t-tests."""

from __future__ import annotations

import math
from typing import Any, Sequence

from .descriptive import descriptive_statistics


def _pvalue(statistic: float, degrees_of_freedom: float, alternative: str) -> float:
    try:
        from scipy.stats import t as student_t
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("t-test verification requires reprofig[proof]") from exc
    cdf = float(student_t.cdf(statistic, degrees_of_freedom))
    if alternative in {"two_sided", "two-sided", "two sided"}:
        return 2 * min(cdf, 1 - cdf)
    if alternative in {"greater", "right"}:
        return 1 - cdf
    if alternative in {"less", "left"}:
        return cdf
    raise ValueError(f"unsupported alternative {alternative!r}")


def one_sample_t(
    values: Sequence[Any], *, null_mean: float = 0.0, alternative: str = "two_sided",
    confidence_level: float = 0.95, missing_policy: str = "omit",
) -> dict[str, Any]:
    summary = descriptive_statistics(values, confidence_level=confidence_level, missing_policy=missing_policy)
    if summary["n"] < 2 or summary["standard_error"] == 0:
        raise ValueError("one-sample t-test requires at least two nonconstant observations")
    statistic = (summary["mean"] - float(null_mean)) / summary["standard_error"]
    df = summary["n"] - 1
    return {**summary, "null_mean": float(null_mean), "statistic": statistic, "df": df, "p_value": _pvalue(statistic, df, alternative), "alternative": alternative}


def paired_t(
    values_a: Sequence[Any], values_b: Sequence[Any], *, alternative: str = "two_sided",
    confidence_level: float = 0.95, missing_policy: str = "omit",
) -> dict[str, Any]:
    if len(values_a) != len(values_b):
        raise ValueError("paired samples must have equal length")
    differences = []
    excluded = 0
    for left, right in zip(values_a, values_b):
        if left is None or right is None:
            excluded += 1
            if missing_policy == "raise":
                raise ValueError("missing pair encountered")
            continue
        differences.append(float(left) - float(right))
    result = one_sample_t(differences, alternative=alternative, confidence_level=confidence_level, missing_policy="raise")
    result.update({"n_pairs": len(differences), "n_excluded": excluded})
    return result


def independent_t(
    values_a: Sequence[Any], values_b: Sequence[Any], *, equal_variance: bool,
    alternative: str = "two_sided", confidence_level: float = 0.95,
    missing_policy: str = "omit",
) -> dict[str, Any]:
    left = descriptive_statistics(values_a, confidence_level=confidence_level, missing_policy=missing_policy)
    right = descriptive_statistics(values_b, confidence_level=confidence_level, missing_policy=missing_policy)
    n_a, n_b = left["n"], right["n"]
    if min(n_a, n_b) < 2:
        raise ValueError("independent t-test requires at least two values per group")
    difference = left["mean"] - right["mean"]
    if equal_variance:
        df = n_a + n_b - 2
        pooled_variance = ((n_a - 1) * left["variance"] + (n_b - 1) * right["variance"]) / df
        standard_error = math.sqrt(pooled_variance * (1 / n_a + 1 / n_b))
    else:
        component_a = left["variance"] / n_a
        component_b = right["variance"] / n_b
        standard_error = math.sqrt(component_a + component_b)
        df = (component_a + component_b) ** 2 / (
            component_a**2 / (n_a - 1) + component_b**2 / (n_b - 1)
        )
        pooled_variance = None
    if standard_error == 0:
        raise ValueError("independent t-test is undefined for zero variance")
    statistic = difference / standard_error
    try:
        from scipy.stats import t as student_t
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("t-test verification requires reprofig[proof]") from exc
    critical = float(student_t.ppf((1 + confidence_level) / 2, df))
    return {
        "n_a": n_a, "n_b": n_b, "mean_a": left["mean"], "mean_b": right["mean"],
        "variance_a": left["variance"], "variance_b": right["variance"],
        "mean_difference": difference, "standard_error": standard_error,
        "pooled_variance": pooled_variance, "statistic": statistic, "df": df,
        "p_value": _pvalue(statistic, df, alternative), "alternative": alternative,
        "confidence_level": confidence_level,
        "ci_low": difference - critical * standard_error,
        "ci_high": difference + critical * standard_error,
    }


__all__ = ["independent_t", "one_sample_t", "paired_t"]
