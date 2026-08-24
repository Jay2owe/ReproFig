# ReproFig

ReproFig makes a scientific Scalable Vector Graphics (SVG) figure carry the
exact analysis-ready comma-separated values (CSV) tables, statistics, software
version, and source fingerprints needed to audit and reproduce it later. It can
extract those records and create privacy-checked publication copies without
altering the internal master.

```console
python -m pip install reprofig
```

ReproFig requires Python 3.10 or newer. The core has no required scientific
stack; install optional adapters with `reprofig[matplotlib,pandas,rocrate]`.

## Create a master figure

```python
from reprofig import save_svg

save_svg(
    figure,
    "Figure 1.svg",
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
from reprofig import extract_figure, publish_figures

extract_figure("Figure 1.svg", "Figure 1 extracted")
publish_figures(
    "Figure 1.svg",
    output_dir="Publication",
    figure_profile="public",
    safe_columns=["condition", "value"],
)
```

## Integrate another plotting package

Attach the plot meaning before its normal save step:

Other plotting packages can attach meaning before their normal save step:

```python
from reprofig import attach, save_svg

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
save_svg(
    figure,
    "Figure.svg",
    producer={"package": "my-analysis", "package_version": "2.1.0"},
)
```

## Make publication-safe copies

The `public` profile retains only explicitly approved columns and source links.
The `minimal_public` profile retains summary statistics and provenance without
row-level data. Both are one-way derivatives of the master:

```text
reprofig publish Figure.svg --output-dir Submission \
  --profile minimal-public --safe-columns condition,value \
  --public-source dataset=https://repository.example/data.csv
```

The command-line interface also provides `inspect`, `validate`, `extract`,
`caption`, `scan`, and `fsb-export`. ReproFig uses the `reprofig/1` record schema,
reads legacy pre-release records, and can import or export Figure-Statistics
Bundle directories and Research Object Crates.

## Develop and verify

```console
python -m pip install --upgrade build twine
python -m build
python -m twine check dist/*
```

Report problems through the [GitHub issue tracker](https://github.com/Jay2owe/ReproFig/issues).
Please cite ReproFig using the metadata in `CITATION.cff`.

ReproFig is licensed under the BSD 3-Clause licence.
