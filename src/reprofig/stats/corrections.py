"""Complete-family multiple-comparison corrections."""

from __future__ import annotations

from typing import Sequence


def bonferroni(values: Sequence[float]) -> list[float]:
    count = len(values)
    return [min(1.0, float(value) * count) for value in values]


def holm(values: Sequence[float]) -> list[float]:
    count = len(values)
    order = sorted(range(count), key=lambda index: (float(values[index]), index))
    adjusted = [0.0] * count
    running = 0.0
    for rank, index in enumerate(order):
        running = max(running, min(1.0, (count - rank) * float(values[index])))
        adjusted[index] = running
    return adjusted


def benjamini_hochberg(values: Sequence[float]) -> list[float]:
    count = len(values)
    order = sorted(range(count), key=lambda index: (float(values[index]), index), reverse=True)
    adjusted = [0.0] * count
    running = 1.0
    for reverse_rank, index in enumerate(order):
        rank = count - reverse_rank
        running = min(running, float(values[index]) * count / rank)
        adjusted[index] = min(1.0, running)
    return adjusted


CORRECTIONS = {"bonferroni/v1": bonferroni, "holm/v1": holm, "benjamini-hochberg/v1": benjamini_hochberg}


def correct(values: Sequence[float], method: str) -> list[float]:
    if method not in CORRECTIONS:
        raise ValueError(f"unsupported correction {method!r}")
    return CORRECTIONS[method](values)


__all__ = ["benjamini_hochberg", "bonferroni", "correct", "holm"]
