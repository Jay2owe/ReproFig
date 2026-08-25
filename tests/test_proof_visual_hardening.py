from __future__ import annotations

from PIL import Image
import matplotlib.pyplot as plt

from reprofig import bind_artist, build_record, save_figure, verify_proof
from reprofig.artifacts import embed_file, extract_record


def _figure():
    figure, axes = plt.subplots(figsize=(3, 2))
    line, = axes.plot([0, 1, 2], [1, 3, 2])
    bind_artist(line, semantic_id="series-a", columns=["x", "y"])
    return figure


def test_declared_raster_region_detects_single_channel_change(tmp_path):
    figure = _figure()
    original = tmp_path / "original.png"
    record = save_figure(
        figure,
        original,
        plotted_data=[{"x": 0, "y": 1}, {"x": 1, "y": 3}, {"x": 2, "y": 2}],
        proof=True,
        dpi=100,
    )
    plt.close(figure)
    assert verify_proof(original, required=["display_verified"]).valid

    region = record.extensions["visual_reference"]["raster_reference"][
        "semantic_regions"
    ][0]["bbox"]
    left, top, right, bottom = region
    with Image.open(original) as image:
        changed = image.convert("RGBA")
    x, y = (left + right) // 2, (top + bottom) // 2
    red, green, blue, alpha = changed.getpixel((x, y))
    changed.putpixel((x, y), ((red + 1) % 256, green, blue, alpha))
    raw = tmp_path / "changed-raw.png"
    changed.save(raw)
    candidate = tmp_path / "changed.png"
    embed_file(raw, record, output_path=candidate)

    report = verify_proof(candidate, required=["display_verified"])
    assert not report.valid
    assert any(
        check.check_id.startswith("raster-region:") and check.status == "fail"
        for check in report.checks
    )


def test_encrypted_evidence_root_is_shared_across_svg_and_png(tmp_path, monkeypatch):
    base = build_record(
        plotted_data=[{"x": 0, "y": 1}, {"x": 1, "y": 3}, {"x": 2, "y": 2}],
        column_classification={"x": "safe", "y": "safe"},
    )
    table_id = f"table:{base.data_tables[0].sha256}"
    monkeypatch.setenv("REPROFIG_TEST_PASSWORD", "variant password")
    policy = {
        "encrypt_sections": [table_id],
        "encryption_password_env": "REPROFIG_TEST_PASSWORD",
    }
    figure = _figure()
    svg = tmp_path / "figure.svg"
    svg_record = save_figure(
        figure, svg, record=base, proof=True, proof_policy=policy
    )
    png = tmp_path / "figure.png"
    png_record = save_figure(
        figure, png, record=svg_record, proof=True, proof_policy=policy, dpi=100
    )
    plt.close(figure)

    assert svg_record.extensions["proof"]["root_sha256"] == png_record.extensions["proof"]["root_sha256"]
    assert extract_record(svg).extensions["proof"]["root_sha256"] == extract_record(png).extensions["proof"]["root_sha256"]
    assert verify_proof(svg, required=["display_verified"]).valid
    assert verify_proof(png, required=["display_verified"]).valid
