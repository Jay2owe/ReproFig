"""Versioned statistical algorithm registry."""

from __future__ import annotations

from typing import Any, Callable

from .anova import one_way_anova, welch_anova
from .corrections import correct
from .descriptive import descriptive_statistics
from .rank import kruskal_wallis, mann_whitney, wilcoxon_signed_rank
from .regression import ordinary_least_squares
from .resampling import bootstrap_mean, permutation_mean_difference
from .specs import AlgorithmSpecification
from .ttests import independent_t, one_sample_t, paired_t

_REGISTRY: dict[str, AlgorithmSpecification] = {}


def _correction_calculator(
    p_values, *, member_ids, method: str, family_id: str | None = None
):
    identities = [str(value) for value in member_ids]
    values = [float(value) for value in p_values]
    if len(identities) != len(values) or len(identities) != len(set(identities)):
        raise ValueError(
            "multiple-comparison correction requires one unique member_id per p value"
        )
    adjusted = correct(values, method)
    return {
        "family_id": family_id,
        "method": method,
        "adjusted_p_values": {
            identity: value for identity, value in sorted(zip(identities, adjusted))
        },
    }


def _paired_calculator(values_a, values_b, **parameters):
    identities = parameters.pop("pairing_identity", None)
    if not isinstance(identities, list) or len(identities) != len(values_a):
        raise ValueError("pairing_identity must contain one identity per declared pair")
    if len(set(map(str, identities))) != len(identities):
        raise ValueError("pairing_identity values must be unique")
    return paired_t(values_a, values_b, **parameters)


def _ols_calculator(design_matrix, outcome, **parameters):
    covariance = parameters.pop("covariance")
    missing_policy = parameters.pop("missing_policy")
    rank_tolerance = float(parameters.pop("rank_tolerance"))
    if covariance != "classical" or missing_policy != "complete_rows":
        raise ValueError("ols/v1 supports classical covariance and complete_rows only")
    if rank_tolerance <= 0:
        raise ValueError("rank_tolerance must be positive")
    return ordinary_least_squares(
        design_matrix, outcome, rank_tolerance=rank_tolerance, **parameters
    )


def _bootstrap_calculator(values, **parameters):
    generator = parameters.pop("random_generator")
    if generator not in {"embedded-index-plan/v1", "python-mt19937/v1"}:
        raise ValueError("unsupported bootstrap random_generator")
    if generator == "embedded-index-plan/v1" and parameters.get("index_plan") is None:
        raise ValueError("embedded-index-plan/v1 requires index_plan")
    if generator == "python-mt19937/v1" and parameters.get("random_seed") is None:
        raise ValueError("python-mt19937/v1 requires random_seed")
    return bootstrap_mean(values, **parameters)


def _permutation_calculator(values_a, values_b, **parameters):
    generator = parameters.pop("random_generator")
    if generator not in {"embedded-index-plan/v1", "python-mt19937/v1"}:
        raise ValueError("unsupported permutation random_generator")
    if generator == "embedded-index-plan/v1" and parameters.get("index_plan") is None:
        raise ValueError("embedded-index-plan/v1 requires index_plan")
    if generator == "python-mt19937/v1" and parameters.get("random_seed") is None:
        raise ValueError("python-mt19937/v1 requires random_seed")
    return permutation_mean_difference(values_a, values_b, **parameters)


def register_algorithm(specification: AlgorithmSpecification) -> None:
    if specification.algorithm_id in _REGISTRY:
        raise ValueError(f"statistical algorithm already registered: {specification.algorithm_id}")
    _REGISTRY[specification.algorithm_id] = specification


def get_algorithm(algorithm_id: str) -> AlgorithmSpecification | None:
    return _REGISTRY.get(algorithm_id)


def algorithm_capabilities() -> list[dict[str, Any]]:
    return [
        {
            "algorithm_id": item.algorithm_id,
            "input_roles": list(item.input_roles),
            "required_parameters": list(item.required_parameters),
            "output_fields": list(item.output_fields),
            "independent": item.independent,
            "notes": item.notes,
        }
        for item in sorted(_REGISTRY.values(), key=lambda value: value.algorithm_id)
    ]


def _register_defaults() -> None:
    entries = [
        AlgorithmSpecification("descriptive/v1", ("values",), ("confidence_level", "missing_policy"), ("n", "mean", "variance", "standard_error", "ci_low", "ci_high"), descriptive_statistics),
        AlgorithmSpecification("one-sample-t/v1", ("values",), ("null_mean", "alternative", "missing_policy", "confidence_level"), ("statistic", "df", "p_value"), one_sample_t),
        AlgorithmSpecification("paired-t/v1", ("values_a", "values_b"), ("alternative", "missing_policy", "confidence_level", "pairing_identity"), ("statistic", "df", "p_value"), _paired_calculator),
        AlgorithmSpecification("student-t/v1", ("values_a", "values_b"), ("alternative", "missing_policy", "confidence_level"), ("statistic", "df", "p_value"), lambda values_a, values_b, **parameters: independent_t(values_a, values_b, equal_variance=True, **parameters)),
        AlgorithmSpecification("welch-t/v1", ("values_a", "values_b"), ("alternative", "missing_policy", "confidence_level"), ("statistic", "df", "p_value"), lambda values_a, values_b, **parameters: independent_t(values_a, values_b, equal_variance=False, **parameters)),
        AlgorithmSpecification("mann-whitney/v1", ("values_a", "values_b"), ("alternative", "method", "continuity"), ("statistic", "p_value"), mann_whitney),
        AlgorithmSpecification("wilcoxon/v1", ("values_a",), ("alternative", "zero_method", "correction", "method"), ("statistic", "p_value"), wilcoxon_signed_rank),
        AlgorithmSpecification("kruskal-wallis/v1", ("groups",), ("nan_policy",), ("statistic", "df", "p_value"), kruskal_wallis),
        AlgorithmSpecification("one-way-anova/v1", ("groups",), (), ("statistic", "df1", "df2", "p_value"), one_way_anova),
        AlgorithmSpecification("welch-anova/v1", ("groups",), (), ("statistic", "df1", "df2", "p_value"), welch_anova),
        AlgorithmSpecification("ols/v1", ("design_matrix", "outcome"), ("coefficient_names", "confidence_level", "covariance", "missing_policy", "rank_tolerance"), ("coefficients", "df_residual", "residual_variance"), _ols_calculator),
        AlgorithmSpecification("bootstrap-mean/v1", ("values",), ("iterations", "confidence_level", "random_generator"), ("estimate", "ci_low", "ci_high"), _bootstrap_calculator),
        AlgorithmSpecification("permutation-mean-difference/v1", ("values_a", "values_b"), ("iterations", "alternative", "random_generator"), ("mean_difference", "p_value"), _permutation_calculator),
        AlgorithmSpecification("bonferroni/v1", ("p_values",), ("member_ids", "family_id"), ("adjusted_p_values",), lambda p_values, **parameters: _correction_calculator(p_values, method="bonferroni/v1", **parameters)),
        AlgorithmSpecification("holm/v1", ("p_values",), ("member_ids", "family_id"), ("adjusted_p_values",), lambda p_values, **parameters: _correction_calculator(p_values, method="holm/v1", **parameters)),
        AlgorithmSpecification("benjamini-hochberg/v1", ("p_values",), ("member_ids", "family_id"), ("adjusted_p_values",), lambda p_values, **parameters: _correction_calculator(p_values, method="benjamini-hochberg/v1", **parameters)),
    ]
    for entry in entries:
        register_algorithm(entry)


_register_defaults()


__all__ = ["algorithm_capabilities", "get_algorithm", "register_algorithm"]
