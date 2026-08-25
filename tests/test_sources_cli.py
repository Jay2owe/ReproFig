from __future__ import annotations

import json
from pathlib import Path

from reprofig import classify_figure, scan_figures, source_reference, source_status
from reprofig.cli import _key_value_pairs, _profile, main


def test_source_fingerprint_detects_changes(tmp_path):
    source = tmp_path / "data.csv"
    source.write_text("x\n1\n", encoding="utf-8")
    reference = source_reference(source, project_root=tmp_path, role="raw_csv")
    assert reference.relative_path == "data.csv"
    assert source_status(reference, project_root=tmp_path) == "unchanged"
    source.write_text("x\n2\n", encoding="utf-8")
    assert source_status(reference, project_root=tmp_path) == "changed"


def test_cli_validate_returns_failure_for_plain_svg(tmp_path, capsys):
    svg = tmp_path / "plain.svg"
    svg.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    assert main(["validate", str(svg)]) == 1
    output = json.loads(capsys.readouterr().out)
    assert output["valid"] is False


def test_cli_accepts_hyphenated_profile_and_public_source_pairs():
    assert _profile("minimal-public") == "minimal_public"
    assert _key_value_pairs(
        ["dataset=https://example.org/data.csv"], option="--public-source"
    ) == {"dataset": "https://example.org/data.csv"}


def test_historical_figures_are_classified_without_inventing_missing_data(tmp_path):
    legacy = tmp_path / "legacy.svg"
    legacy.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<metadata><dc:description>{"function":"old.plot","pyflash_version":"0.1"}'
        '</dc:description></metadata></svg>',
        encoding="utf-8",
    )
    sidecar = tmp_path / "sidecar.svg"
    sidecar.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    (tmp_path / "figures.json").write_text(
        json.dumps({"figures": {sidecar.name: {"function": "older.plot"}}}),
        encoding="utf-8",
    )
    assert classify_figure(legacy)["provenance_level"] == "producer_only"
    assert classify_figure(sidecar)["provenance_level"] == "sidecar_only"
    rows = {Path(row["path"]).name: row for row in scan_figures(tmp_path)}
    assert rows[legacy.name]["provenance_level"] == "producer_only"
    assert rows[sidecar.name]["provenance_level"] == "sidecar_only"
