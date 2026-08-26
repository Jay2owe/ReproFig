# ReproFig

ReproFig makes a figure carry the exact comma-separated values (CSV), optional
statistics, software version, source fingerprints, and reproduction
instructions needed to audit it later. It works for general data figures;
scientific figures and publication workflows are the main use case because
their evidence and reporting requirements benefit most. The same `reprofig/1` record works in
SVG, PDF, PNG, JPEG, TIFF, WebP, AVIF/HEIF, PowerPoint, Word, Excel, HTML,
HDF5, netCDF-4, FITS, and deterministic ZIP/RO-Crate bundles.

```console
python -m pip install reprofig
```

ReproFig requires Python 3.10 or newer. The core has no required scientific
stack. The main installation choices are:

```console
python -m pip install reprofig           # ordinary save, embed, inspect, extract
python -m pip install "reprofig[excel]"  # publication workbooks
python -m pip install "reprofig[proof]"  # workbooks, statistics, visuals, signatures, encryption
```

Carrier-specific extras remain available for PDF, HEIF, HDF5, netCDF and FITS.

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

This ordinary workflow is unchanged and does not activate proof checks,
cryptography, interception, or extra dependencies.

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

### Readable export names

Automatic exports use lowercase hyphenated names such as
`paired-change-record.json`, `paired-change-figure-data.csv`, and
`paired-change-reproduced.svg`. The permanent `rf-...` figure identifier stays
inside the record and is added to a filename only when two readable names
collide.

Pass `export_name="paired-change"` to `extract_artifact`, `publish_artifacts`,
or `reproduce_figure` to override the automatic name. The fallback order is
the explicit export name, original figure stem, current artifact stem, figure
title, then `figure`. Existing automation can request the previous identifier
and dotted-suffix names with `naming="legacy"`; the command-line equivalents
are `--name` and `--naming legacy`.

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

## Build a publication source-data workbook

Combine every unique embedded CSV with a normalized table of all plotted and
unplotted tests:

```python
from reprofig import build_publication_workbook

result = build_publication_workbook(
    "figures/",
    "Publication-source-data.xlsx",
    experiment_statistics="analysis/all-tests.json",
)
```

Set the ledger's coverage to `analysis_complete` only when it intentionally
lists every analysis, including unplotted tests. That is a declaration, not
proof that undisclosed analyses never occurred. See
[`docs/publication_workbook.md`](https://github.com/Jay2owe/ReproFig/blob/main/docs/publication_workbook.md).

## Opt into proof-carrying output

```python
from reprofig import bind_artist, save_figure, verify_proof

bind_artist(line, semantic_id="treated-series", columns=["time", "signal"])
save_figure(
    figure,
    "Figure-1.svg",
    plotted_data=rows,
    statistics=statistics,
    proof=True,
)
report = verify_proof(
    "Figure-1.svg",
    required=["internally_consistent", "display_verified"],
)
```

Complete figure reproduction is deliberately separate because it executes the
embedded producer. It saves a second carrier and a report; later verification
only reads those files and never reruns code:

```python
from reprofig import reproduce_figure

run = reproduce_figure(
    "Figure-1.svg",
    bundle_root="figure-bundle",
    output_dir="figure-bundle/verification/reproduced",
    execute_trusted_producer=True,
)
```

This writes a readable carrier such as `Figure-1-reproduced.svg`; an explicit
`report_path` remains available when a bundle requires a fixed internal report
location.

Use `statistics_reproduced` when declared statistics match the same
implementation, `statistics_independently_verified` when a separate reference
implementation matches, and `figure_reproduced` only when a separately saved
figure also matches. See
[`docs/figure-reproduction.md`](https://github.com/Jay2owe/ReproFig/blob/main/docs/figure-reproduction.md).

Typed statistical specifications can additionally reconstruct declared source
transformations and recalculate supported tests. A passing report proves that
the stated evidence agrees with the output; it does not prove that source data
are true or that the chosen method is scientifically appropriate.

## Presentation-ready examples

[`examples/diverse-verification-workflows`](examples/diverse-verification-workflows)
contains three standalone workflows rather than variations of one plot:

- Matplotlib paired trajectories with a Wilcoxon signed-rank test;
- Seaborn regression with an ordinary least-squares slope test;
- Plotly box plots with raw observations and a one-way analysis of variance.

Each example has one master figure, one statistical result, a separately saved
reproduction, unpacked evidence, and a browser-ready page rendering the clean
figure and its exact syntax-highlighted producer code.

Signatures answer “has this evidence changed since this key signed it?” Trust
stores separately answer “do I accept that key for this purpose?” Individual
tables, statistics, provenance, or specifications can be encrypted for a
password or named X25519 recipient before signing. See
[`docs/proof-carrying-verification.md`](https://github.com/Jay2owe/ReproFig/blob/main/docs/proof-carrying-verification.md)
and [`docs/security.md`](https://github.com/Jay2owe/ReproFig/blob/main/docs/security.md).

## Develop and verify

```console
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

Report problems through the [GitHub issue tracker](https://github.com/Jay2owe/ReproFig/issues).
Please cite ReproFig using the metadata in `CITATION.cff`.

ReproFig is licensed under the BSD 3-Clause licence.
