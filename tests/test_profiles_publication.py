from __future__ import annotations

import json

import pandas as pd
import pytest

from reprofig import (
    SourceReference,
    build_record,
    caption_for,
    derive_profile,
    embed_record,
    extract_record,
    publish_figures,
    validate_svg,
)
from reprofig.cli import main


def _master(tmp_path):
    frame = pd.DataFrame(
        {
            "condition": ["control", "treated"],
            "value": [1.0, 2.0],
            "subject": ["Jamie-001", "Jamie-002"],
        }
    )
    record = build_record(
        title="Public probe",
        producer={
            "package": "example-analysis",
            "version": "1.0",
            "function": "example.plot",
            "request": {"data": r"X:\private\data.csv"},
        },
        plotted_data=frame,
        statistics=[{"kind": "comparison", "p_raw": 0.0123456789, "n": 2}],
        sources=[
            SourceReference(
                role="raw_csv",
                relative_path="Data/private.csv",
                sha256="abc",
                source_id="dataset",
            )
        ],
        reproduction={"script": r"read_csv('X:\private\data.csv')"},
        column_classification={
            "condition": "safe",
            "value": "safe",
            "subject": "private",
        },
    )
    svg = tmp_path / "Figure 1.svg"
    svg.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        '<metadata><dc:description>{"path":"X:\\private"}'
        '</dc:description></metadata><text>plot</text></svg>',
        encoding="utf-8",
    )
    embed_record(svg, record)
    return svg, record


def test_public_and_minimal_profiles_are_one_way(tmp_path):
    _svg, master = _master(tmp_path)
    public = derive_profile(
        master,
        "public",
        safe_columns=["condition", "value"],
        public_sources={"dataset": "https://example.org/data.csv"},
    )
    assert [column.name for column in public.data_tables[0].columns] == [
        "condition",
        "value",
    ]
    assert "subject" not in public.data_tables[0].contents
    assert public.sources[0].relative_path is None
    assert public.sources[0].uri == "https://example.org/data.csv"
    minimal = derive_profile(public, "minimal_public")
    assert minimal.data_tables[0].contents is None
    with pytest.raises(ValueError):
        derive_profile(minimal, "public")


def test_caption_uses_exact_machine_value_not_only_display_text(tmp_path):
    _svg, master = _master(tmp_path)
    caption = caption_for(master)
    assert "exact p=0.0123456789" in caption
    assert "n=2" in caption


@pytest.mark.parametrize("profile,suffix", [("public", "public"), ("minimal_public", "minimal-public")])
def test_batch_publication_writes_safe_svg_csvs_and_reports(tmp_path, profile, suffix):
    svg, master = _master(tmp_path)
    output = tmp_path / profile
    result = publish_figures(
        svg,
        output_dir=output,
        figure_profile=profile,
        safe_columns=["condition", "value"],
        public_sources={"dataset": "https://example.org/data.csv"},
    )
    published = output / f"figure-1-{suffix}.svg"
    assert result.valid
    assert published.is_file()
    assert (output / "figure-1-source-data.csv").is_file()
    assert (output / "figure-1-statistics.csv").is_file()
    assert (output / "publication-manifest.csv").is_file()
    validation = json.loads((output / "publication-validation.json").read_text(encoding="utf-8"))
    assert validation["valid"] is True
    assert validation["figures"][0]["transformations"]
    record = extract_record(published)
    assert record.figure_id == master.figure_id
    assert record.distribution_profile == profile
    assert validate_svg(published, public_safety=True).valid
    for path in output.iterdir():
        if path.is_file():
            assert "X:\\private" not in path.read_text(encoding="utf-8-sig")
    manifest = (output / "publication-manifest.csv").read_text(encoding="utf-8")
    assert "output_svg_sha256" in manifest
    assert "source_data_sha256s" in manifest
    assert "statistics_csv_sha256" in manifest
    assert "public_source_links" in manifest
    assert str(svg) not in manifest
    if profile == "minimal_public":
        assert record.data_tables[0].contents is None


def test_cli_publishes_hyphenated_minimal_profile_with_public_source(tmp_path, capsys):
    svg, _master_record = _master(tmp_path)
    output = tmp_path / "cli-publication"
    assert main([
        "publish",
        str(svg),
        "--output-dir",
        str(output),
        "--profile",
        "minimal-public",
        "--safe-columns",
        "condition,value",
        "--name",
        "Final Figure",
        "--public-source",
        "dataset=https://example.org/data.csv",
    ]) == 0
    capsys.readouterr()
    record = extract_record(output / "final-figure-minimal-public.svg")
    assert record.distribution_profile == "minimal_public"
    assert record.sources[0].uri == "https://example.org/data.csv"


def test_publication_fails_closed_without_column_approval(tmp_path):
    svg, _record = _master(tmp_path)
    with pytest.raises(ValueError, match="no public columns"):
        publish_figures(svg, output_dir=tmp_path / "failed", safe_columns=[])


def test_publication_rejects_external_styles_and_leaves_no_artifacts(tmp_path):
    svg, _record = _master(tmp_path)
    text = svg.read_text(encoding="utf-8").replace(
        "<metadata>", '<style>@import url("https://private.example/style.css");</style><metadata>',
    )
    svg.write_text(text, encoding="utf-8")
    output = tmp_path / "unsafe-style"
    with pytest.raises(ValueError, match="public validation failed"):
        publish_figures(
            svg,
            output_dir=output,
            safe_columns=["condition", "value"],
        )
    assert not list(output.glob("*"))
