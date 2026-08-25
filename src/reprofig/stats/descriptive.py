"""Reference descriptive statistics."""

from __future__ import annotations

import math
from statistics import mean
from typing import Any, Sequence


def _clean(values: Sequence[Any], missing_policy: str) -> tuple[list[float], int]:
    clean: list[float] = []
    missing = 0
    for value in values:
        if value is None or (isinstance(value, float) and math.isnan(value)):
            missing += 1
            if missing_policy == "raise":
                raise ValueError("missing value encountered")
            continue
        clean.append(float(value))
    return clean, missing


def descriptive_statistics(
    values: Sequence[Any],
    *,
    confidence_level: float = 0.95,
    missing_policy: str = "omit",
) -> dict[str, Any]:
    clean, missing = _clean(values, missing_policy)
    n = len(clean)
    if not n:
        raise ValueError("descriptive statistics require at least one value")
    average = mean(clean)
    variance = sum((value - average) ** 2 for value in clean) / (n - 1) if n > 1 else math.nan
    standard_deviation = math.sqrt(variance) if n > 1 else math.nan
    standard_error = standard_deviation / math.sqrt(n) if n > 1 else math.nan
    ci_low = ci_high = math.nan
    if n > 1:
        try:
            from scipy.stats import t as student_t
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("independent statistics require reprofig[proof]") from exc
        critical = float(student_t.ppf((1 + confidence_level) / 2, n - 1))
        ci_low = average - critical * standard_error
        ci_high = average + critical * standard_error
    return {
        "n": n,
        "n_missing": missing,
        "mean": average,
        "variance": variance,
        "standard_deviation": standard_deviation,
        "standard_error": standard_error,
        "confidence_level": confidence_level,
        "ci_low": ci_low,
        "ci_high": ci_high,
    }


__all__ = ["descriptive_statistics"]
