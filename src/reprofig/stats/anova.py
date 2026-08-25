"""Reference ordinary and Welch one-way analysis of variance."""

from __future__ import annotations

from statistics import mean
from typing import Any, Sequence


def one_way_anova(groups: Sequence[Sequence[Any]]) -> dict[str, Any]:
    values = [[float(value) for value in group] for group in groups]
    if len(values) < 2 or any(len(group) < 1 for group in values):
        raise ValueError("one-way ANOVA requires at least two non-empty groups")
    sizes = [len(group) for group in values]
    means = [mean(group) for group in values]
    total = sum(sizes)
    grand = sum(size * average for size, average in zip(sizes, means)) / total
    between = sum(size * (average - grand) ** 2 for size, average in zip(sizes, means))
    within = sum(sum((value - average) ** 2 for value in group) for group, average in zip(values, means))
    df1 = len(values) - 1
    df2 = total - len(values)
    statistic = (between / df1) / (within / df2)
    from scipy.stats import f
    variances = [
        sum((value - average) ** 2 for value in group) / (len(group) - 1)
        if len(group) > 1 else None
        for group, average in zip(values, means)
    ]
    return {"statistic": statistic, "p_value": float(f.sf(statistic, df1, df2)), "df1": df1, "df2": df2, "group_sizes": sizes, "group_means": means, "group_variances": variances, "sum_squares_between": between, "sum_squares_within": within}


def welch_anova(groups: Sequence[Sequence[Any]]) -> dict[str, Any]:
    values = [[float(value) for value in group] for group in groups]
    if len(values) < 2 or any(len(group) < 2 for group in values):
        raise ValueError("Welch ANOVA requires at least two groups with two observations each")
    sizes = [len(group) for group in values]
    means = [mean(group) for group in values]
    variances = [sum((value - average) ** 2 for value in group) / (len(group) - 1) for group, average in zip(values, means)]
    if any(variance <= 0 for variance in variances):
        raise ValueError("Welch ANOVA requires positive within-group variances")
    weights = [size / variance for size, variance in zip(sizes, variances)]
    weight_sum = sum(weights)
    weighted_mean = sum(weight * average for weight, average in zip(weights, means)) / weight_sum
    k = len(values)
    term = sum((1 / (size - 1)) * (1 - weight / weight_sum) ** 2 for size, weight in zip(sizes, weights))
    numerator = sum(weight * (average - weighted_mean) ** 2 for weight, average in zip(weights, means)) / (k - 1)
    denominator = 1 + (2 * (k - 2) / (k**2 - 1)) * term
    statistic = numerator / denominator
    df1 = k - 1
    df2 = (k**2 - 1) / (3 * term)
    from scipy.stats import f
    return {"statistic": statistic, "p_value": float(f.sf(statistic, df1, df2)), "df1": df1, "df2": df2, "group_sizes": sizes, "group_means": means, "group_variances": variances, "weights": weights}


__all__ = ["one_way_anova", "welch_anova"]
