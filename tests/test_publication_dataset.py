from __future__ import annotations

import importlib

from reprofig.schema import ColumnSpec, SCHEMA_ID, sha256_bytes
from reprofig.workbook.models import (
    WORKBOOK_SCHEMA,
    CoverageDeclaration,
    PublicationDataset,
    PublicationFigure,
    PublicationStatistic,
    PublicationTable,
    StatisticOccurrence,
    TableOccurrence,
    TestFamily as PublicationTestFamily,
    VerificationRow,
)


FIGURE_A_SHA = "a" * 64
FIGURE_B_SHA = "b" * 64


def _table(name: str, contents: str, figure_id: str, record_sha: str, index: int) -> PublicationTable:
    table_sha = sha256_bytes(contents.encode("utf-8"))
    return PublicationTable(
        name=name,
        purpose="plot_and_statistics",
        sha256=table_sha,
        row_count=1,
        column_count=2,
        columns=[
            ColumnSpec("group", dtype="str", role="group", public_state="safe"),
            ColumnSpec("value", dtype="float", role="value", public_state="safe"),
        ],
        contents=contents,
        occurrences=[
            TableOccurrence(
                figure_id=figure_id,
                figure_record_sha256=record_sha,
                table_name=name,
                table_index=index,
            )
        ],
    )


def _dataset(**overrides) -> PublicationDataset:
    stats = [
        PublicationStatistic(
            test_id="experiment-test:welch:fig-a:0",
            raw_record={"kind": "comparison", "p": "0.012345678900", "n": 2},
            occurrences=[
                StatisticOccurrence(
                    figure_id="fig-a",
                    figure_record_sha256=FIGURE_A_SHA,
                    statistic_index=0,
                )
            ],
            normalized={"family": "t_test", "p": "0.012345678900"},
            family_id="test-family:t-tests",
        ),
        PublicationStatistic(
            test_id="figure-stat:fig-b:0",
            raw_record={"kind": "summary", "value": "not_applicable"},
            occurrences=[
                StatisticOccurrence(
                    figure_id="fig-b",
                    figure_record_sha256=FIGURE_B_SHA,
                    statistic_index=0,
                )
            ],
            displayed=True,
            source="figure",
        ),
    ]
    values = {
        "profile": "master",
        "figures": [
            PublicationFigure(
                figure_id="fig-a",
                figure_record_sha256=FIGURE_A_SHA,
                display_order=1,
                title="Figure A",
            ),
            PublicationFigure(
                figure_id="fig-b",
                figure_record_sha256=FIGURE_B_SHA,
                display_order=2,
                title="Figure B",
            ),
        ],
        "tables": [
            _table("source-data", "group,value\ncontrol,1.0\n", "fig-a", FIGURE_A_SHA, 0),
            _table("source-data", "group,value\ntreated,2.0\n", "fig-b", FIGURE_B_SHA, 0),
        ],
        "statistics": stats,
        "test_families": [
            PublicationTestFamily(
                family_id="test-family:t-tests",
                label="Welch t-tests",
                test_ids=["experiment-test:welch:fig-a:0"],
            )
        ],
        "verification": [
            VerificationRow(
                verification_id="verification:tables-present",
                subject_id="table",
                status="pass",
                check="source-data",
                message="tables represented",
            )
        ],
        "statistics_coverage": "figure_complete",
        "coverage": CoverageDeclaration(
            figure_ids=["fig-a", "fig-b"],
            test_ids=["experiment-test:welch:fig-a:0", "figure-stat:fig-b:0"],
        ),
    }
    values.update(overrides)
    return PublicationDataset(**values)


def test_workbook_models_import_without_optional_packages():
    models = importlib.import_module("reprofig.workbook.models")
    assert models.WORKBOOK_SCHEMA == "reprofig-publication-workbook/1"
    assert SCHEMA_ID == "reprofig/1"


def test_publication_dataset_round_trips_through_deterministic_json():
    dataset = _dataset()
    loaded = PublicationDataset.from_json(dataset.to_json())
    assert loaded == dataset
    assert loaded.to_json() == dataset.to_json()
    assert loaded.validate() == []


def test_reordering_inputs_does_not_change_fingerprint_or_default_identifier():
    dataset = _dataset()
    reordered = _dataset(
        figures=list(reversed(dataset.figures)),
        tables=list(reversed(dataset.tables)),
        statistics=list(reversed(dataset.statistics)),
        test_families=list(reversed(dataset.test_families)),
        verification=list(reversed(dataset.verification)),
    )
    assert reordered.publication_id == dataset.publication_id
    assert reordered.fingerprint() == dataset.fingerprint()


def test_evidence_fingerprint_changes_when_canonical_evidence_changes():
    dataset = _dataset()
    changed_table = _dataset(
        tables=[
            _table("source-data", "group,value\ncontrol,9.0\n", "fig-a", FIGURE_A_SHA, 0),
            dataset.tables[1],
        ]
    )
    changed_statistic = _dataset(
        statistics=[
            PublicationStatistic(
                test_id="experiment-test:welch:fig-a:0",
                raw_record={"kind": "comparison", "p": "0.020000000000", "n": 2},
                occurrences=dataset.statistics[0].occurrences,
                normalized={"family": "t_test", "p": "0.020000000000"},
                family_id="test-family:t-tests",
            ),
            dataset.statistics[1],
        ]
    )
    changed_figure = _dataset(
        figures=[
            PublicationFigure(
                figure_id="fig-a",
                figure_record_sha256="c" * 64,
                display_order=1,
                title="Figure A",
            ),
            dataset.figures[1],
        ],
        statistics=[
            PublicationStatistic(
                test_id="experiment-test:welch:fig-a:0",
                raw_record=dataset.statistics[0].raw_record,
                occurrences=[
                    StatisticOccurrence(
                        figure_id="fig-a",
                        figure_record_sha256="c" * 64,
                        statistic_index=0,
                    )
                ],
                normalized=dataset.statistics[0].normalized,
                family_id="test-family:t-tests",
            ),
            dataset.statistics[1],
        ],
        tables=[
            _table("source-data", "group,value\ncontrol,1.0\n", "fig-a", "c" * 64, 0),
            dataset.tables[1],
        ],
    )
    fingerprints = {
        dataset.fingerprint(),
        changed_table.fingerprint(),
        changed_statistic.fingerprint(),
        changed_figure.fingerprint(),
    }
    assert len(fingerprints) == 4


def test_build_path_and_worksheet_style_do_not_affect_evidence_fingerprint():
    first = _dataset(
        build_metadata={"created_at": "2026-08-25T12:00:00+01:00"},
        output_path=r"X:\private\Publication-source-data.xlsx",
        worksheet_style={"header_fill": "blue"},
    )
    second = _dataset(
        build_metadata={"created_at": "2030-01-01T00:00:00+00:00"},
        output_path="/tmp/renamed.xlsx",
        worksheet_style={"header_fill": "green"},
    )
    assert first.to_dict() != second.to_dict()
    assert first.publication_id == second.publication_id
    assert first.fingerprint() == second.fingerprint()


def test_validation_reports_duplicate_identifiers_and_invalid_coverage():
    duplicate_table = _dataset().tables[0]
    invalid = _dataset(
        figures=[
            PublicationFigure("fig-a", FIGURE_A_SHA),
            PublicationFigure("fig-a", FIGURE_B_SHA),
        ],
        tables=[duplicate_table, duplicate_table],
        statistics=[
            PublicationStatistic(test_id="test:duplicate", raw_record={"p": "0.01"}),
            PublicationStatistic(test_id="test:duplicate", raw_record={"p": "0.02"}),
        ],
        statistics_coverage="complete",
        coverage=CoverageDeclaration(test_ids=["missing-test"], figure_ids=["missing-figure"]),
    )
    errors = invalid.validate()
    assert (
        "conflicting figures share figure_id 'fig-a' "
        "with different figure_record_sha256 values"
    ) in errors
    assert any(error.startswith("duplicate table_id: table:") for error in errors)
    assert "duplicate test_id: test:duplicate" in errors
    assert (
        "statistics_coverage must be one of "
        "['analysis_complete', 'figure_complete', 'incomplete', 'not_applicable'], "
        "not 'complete'"
    ) in errors
    assert "coverage references unknown figure_id: missing-figure" in errors
    assert "coverage references unknown test_id: missing-test" in errors


def test_validation_reports_table_hash_mismatch():
    table = PublicationTable(
        name="source-data",
        purpose="plot_and_statistics",
        sha256=sha256_bytes(b"original\n"),
        row_count=1,
        column_count=1,
        columns=[ColumnSpec("value")],
        contents="changed\n",
    )
    errors = _dataset(tables=[table]).validate()
    assert errors == [f"table hash mismatch: {table.table_id}"]


def test_workbook_schema_identifier_is_separate_from_figure_record_schema():
    dataset = _dataset()
    assert WORKBOOK_SCHEMA == "reprofig-publication-workbook/1"
    assert dataset.schema == WORKBOOK_SCHEMA
    assert SCHEMA_ID == "reprofig/1"
