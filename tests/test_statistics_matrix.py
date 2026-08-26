from __future__ import annotations

import copy

import pytest

from reprofig import StatisticalSpecification, TransformationSpec, attach_evidence_graph
from reprofig.api import build_record
from reprofig.stats.engine import calculate_specification, verify_record_statistics
from reprofig.stats.registry import algorithm_capabilities
from reprofig.tables import table_from_data
from reprofig.transformations import verify_record_transformations
from reprofig.validation import validate_record


CASES = [
    ("descriptive/v1", {"values": [1, 2, 4, 5]}, {"confidence_level": 0.95, "missing_policy": "omit"}),
    ("one-sample-t/v1", {"values": [1, 2, 4, 5]}, {"null_mean": 0, "alternative": "two_sided", "missing_policy": "omit", "confidence_level": 0.95}),
    ("paired-t/v1", {"values_a": [2, 4, 8, 9], "values_b": [1, 3, 5, 7]}, {"alternative": "two_sided", "missing_policy": "omit", "confidence_level": 0.95, "pairing_identity": ["a", "b", "c", "d"]}),
    ("student-t/v1", {"values_a": [1, 2, 4, 5], "values_b": [3, 4, 7, 9]}, {"alternative": "two_sided", "missing_policy": "omit", "confidence_level": 0.95}),
    ("welch-t/v1", {"values_a": [1, 2, 4, 5], "values_b": [3, 4, 7, 9]}, {"alternative": "greater", "missing_policy": "omit", "confidence_level": 0.95}),
    ("mann-whitney/v1", {"values_a": [1, 2, 2, 5], "values_b": [2, 3, 4, 6]}, {"alternative": "two-sided", "method": "asymptotic", "continuity": True}),
    ("wilcoxon/v1", {"values_a": [0, 1, 1, -2, 3]}, {"alternative": "two-sided", "zero_method": "wilcox", "correction": False, "method": "approx"}),
    ("kruskal-wallis/v1", {"groups": [[1, 2, 2], [2, 3, 4], [4, 5, 6]]}, {"nan_policy": "omit"}),
    ("one-way-anova/v1", {"groups": [[1, 2, 3], [3, 5, 7], [8, 9, 11]]}, {}),
    ("welch-anova/v1", {"groups": [[1, 2, 4], [3, 5, 8], [7, 9, 13]]}, {}),
    ("ols/v1", {"design_matrix": [[1, 0], [1, 1], [1, 2], [1, 3], [1, 4]], "outcome": [1, 2, 2, 4, 5]}, {"coefficient_names": ["intercept", "dose"], "confidence_level": 0.95, "covariance": "classical", "missing_policy": "complete_rows", "rank_tolerance": 1e-12}),
    ("bootstrap-mean/v1", {"values": [1, 2, 4, 8]}, {"iterations": 100, "confidence_level": 0.95, "random_generator": "python-mt19937/v1", "random_seed": 7}),
    ("permutation-mean-difference/v1", {"values_a": [1, 2, 3], "values_b": [4, 5, 7]}, {"iterations": 100, "alternative": "two_sided", "random_generator": "python-mt19937/v1", "random_seed": 7}),
    ("bonferroni/v1", {"p_values": [0.01, 0.04, 0.2]}, {"member_ids": ["a", "b", "c"], "family_id": "family-1"}),
    ("holm/v1", {"p_values": [0.01, 0.04, 0.2]}, {"member_ids": ["a", "b", "c"], "family_id": "family-1"}),
    ("benjamini-hochberg/v1", {"p_values": [0.01, 0.04, 0.2]}, {"member_ids": ["a", "b", "c"], "family_id": "family-1"}),
]


@pytest.mark.parametrize(("algorithm_id", "inputs", "parameters"), CASES)
def test_every_registered_statistical_family_recalculates(
    algorithm_id, inputs, parameters
):
    draft = StatisticalSpecification(
        statistic_id=algorithm_id,
        algorithm_id=algorithm_id,
        inputs=inputs,
        parameters=parameters,
        expected={},
    )
    expected = calculate_specification(draft)
    specification = StatisticalSpecification.from_dict(
        {**draft.to_dict(), "expected": expected}
    )
    record = build_record(
        statistics=[{"test_id": algorithm_id}],
        extensions={"proof": {"statistical_specifications": [specification.to_dict()]}},
    )
    record = attach_evidence_graph(record)
    checks = verify_record_statistics(record)
    assert checks[0].status == "pass", [check.to_dict() for check in checks]
    assert checks[0].meaning == "statistics_independently_verified"


def test_registry_lists_all_implemented_algorithms_and_answer_changing_choices():
    capabilities = {item["algorithm_id"]: item for item in algorithm_capabilities()}
    assert set(capabilities) == {case[0] for case in CASES}
    assert "pairing_identity" in capabilities["paired-t/v1"]["required_parameters"]
    assert "family_id" in capabilities["holm/v1"]["required_parameters"]
    assert "random_generator" in capabilities["bootstrap-mean/v1"]["required_parameters"]
    assert "rank_tolerance" in capabilities["ols/v1"]["required_parameters"]


def test_incomplete_typed_specification_is_invalid_and_wrong_result_fails():
    incomplete = StatisticalSpecification(
        statistic_id="bad",
        algorithm_id="welch-t/v1",
        inputs={"values_a": [1, 2], "values_b": [3, 4]},
        parameters={"alternative": "two_sided"},
        expected={"p_value": 0.5},
    )
    record = build_record(
        extensions={"proof": {"statistical_specifications": [incomplete.to_dict()]}}
    )
    record = attach_evidence_graph(record)
    report = validate_record(record)
    assert any(issue.code == "statistical_specification_incomplete" for issue in report.issues)
    assert verify_record_statistics(record)[0].status == "fail"


def test_exact_result_and_display_formatter_are_checked_separately():
    draft = StatisticalSpecification(
        statistic_id="displayed-p",
        algorithm_id="welch-t/v1",
        inputs={"values_a": [1, 2, 4, 5], "values_b": [3, 4, 7, 9]},
        parameters={"alternative": "two_sided", "missing_policy": "omit", "confidence_level": 0.95},
        expected={},
    )
    expected = calculate_specification(draft)
    draft.expected = expected
    draft.display = {
        "field": "p_value",
        "format": "p_equals_4dp/v1",
        "text": f"p = {expected['p_value']:.4f}",
    }
    record = attach_evidence_graph(build_record(
        extensions={"proof": {"statistical_specifications": [draft.to_dict()]}}
    ))
    checks = verify_record_statistics(record)
    assert [check.status for check in checks] == ["pass", "pass"]

    changed = copy.deepcopy(record)
    changed.extensions["proof"]["statistical_specifications"][0]["display"]["text"] = "p = 0.9999"
    changed = attach_evidence_graph(changed)
    assert verify_record_statistics(changed)[1].status == "fail"


def test_source_transformation_reconstructs_exact_target_and_detects_changed_source():
    source_rows = [
        {"group": "A", "value": 1},
        {"group": "B", "value": 2},
        {"group": "A", "value": 3},
    ]
    target = table_from_data(
        [{"group": "A", "value": 1}, {"group": "A", "value": 3}]
    )
    record = build_record(data_tables=[target])
    specification = TransformationSpec(
        operation="filter",
        input_table_ids=["source:raw"],
        output_table_id=f"table:{target.sha256}",
        parameters={"column": "group", "operator": "eq", "value": "A"},
    )
    record.extensions["proof"] = {"transformations": [specification.to_dict()]}
    record = attach_evidence_graph(record)
    assert verify_record_transformations(
        record, supplied_tables={"source:raw": source_rows}
    )[0].status == "pass"
    changed = copy.deepcopy(source_rows)
    changed[2]["value"] = 9
    assert verify_record_transformations(
        record, supplied_tables={"source:raw": changed}
    )[0].status == "fail"
