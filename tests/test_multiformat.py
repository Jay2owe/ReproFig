from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from reprofig.api import build_record
from reprofig.artifacts import (
    embed_file,
    extract_records,
    publish_artifacts,
    save_figure,
    validate_artifact,
)


@pytest.fixture
def record():
    return build_record(
        title="Round trip",
        producer={"package": "test", "version": "1.2.3"},
        plotted_data=[{"group": "A", "value": 1.25}, {"group": "B", "value": 2.5}],
        statistics=[{"test": "Welch t-test", "n": 2, "p": 0.012345}],
        column_classification={"group": "safe", "value": "safe"},
    )


def _roundtrip(source: Path, target: Path, record, **kwargs):
    embed_file(source, record, output_path=target, **kwargs)
    recovered = extract_records(target)
    assert [item.fingerprint() for item in recovered] == [record.fingerprint()]
    assert validate_artifact(target).valid


def test_svg(tmp_path, record):
    source = tmp_path / "source.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
    _roundtrip(source, tmp_path / "out.svg", record)


@pytest.mark.parametrize("suffix", ["png", "jpg", "tif", "webp"])
def test_common_rasters(tmp_path, record, suffix):
    from PIL import Image

    source = tmp_path / f"source.{suffix}"
    Image.new("RGB", (4, 3), "red").save(source)
    original_pixels = list(Image.open(source).get_flattened_data())
    target = tmp_path / f"out.{suffix}"
    _roundtrip(source, target, record)
    assert list(Image.open(target).get_flattened_data()) == original_pixels


def test_pdf(tmp_path, record):
    import pikepdf

    source = tmp_path / "source.pdf"
    with pikepdf.Pdf.new() as pdf:
        pdf.add_blank_page(page_size=(100, 100))
        pdf.save(source)
    _roundtrip(source, tmp_path / "out.pdf", record)
    with pikepdf.Pdf.open(tmp_path / "out.pdf") as pdf:
        assert len(pdf.pages) == 1
        assert "reprofig/manifest.json" in pdf.attachments


@pytest.mark.parametrize(
    ("suffix", "marker"),
    [
        ("pptx", "ppt/presentation.xml"),
        ("docx", "word/document.xml"),
        ("xlsx", "xl/workbook.xml"),
    ],
)
def test_office(tmp_path, record, suffix, marker):
    source = tmp_path / f"source.{suffix}"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr(marker, "<root/>")
        archive.writestr(
            "[Content_Types].xml",
            '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"/>',
        )
    _roundtrip(source, tmp_path / f"out.{suffix}", record)


def test_html(tmp_path, record):
    source = tmp_path / "source.html"
    source.write_text("<!doctype html><html><body><p>hello</p></body></html>")
    _roundtrip(source, tmp_path / "out.html", record)


def test_hdf5(tmp_path, record):
    import h5py

    source = tmp_path / "source.h5"
    with h5py.File(source, "w") as file:
        file.create_dataset("values", data=[1, 2, 3])
    _roundtrip(source, tmp_path / "out.h5", record)
    with h5py.File(tmp_path / "out.h5") as file:
        assert list(file["values"][...]) == [1, 2, 3]


def test_netcdf(tmp_path, record):
    import netCDF4

    source = tmp_path / "source.nc"
    with netCDF4.Dataset(source, "w", format="NETCDF4") as dataset:
        dataset.createDimension("x", 3)
        variable = dataset.createVariable("values", "i4", ("x",))
        variable[:] = [1, 2, 3]
    _roundtrip(source, tmp_path / "out.nc", record)
    with netCDF4.Dataset(tmp_path / "out.nc") as dataset:
        assert list(dataset.variables["values"][:]) == [1, 2, 3]


def test_fits(tmp_path, record):
    from astropy.io import fits

    source = tmp_path / "source.fits"
    fits.PrimaryHDU(data=[[1, 2], [3, 4]]).writeto(source)
    _roundtrip(source, tmp_path / "out.fits", record)
    with fits.open(tmp_path / "out.fits") as opened:
        assert opened[0].data.tolist() == [[1, 2], [3, 4]]


def test_zip_bundle_is_deterministic(tmp_path, record):
    source = tmp_path / "source.zip"
    with zipfile.ZipFile(source, "w") as archive:
        archive.writestr("README.txt", "hello")
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    _roundtrip(source, first, record)
    _roundtrip(source, second, record)
    assert first.read_bytes() == second.read_bytes()


def test_avif_requires_explicit_reencode(tmp_path, record):
    from PIL import Image

    source = tmp_path / "source.avif"
    Image.new("RGB", (4, 3), "red").save(source, format="AVIF")
    with pytest.raises(ValueError, match="allow_reencode"):
        embed_file(source, record, output_path=tmp_path / "rejected.avif")
    _roundtrip(
        source,
        tmp_path / "out.avif",
        record,
        allow_reencode=True,
    )


@pytest.mark.parametrize("suffix", ["png", "jpg", "tif", "webp", "avif"])
def test_save_figure_records_completed_raster_resolution(tmp_path, record, suffix):
    from matplotlib.figure import Figure

    figure = Figure(figsize=(2, 1))
    output = tmp_path / f"rendered.{suffix}"
    save_figure(figure, output, record=record, dpi=300)
    records, manifest = extract_records(output, include_manifest=True)
    render = manifest.records[0].render
    assert render["requested_dpi"] == 300
    assert render["width_px"] == 600
    assert render["height_px"] == 300
    if "actual_dpi_x" in render:
        assert render["actual_dpi_x"] == pytest.approx(300, abs=1.0)
    assert validate_artifact(output).valid


def test_mixed_format_publication_outputs_safe_csvs(tmp_path, record):
    from PIL import Image

    svg_source = tmp_path / "figure-a.svg"
    svg_source.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    embed_file(svg_source, record)
    second = build_record(
        title="Second",
        producer={"package": "test", "version": "1.2.3"},
        plotted_data=[{"group": "A", "value": 3.0}],
        statistics=[{"test": "descriptive", "n": 1}],
        column_classification={"group": "safe", "value": "safe"},
    )
    png_source = tmp_path / "figure-b.png"
    Image.new("RGB", (4, 3), "blue").save(png_source, dpi=(300, 300))
    embed_file(png_source, second)
    result = publish_artifacts(
        [svg_source, png_source],
        output_dir=tmp_path / "publication",
        figure_profile="minimal_public",
        safe_columns=["group", "value"],
    )
    assert result.valid
    assert len(result.artifact_paths) == 2
    assert len(result.csv_paths) == 4
    assert all(
        extract_records(path)[0].distribution_profile == "minimal_public"
        for path in result.artifact_paths
    )
