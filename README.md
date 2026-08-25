# ReproFig

ReproFig makes a scientific figure carry the exact comma-separated values
(CSV), statistics, software version, source fingerprints, and reproduction
instructions needed to audit it later. The same `reprofig/1` record works in
SVG, PDF, PNG, JPEG, TIFF, WebP, AVIF/HEIF, PowerPoint, Word, Excel, HTML,
HDF5, netCDF-4, FITS, and deterministic ZIP/RO-Crate bundles.

```console
python -m pip install reprofig
```

ReproFig requires Python 3.10 or newer. The core has no required scientific
stack. Install every binary adapter with:

```console
python -m pip install "reprofig[all-formats,matplotlib,pandas]"
```

## Create a master figure

```python
from reprofig import save_figure

save_figure(
    figure,
    "Figure 1.pdf",
    plotted_data=dataframe,
    statistics=records,
    producer={"package": "my-analysis", "version": "1.4.0"},
    figure_profile="master",
)
```

A `master` embeds the exact CSV bytes used for the plot. This is the auditable
source of truth and may contain private data or local paths, so do not upload it
without checking it first. Sidecar files are optional and can be regenerated:

```python
from reprofig import extract_artifact, publish_artifacts

extract_artifact("Figure 1.pdf", "Figure 1 extracted")
publish_artifacts(
    ["Figure 1.pdf", "Figure 2.jpg", "Slides.pptx"],
    output_dir="Publication",
    figure_profile="public",
    safe_columns=["condition", "value"],
)
```

## Integrate another plotting package

Attach the plot meaning before its normal save step:

```python
from reprofig import attach, save_figure

attach(
    figure,
    plotted_data=analysis_rows,
    statistics=statistical_records,
    analysis={"independent_unit": "participant"},
    column_classification={
        "condition": "safe",
        "value": "safe",
        "participant_id": "private",
    },
)
save_figure(
    figure,
    "Figure.png",
    producer={"package": "my-analysis", "package_version": "2.1.0"},
    render_preset="line_art",
)
```

New raster figures default to 300 dots per inch (DPI). Use `screen` for 150
DPI, `continuous_tone` for 300 DPI, `line_art` for 600 DPI, or pass an exact
`dpi`, `width`, and `height`. Existing raster files are never resampled by
`embed_file`; AVIF/HEIF metadata changes require `allow_reencode=True` because
the available backend must rebuild those images.

## Make publication-safe copies

The `public` profile retains only explicitly approved columns and source links.
The `minimal_public` profile retains summary statistics and provenance without
row-level data. Both are one-way derivatives of the master:

```text
reprofig publish Figure.svg Figure.jpg --output-dir Submission \
  --profile minimal-public --safe-columns condition,value \
  --public-source dataset=https://repository.example/data.csv
```

The command-line interface also provides `formats`, `inspect`, `validate`,
`embed`, `extract`, `caption`, `scan`, `bundle`, and `fsb-export`. Run
`reprofig formats` to see optional dependencies and carrier capabilities.

Embedded metadata can be stripped by editors, social platforms, publisher
pipelines, or format conversion. Keep the master. When the delivery route is
unknown, send a `.reprofig.zip` bundle alongside the visible figure; its fixed
layout and SHA-256 checksums make missing or changed files detectable.

## Develop and verify

```console
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

Report problems through the [GitHub issue tracker](https://github.com/Jay2owe/ReproFig/issues).
Please cite ReproFig using the metadata in `CITATION.cff`.

ReproFig is licensed under the BSD 3-Clause licence.
