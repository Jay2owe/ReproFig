"""Reference ordinary least-squares regression from a frozen design matrix."""

from __future__ import annotations

from typing import Any, Sequence


def ordinary_least_squares(
    design_matrix: Sequence[Sequence[Any]],
    outcome: Sequence[Any],
    *,
    coefficient_names: Sequence[str] | None = None,
    confidence_level: float = 0.95,
    contrasts: Sequence[Sequence[Any]] | None = None,
    rank_tolerance: float | None = None,
) -> dict[str, Any]:
    import numpy as np
    from scipy.stats import t
    x = np.asarray(design_matrix, dtype=float)
    y = np.asarray(outcome, dtype=float)
    if x.ndim != 2 or y.ndim != 1 or x.shape[0] != y.shape[0]:
        raise ValueError("design matrix and outcome dimensions do not agree")
    if x.shape[0] > 2_000_000 or x.shape[1] > 10_000:
        raise ValueError("ordinary least-squares input exceeds resource limits")
    if not np.isfinite(x).all() or not np.isfinite(y).all():
        raise ValueError("ordinary least-squares complete_rows input must be finite")
    rank = int(np.linalg.matrix_rank(x, tol=rank_tolerance))
    if rank != x.shape[1]:
        raise ValueError("design matrix is rank deficient")
    xtx_inverse = np.linalg.inv(x.T @ x)
    coefficients = xtx_inverse @ x.T @ y
    residuals = y - x @ coefficients
    df = int(x.shape[0] - x.shape[1])
    if df <= 0:
        raise ValueError("ordinary least-squares requires positive residual degrees of freedom")
    residual_variance = float((residuals @ residuals) / df)
    covariance = residual_variance * xtx_inverse
    standard_errors = np.sqrt(np.diag(covariance))
    statistics = coefficients / standard_errors
    p_values = 2 * t.sf(np.abs(statistics), df)
    critical = float(t.ppf((1 + confidence_level) / 2, df))
    names = list(coefficient_names or [f"x{index}" for index in range(x.shape[1])])
    if len(names) != x.shape[1]:
        raise ValueError("coefficient_names length does not match design columns")
    result: dict[str, Any] = {
        "n": int(x.shape[0]), "rank": rank, "df_residual": df,
        "residual_variance": residual_variance,
        "rank_tolerance": rank_tolerance,
        "coefficients": {
            name: {
                "estimate": float(coefficients[index]),
                "standard_error": float(standard_errors[index]),
                "statistic": float(statistics[index]),
                "p_value": float(p_values[index]),
                "ci_low": float(coefficients[index] - critical * standard_errors[index]),
                "ci_high": float(coefficients[index] + critical * standard_errors[index]),
            }
            for index, name in enumerate(names)
        },
        "residual_sum_squares": float(residuals @ residuals),
        "confidence_level": confidence_level,
    }
    if contrasts:
        contrast_results = []
        for weights_value in contrasts:
            weights = np.asarray(weights_value, dtype=float)
            if weights.shape != coefficients.shape:
                raise ValueError("contrast length does not match coefficients")
            estimate = float(weights @ coefficients)
            standard_error = float(np.sqrt(weights @ covariance @ weights))
            statistic = estimate / standard_error
            contrast_results.append({
                "weights": weights.tolist(), "estimate": estimate,
                "standard_error": standard_error, "statistic": statistic,
                "p_value": float(2 * t.sf(abs(statistic), df)),
                "ci_low": estimate - critical * standard_error,
                "ci_high": estimate + critical * standard_error,
            })
        result["contrasts"] = contrast_results
    return result


__all__ = ["ordinary_least_squares"]
