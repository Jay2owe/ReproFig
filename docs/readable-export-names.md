# Readable export names

ReproFig keeps permanent figure identifiers inside its records while giving
files short human-readable names. An identifier appears in a filename only to
resolve a collision.

## Name selection

The automatic stem uses the first available value:

1. explicit `export_name`;
2. the record's original figure stem;
3. the current artifact stem;
4. the figure title; or
5. `figure`.

Names are lowercase ASCII, use hyphens between words, and limit the human stem
to 80 characters. Reserved Windows device names receive a `figure-` prefix.

```python
from reprofig import extract_artifact, publish_artifacts, reproduce_figure

extract_artifact(
    "Figure 1.svg",
    "unpacked",
    export_name="paired-change",
)

publish_artifacts(
    "Figure 1.svg",
    output_dir="public",
    export_name="paired-change",
    safe_columns=["condition", "value"],
)

reproduce_figure(
    "Figure 1.svg",
    bundle_root="bundle",
    output_dir="bundle/verification/reproduced",
    export_name="paired-change",
    execute_trusted_producer=True,
)
```

## Output roles

| Role | Example |
|---|---|
| public carrier | `paired-change-public.svg` |
| minimal-public carrier | `paired-change-minimal-public.svg` |
| reproduced carrier | `paired-change-reproduced.svg` |
| embedded record | `paired-change-record.json` |
| plotted table | `paired-change-figure-data.csv` |
| statistics | `paired-change-statistics.csv` |
| producer script | `paired-change-plot.py` |
| rendered producer | `paired-change-code.html` |
| verification report | `paired-change-verification-report.json` |

Batch exports that would otherwise collide append the first eight characters
of the permanent figure identifier, for example
`paired-change-8e6d9973-public.svg`.

## Compatibility

Readable naming is the default for new automatic exports. It does not rename a
master path explicitly supplied to `save_figure`, a workbook path supplied to
`build_publication_workbook`, or standardized internal plot-that bundle inputs.

Pass `naming="legacy"` in Python or `--naming legacy` on the command line to
retain identifier-prefixed extraction names and dotted suffixes. Embedded
records and existing files remain readable in either mode.
