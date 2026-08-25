"""Independent, versioned statistical verification."""

from .engine import calculate_specification, verify_record_statistics
from .registry import algorithm_capabilities, get_algorithm, register_algorithm
from .specs import AlgorithmSpecification, StatisticalSpecification

__all__ = [
    "AlgorithmSpecification",
    "StatisticalSpecification",
    "algorithm_capabilities",
    "calculate_specification",
    "get_algorithm",
    "register_algorithm",
    "verify_record_statistics",
]
