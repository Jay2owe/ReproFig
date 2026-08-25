"""Reference rank-based tests with explicit method choices."""

from __future__ import annotations

from typing import Any, Sequence


def mann_whitney(
    values_a: Sequence[Any], values_b: Sequence[Any], *, alternative: str = "two-sided",
    method: str = "auto", continuity: bool = True,
) -> dict[str, Any]:
    from scipy.stats import mannwhitneyu, rankdata
    combined = [float(value) for value in values_a] + [float(value) for value in values_b]
    ranks = [float(value) for value in rankdata(combined, method="average")]
    tie_groups = sorted(
        count for value in set(combined)
        if (count := combined.count(value)) > 1
    )
    result = mannwhitneyu(
        [float(value) for value in values_a], [float(value) for value in values_b],
        alternative=alternative.replace("_", "-"), method=method, use_continuity=continuity,
    )
    return {
        "statistic": float(result.statistic), "p_value": float(result.pvalue),
        "alternative": alternative, "method": method, "continuity": continuity,
        "n_a": len(values_a), "n_b": len(values_b),
        "rank_sum_a": sum(ranks[:len(values_a)]), "tie_group_sizes": tie_groups,
    }


def wilcoxon_signed_rank(
    values_a: Sequence[Any], values_b: Sequence[Any] | None = None, *,
    alternative: str = "two-sided", zero_method: str = "wilcox", correction: bool = False,
    method: str = "auto",
) -> dict[str, Any]:
    from scipy.stats import rankdata, wilcoxon
    left = [float(value) for value in values_a]
    right = None if values_b is None else [float(value) for value in values_b]
    differences = left if right is None else [a - b for a, b in zip(left, right)]
    nonzero = [value for value in differences if value != 0]
    absolute = [abs(value) for value in nonzero]
    ranks = [float(value) for value in rankdata(absolute, method="average")]
    tie_groups = sorted(
        count for value in set(absolute)
        if (count := absolute.count(value)) > 1
    )
    result = wilcoxon(
        left, right,
        alternative=alternative.replace("_", "-"), zero_method=zero_method,
        correction=correction, method=method,
    )
    return {
        "statistic": float(result.statistic), "p_value": float(result.pvalue),
        "alternative": alternative, "zero_method": zero_method,
        "continuity": correction, "method": method, "n": len(values_a),
        "n_zero": len(differences) - len(nonzero),
        "positive_rank_sum": sum(rank for rank, difference in zip(ranks, nonzero) if difference > 0),
        "negative_rank_sum": sum(rank for rank, difference in zip(ranks, nonzero) if difference < 0),
        "tie_group_sizes": tie_groups,
    }


def kruskal_wallis(groups: Sequence[Sequence[Any]], *, nan_policy: str = "omit") -> dict[str, Any]:
    from scipy.stats import kruskal, rankdata
    values = [[float(value) for value in group] for group in groups]
    combined = [value for group in values for value in group]
    ranks = [float(value) for value in rankdata(combined, method="average")]
    rank_sums = []
    offset = 0
    for group in values:
        rank_sums.append(sum(ranks[offset:offset + len(group)]))
        offset += len(group)
    tie_groups = sorted(
        count for value in set(combined)
        if (count := combined.count(value)) > 1
    )
    result = kruskal(*values, nan_policy=nan_policy)
    return {
        "statistic": float(result.statistic), "p_value": float(result.pvalue),
        "df": len(values) - 1, "group_sizes": [len(group) for group in values],
        "rank_sums": rank_sums, "tie_group_sizes": tie_groups,
        "nan_policy": nan_policy,
    }


__all__ = ["kruskal_wallis", "mann_whitney", "wilcoxon_signed_rank"]
