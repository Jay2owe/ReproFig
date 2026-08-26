# Diverse single-figure verification workflows

Each folder is one self-contained example: one figure, one statistical test,
one plotting library, and one complete verification workflow. The synthetic
data make no scientific claim.

| folder | plotting library | figure | statistical test |
|---|---|---|---|
| `matplotlib-paired-change` | Matplotlib | paired slope plot | Wilcoxon signed-rank test |
| `seaborn-regression` | Seaborn | scatter plot with fitted line | ordinary least-squares regression |
| `plotly-multigroup` | Plotly | box plots with raw observations | one-way analysis of variance |

Open each folder's `presentation/index.html` for the clean figure, the
verification result, the workflow, and a PNG of the syntax-highlighted exact
producer code beside the result. An editable SVG is supplied beside every PNG.
The private master, copied input, exact plotted table, exact statistics,
reproduction report, separately reproduced carrier, and unpacked evidence stay
beside that presentation.

The producers use the public one-call interface. They pass ordinary rows,
source paths, statistics, and typed statistical specifications to
`save_figure`; ReproFig serializes JSON, fingerprints every input, discovers
package versions, captures the script, and builds the evidence graph internally.

Each `code-figure/` folder is a separate registered `plot-that` bundle. It
contains the exact source copy, the copied code renderer, a per-line data table,
and SVG and 2x PNG variants sharing one ReproFig figure identity.

Build every example from the repository root with:

```text
python examples/diverse-verification-workflows/code/build_examples.py --register
```

Install the presentation dependencies with:

```text
python -m pip install -r examples/diverse-verification-workflows/requirements.txt
```

Plotly's static PNG export uses Kaleido and a local Chrome or Chromium browser.
Run `plotly_get_chrome` if the Plotly producer reports that no browser is
available.
