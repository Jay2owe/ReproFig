"""Bounded deterministic bootstrap and permutation reference calculations."""

from __future__ import annotations

import random
from statistics import mean
from typing import Any, Sequence

MAX_ITERATIONS = 1_000_000
MAX_INDEX_VALUES = 20_000_000


def _plan(
    *, size: int, iterations: int, index_plan: Sequence[Sequence[int]] | None,
    random_seed: int | None,
) -> tuple[list[list[int]], str]:
    if iterations < 1 or iterations > MAX_ITERATIONS:
        raise ValueError("resampling iterations exceed limits")
    if index_plan is not None:
        values = [list(map(int, row)) for row in index_plan]
        if len(values) != iterations or sum(map(len, values)) > MAX_INDEX_VALUES:
            raise ValueError("embedded resampling index plan exceeds limits or has wrong length")
        if any(index < 0 or index >= size for row in values for index in row):
            raise ValueError("resampling index plan contains an out-of-range index")
        return values, "embedded-index-plan/v1"
    if random_seed is None:
        raise ValueError("resampling requires an embedded index plan or explicit random_seed")
    generator = random.Random(int(random_seed))
    return [[generator.randrange(size) for _ in range(size)] for _ in range(iterations)], "python-mt19937/v1"


def bootstrap_mean(
    values: Sequence[Any], *, iterations: int,
    index_plan: Sequence[Sequence[int]] | None = None, random_seed: int | None = None,
    confidence_level: float = 0.95,
) -> dict[str, Any]:
    clean = [float(value) for value in values]
    plan, portability = _plan(size=len(clean), iterations=iterations, index_plan=index_plan, random_seed=random_seed)
    estimates = sorted(mean(clean[index] for index in row) for row in plan)
    lower_index = max(0, int(((1 - confidence_level) / 2) * iterations))
    upper_index = min(iterations - 1, int(((1 + confidence_level) / 2) * iterations))
    return {"estimate": mean(clean), "bootstrap_mean": mean(estimates), "ci_low": estimates[lower_index], "ci_high": estimates[upper_index], "confidence_level": confidence_level, "iterations": iterations, "plan_identity": portability}


def permutation_mean_difference(
    values_a: Sequence[Any], values_b: Sequence[Any], *, iterations: int,
    index_plan: Sequence[Sequence[int]] | None = None, random_seed: int | None = None,
    alternative: str = "two_sided",
) -> dict[str, Any]:
    left = [float(value) for value in values_a]
    right = [float(value) for value in values_b]
    combined = left + right
    if index_plan is None:
        if random_seed is None:
            raise ValueError(
                "permutation requires an embedded index plan or explicit random_seed"
            )
        if iterations < 1 or iterations > MAX_ITERATIONS:
            raise ValueError("resampling iterations exceed limits")
        generator = random.Random(int(random_seed))
        plan = []
        for _ in range(iterations):
            row = list(range(len(combined)))
            generator.shuffle(row)
            plan.append(row)
        portability = "python-mt19937/v1"
    else:
        plan, portability = _plan(
            size=len(combined), iterations=iterations,
            index_plan=index_plan, random_seed=random_seed,
        )
    if any(len(row) != len(combined) or len(set(row)) != len(combined) for row in plan):
        raise ValueError("permutation index plan must contain each combined index exactly once")
    observed = mean(left) - mean(right)
    permutations = []
    for row in plan:
        reordered = [combined[index] for index in row]
        permutations.append(mean(reordered[: len(left)]) - mean(reordered[len(left):]))
    if alternative == "two_sided":
        extreme = sum(abs(value) >= abs(observed) for value in permutations)
    elif alternative == "greater":
        extreme = sum(value >= observed for value in permutations)
    elif alternative == "less":
        extreme = sum(value <= observed for value in permutations)
    else:
        raise ValueError(f"unsupported alternative {alternative!r}")
    return {"mean_difference": observed, "p_value": (extreme + 1) / (iterations + 1), "iterations": iterations, "alternative": alternative, "plan_identity": portability}


__all__ = ["bootstrap_mean", "permutation_mean_difference"]
