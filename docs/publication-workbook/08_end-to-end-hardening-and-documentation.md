# Stage 08 — Harden and document the complete publication-workbook workflow

## Why this stage exists

The workbook becomes a journal-facing deliverable, so isolated unit tests are not enough. This stage proves the complete mixed-carrier workflow, records the exact scientific claims the workbook can make and leaves the package buildable for the proof-carrying plan that follows.

## Prerequisites

- Stages 01 through 07 must all be `_COMPLETED`.

## Read first

- `docs/publication-workbook/00_overview.md:1-74`
- `docs/publication-workbook/01_publication-dataset-contract_COMPLETED.md:1-end`
- `docs/publication-workbook/02_batch-record-collection_COMPLETED.md:1-end`
- `docs/publication-workbook/03_statistics-ledger_COMPLETED.md:1-end`
- `docs/publication-workbook/04_excel-rendering_COMPLETED.md:1-end`
- `docs/publication-workbook/05_embedded-evidence-and-validation_COMPLETED.md:1-end`
- `docs/publication-workbook/06_publication-profiles-and-privacy_COMPLETED.md:1-end`
- `docs/publication-workbook/07_python-and-cli-interfaces_COMPLETED.md:1-end`
- `README.md:1-115`
- `docs/schema.md:1-27`
- `docs/carrier_survival.md:1-42`
- `docs/multiformat_embedding_plan.md:266-353`
- `docs/multiformat_embedding_plan.md:526-557`
- `CHANGELOG.md:1-17`
- `pyproject.toml:1-71`
- `tests/test_multiformat.py:1-197`
- `tests/test_profiles_publication.py:1-171`

## Scope

- Add an end-to-end fixture containing mixed SVG, PDF, PNG, Excel and ZIP carriers.
- Include reused source data, duplicate carrier copies, several figure panels, displayed and unplotted tests, adjusted probabilities, confidence intervals and missing fields.
- Prove exact CSV extraction, deterministic logical identity, workbook sheet mapping and statistics-ledger reconciliation.
- Test master, public and minimal-public builds from fresh inputs.
- Test visible-cell, index, statistics and embedded-record tampering.
- Test formula-shaped text, long exact decimals, Unicode, duplicate names and Excel limits.
- Document the Python and command-line workflows for figure-only and analysis-complete workbooks.
- Lead documentation with the unchanged basic save-and-extract workflow, then present the workbook as a separate opt-in publication task.
- Provide a journal handoff guide explaining each sheet and which file/profile to upload.
- State that `analysis_complete` is a declared coverage property and not proof that undisclosed analyses never occurred.
- Document that the workbook checks reported values and evidence integrity but does not yet independently recalculate statistics.
- Run the full test suite, package build, metadata check and clean installation with the Excel extra.
- Record the feature in the changelog without publishing, tagging or pushing.

## Out of scope

- Do not add a new carrier, statistical algorithm, signature or encryption feature.
- Do not integrate external plotting packages here; the later proof-carrying plan owns those repositories and skills.
- Do not upload to the Python Package Index or create a release without a separate explicit request.
- Do not call an Excel workbook the sole archival form; retain the ReproFig ZIP fallback guidance.

## Files touched

| path | change | reason |
|---|---|---|
| `tests/test_publication_workbook_e2e.py` | NEW | Exercise the complete mixed-carrier and ledger workflow. |
| `README.md` | MODIFY | Add the shortest supported workbook examples. |
| `docs/publication_workbook.md` | NEW | Explain sheets, inputs, profiles, coverage and journal handoff. |
| `docs/schema.md` | MODIFY | Reference the publication dataset and aggregate-record extension. |
| `docs/carrier_survival.md` | MODIFY | Describe Excel custom-part survival and ZIP fallback behavior. |
| `CHANGELOG.md` | MODIFY | Record the complete feature and limitations. |
| `pyproject.toml` | MODIFY | Finalize optional-extra metadata if Stage 04 did not already do so. |

## Implementation sketch

The end-to-end test should perform this sequence:

```text
build several ReproFig carriers from known exact tables and statistics
create a complete experiment ledger with one unplotted test
build master publication workbook
validate workbook and extract aggregate record
assert byte-identical unique CSV recovery
assert one statistics row per test and every panel link
build public workbook from fresh master inputs and approved columns
build minimal-public workbook from fresh master inputs
tamper each visible/evidence layer and assert the named failure
```

Documentation examples:

```python
from reprofig import build_publication_workbook

result = build_publication_workbook(
    "figures/",
    "Publication-source-data.xlsx",
    experiment_statistics="analysis/all-tests.json",
)
```

```text
reprofig publication-workbook figures/ \
  --statistics-ledger analysis/all-tests.json \
  --output Publication-source-data.xlsx
```

Use the repository's actual environment for final checks, including at minimum:

```text
pytest -q
python -m build
python -m twine check dist/*
clean-environment install of the built wheel with [excel]
reprofig publication-workbook --help
```

## Exit gate

1. The mixed-carrier end-to-end test produces one workbook with all unique CSVs and every declared test.
2. Extraction from the workbook reproduces exact CSV bytes and deterministic normalized statistics.
3. Master/public/minimal fixtures prove their complete privacy behavior across the entire Office ZIP package.
4. All tampering fixtures fail at the correct validation layer.
5. README and the journal handoff guide distinguish figure-complete from analysis-complete coverage.
6. Documentation states that Excel cells are projections and embedded ReproFig evidence is canonical.
7. Full tests, package build, metadata validation and clean wheel installation with `[excel]` pass.
8. No release, tag, push or upload occurs during this stage.
9. A clean base-only installation can still save, inspect and extract ordinary ReproFig figures without Excel or proof dependencies.

## Known risks

- Optional carrier fixtures may not be installed in every development environment. Mark dependency-specific cases clearly while keeping a standard-library plus Excel core path mandatory.
- Office applications may strip ReproFig package parts. Document validation after editing and the deterministic ZIP fallback.
- Documentation can overstate completeness. Use the exact coverage vocabulary and preserve its limitations in examples.
