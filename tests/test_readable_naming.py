from __future__ import annotations

from pathlib import Path

from reprofig import (
    build_record,
    embed_file,
    extract_artifact,
    publish_artifacts,
    readable_filename_token,
)


def _artifact(path: Path, *, original_stem: str = "Readable Figure", figure_id: str | None = None):
    path.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>', encoding="utf-8")
    record = build_record(
        title="A much longer title that is not needed for the filename",
        original_stem=original_stem,
        producer={"package": "example"},
        plotted_data=[{"group": "control", "value": 1.0}],
        statistics=[{"test": "descriptive", "n": 1}],
        reproduction={"script": "print('reproduce')", "command": "python code/plot.py"},
        column_classification={"group": "safe", "value": "safe"},
    )
    if figure_id is not None:
        record.figure_id = figure_id
    embed_file(path, record, output_path=path)
    return record


def test_readable_tokens_are_short_portable_and_human_facing():
    assert readable_filename_token("  Résponse & Dose__Figure  ") == "response-and-dose-figure"
    assert readable_filename_token("CON") == "figure-con"
    assert len(readable_filename_token("word " * 100)) <= 80


def test_extract_artifact_uses_readable_names_without_exposing_identity(tmp_path):
    artifact = tmp_path / "machine-name.svg"
    record = _artifact(artifact)

    outputs = extract_artifact(artifact, tmp_path / "readable")
    names = {path.name for path in outputs}

    assert names == {
        "reprofig-manifest.json",
        "readable-figure-record.json",
        "readable-figure-plotted-data.csv",
        "readable-figure-statistics.csv",
        "readable-figure-caption.md",
        "readable-figure-producer.json",
        "readable-figure-plot.py",
    }
    assert all(record.figure_id not in name for name in names)


def test_extract_name_override_and_legacy_mode_are_explicit(tmp_path):
    artifact = tmp_path / "machine-name.svg"
    record = _artifact(artifact)

    readable = extract_artifact(
        artifact,
        tmp_path / "named",
        export_name="Final Dose Response",
    )
    assert "final-dose-response-record.json" in {path.name for path in readable}

    legacy = extract_artifact(artifact, tmp_path / "legacy", naming="legacy")
    legacy_names = {path.name for path in legacy}
    assert f"{record.figure_id}.record.json" in legacy_names
    assert f"{record.figure_id}.000-plotted_data.csv" in legacy_names
    assert f"{record.figure_id}.reproduce.py" in legacy_names


def test_publication_uses_override_and_readable_semantic_suffixes(tmp_path):
    artifact = tmp_path / "machine-name.svg"
    _artifact(artifact)

    result = publish_artifacts(
        artifact,
        output_dir=tmp_path / "public",
        safe_columns=["group", "value"],
        export_name="Final Dose Response",
    )

    assert result.valid
    assert {path.name for path in result.artifact_paths} == {
        "final-dose-response-public.svg"
    }
    assert {path.name for path in result.csv_paths} == {
        "final-dose-response-source-data.csv",
        "final-dose-response-statistics.csv",
    }
    assert result.manifest_path.name == "publication-manifest.json"
    assert result.validation_path.name == "publication-validation.json"


def test_legacy_publication_names_remain_available(tmp_path):
    artifact = tmp_path / "Machine Name.svg"
    _artifact(artifact)

    result = publish_artifacts(
        artifact,
        output_dir=tmp_path / "legacy-public",
        safe_columns=["group", "value"],
        naming="legacy",
    )

    assert {path.name for path in result.artifact_paths} == {
        "Machine Name.public.svg"
    }
    assert result.manifest_path.name == "publication_manifest.json"
    assert result.validation_path.name == "publication_validation.json"


def test_batch_collisions_add_only_a_short_permanent_identity(tmp_path):
    first = tmp_path / "first.svg"
    second = tmp_path / "second.svg"
    _artifact(first, original_stem="Repeated Name", figure_id="rf-aaaaaaaa11111111")
    _artifact(second, original_stem="Repeated Name", figure_id="rf-bbbbbbbb22222222")

    result = publish_artifacts(
        [first, second],
        output_dir=tmp_path / "public",
        safe_columns=["group", "value"],
    )

    assert {path.name for path in result.artifact_paths} == {
        "repeated-name-aaaaaaaa-public.svg",
        "repeated-name-bbbbbbbb-public.svg",
    }


def test_format_variants_share_readable_stem_and_companion_tables(tmp_path):
    svg = tmp_path / "figure.svg"
    record = _artifact(svg)
    html = tmp_path / "figure.html"
    html.write_text("<!doctype html><p>figure</p>", encoding="utf-8")
    embed_file(html, record, output_path=html)

    result = publish_artifacts(
        [svg, html],
        output_dir=tmp_path / "public",
        safe_columns=["group", "value"],
    )

    assert {path.name for path in result.artifact_paths} == {
        "readable-figure-public.svg",
        "readable-figure-public.html",
    }
    assert {path.name for path in result.csv_paths} == {
        "readable-figure-source-data.csv",
        "readable-figure-statistics.csv",
    }


def test_distinct_figures_get_suffixes_even_when_formats_differ(tmp_path):
    svg = tmp_path / "first" / "shared.svg"
    svg.parent.mkdir()
    html = tmp_path / "second" / "shared.html"
    html.parent.mkdir()
    _artifact(svg, original_stem="Shared", figure_id="rf-aaaaaaaa11111111")
    html.write_text("<!doctype html><p>figure</p>", encoding="utf-8")
    second = build_record(
        title="Shared",
        original_stem="Shared",
        producer={"package": "example"},
        plotted_data=[{"group": "control", "value": 2.0}],
        statistics=[{"test": "descriptive", "n": 1}],
        column_classification={"group": "safe", "value": "safe"},
    )
    second.figure_id = "rf-bbbbbbbb22222222"
    embed_file(html, second, output_path=html)

    result = publish_artifacts(
        [svg, html],
        output_dir=tmp_path / "public",
        safe_columns=["group", "value"],
    )

    assert {path.name for path in result.artifact_paths} == {
        "shared-aaaaaaaa-public.svg",
        "shared-bbbbbbbb-public.html",
    }
    assert len({path.name for path in result.csv_paths}) == len(result.csv_paths)
