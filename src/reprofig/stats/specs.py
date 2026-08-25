"""Declarative statistical algorithm and result specifications."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

from ..schema import StatisticalSpecification


@dataclass(frozen=True)
class AlgorithmSpecification:
    algorithm_id: str
    input_roles: tuple[str, ...]
    required_parameters: tuple[str, ...]
    output_fields: tuple[str, ...]
    calculator: Callable[..., dict[str, Any]]
    independent: bool = True
    notes: str = ""


__all__ = ["AlgorithmSpecification", "StatisticalSpecification"]
