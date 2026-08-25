from __future__ import annotations

import shutil

import pandas as pd
import pytest

from reprofig import (
    FigureRecord,
    build_record,
    embed_record,
    extract_figure,
    extract_record,
    statistics_csv_bytes,
    validate_record,
)


def _svg(path):
    path.write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<rect width="10" height="10"/></svg>\n',
        encoding="utf-8",
    )


def test_master_round_trip_extracts_exact_csv_and_statistics(tmp_path):
    frame = pd.DataFrame(
        {
            "group": ["control", "treated"],
            "value": [0.1 + 0.2, 1.2345678901234567],
            "animal": ["a-1", "a-2"],
        }
    )
    statistics = [
        {
            "kind": "group_comparison",
            "test": {"name": "Welch t-test", "statistic": 2.3, "p": 0.003781462913},
            "groups": [{"name": "control", "n": 1}, {"name": "treated", "n": 1}],
        }
    ]
    record = build_record(
        title="Probe",
        producer={"package": "OtherPlotPackage", "version": "9.1"},
        plotted_data=frame,
        statistics=statistics,
        column_classification={"group": "safe", "value": "safe", "animal": "private"},
        column_roles={"group": "group", "value": "value", "animal": "independent_unit"},
    )
    svg = tmp_path / "probe.svg"
    _svg(svg)
    embed_record(svg, record)
    loaded = extract_record(svg)
    assert loaded.figure_id == record.figure_id
    assert loaded.data_tables[0].contents == record.data_tables[0].contents
    assert loaded.data_tables[0].verify()
    assert loaded.statistics == record.statistics
    assert validate_record(loaded, require_complete=True).valid

    output = tmp_path / "extracted"
    written = extract_figure(svg, output)
    data = output / "probe.source-data.csv"
    stats = output / "probe.statistics.csv"
    assert data in written
    assert data.read_bytes() == record.data_tables[0].contents.encode("utf-8")
    assert stats.read_bytes() == statistics_csv_bytes(statistics)


def test_embedding_is_idempotent_and_survives_move(tmp_path):
    record = build_record(
        plotted_data=b"x,y\n1,2\n",
        statistics=[],
        statistics_status="not_applicable",
        producer={"package": "example"},
    )
    svg = tmp_path / "one.svg"
    _svg(svg)
    embed_record(svg, record)
    embed_record(svg, record)
    assert svg.read_text(encoding="utf-8").count("<fig:figure-record") == 1
    moved = tmp_path / "renamed.svg"
    shutil.copy2(svg, moved)
    assert extract_record(moved).figure_id == record.figure_id


@pytest.mark.parametrize(
    ("schema", "figure_id", "legacy_namespace"),
    [
        (
            "figure-artifact/1",
            "fa-development-record",
            "https://figure-artifact.org/ns/figure-record/1",
        ),
        (
            "metafig/1",
            "mf-development-record",
            "https://metafig.org/ns/figure-record/1",
        ),
    ],
)
def test_reprofig_rename_keeps_development_era_svg_records_readable(
    tmp_path, schema, figure_id, legacy_namespace
):
    record = FigureRecord(
        schema=schema,
        figure_id=figure_id,
        statistics_status="not_applicable",
    )
    svg = tmp_path / "legacy-name.svg"
    _svg(svg)
    embed_record(svg, record)
    svg.write_text(
        svg.read_text(encoding="utf-8").replace(
            "https://reprofig.org/ns/figure-record/1",
            legacy_namespace,
        ),
        encoding="utf-8",
    )

    loaded = extract_record(svg)
    assert loaded.figure_id == figure_id
    assert loaded.schema == schema
    assert validate_record(loaded).valid


def test_large_payload_is_not_limited_to_svg_header(tmp_path):
    frame = pd.DataFrame({"x": range(25_000), "text": ["αβγ" * 5] * 25_000})
    record = build_record(
        plotted_data=frame,
        statistics=[],
        statistics_status="not_applicable",
        producer={"package": "large-example"},
    )
    svg = tmp_path / "large.svg"
    _svg(svg)
    embed_record(svg, record)
    assert svg.stat().st_size > 65_536
    loaded = extract_record(svg)
    assert loaded.data_tables[0].row_count == 25_000
    assert loaded.data_tables[0].contents == record.data_tables[0].contents


def test_embedding_warns_at_configurable_size_threshold(tmp_path):
    record = build_record(
        plotted_data=pd.DataFrame({"value": range(10)}),
        statistics_status="not_applicable",
    )
    svg = tmp_path / "warning.svg"
    _svg(svg)
    with pytest.warns(RuntimeWarning, match="uncompressed bytes"):
        embed_record(svg, record, warn_uncompressed=1, warn_compressed=None)


def test_master_rejects_absolute_paths_inside_exact_plotted_data():
    with pytest.raises(ValueError, match="private material"):
        build_record(
            plotted_data=pd.DataFrame({"source": [r"X:\private\private.csv"]}),
            statistics_status="not_applicable",
        )
