# Stage 03 — Build and reconcile the publication statistics ledger

## Why this stage exists

Journal statistics tables need consistent columns even though current figure records accept arbitrary nested dictionaries. They also need an honest distinction between tests visible in figures and all tests declared by an analysis, so this stage normalizes without inventing missing details and retains every unrecognized field.

## Prerequisites

- Stages 01 and 02 must be `_COMPLETED`.

## Read first

- `docs/publication-workbook/00_overview.md:1-74`
- `docs/publication-workbook/01_publication-dataset-contract_COMPLETED.md:1-end`
- `docs/publication-workbook/02_batch-record-collection_COMPLETED.md:1-end`
- `src/reprofig/schema.py:221-353`
- `src/reprofig/tables.py:1-26`
- `src/reprofig/tables.py:160-215`
- `src/reprofig/api.py:163-210`
- `tests/test_roundtrip.py:28-68`
- `tests/test_profiles_publication.py:20-86`

## Scope

- Define the canonical normalized columns for every statistical-test row.
- Preserve exact input lexemes for probability values, statistics, confidence bounds and effect sizes.
- Add separate numeric convenience values only where conversion is lossless enough for Excel display; never replace exact text.
- Preserve the complete original statistical record as deterministic `raw_record_json`.
- Recognize common aliases such as `p`, `p_raw`, `p_adjusted`, `q`, `df`, `degrees_of_freedom`, `n`, `n_a` and nested test records without guessing ambiguous meanings.
- Assign a stable occurrence identifier when a figure statistic has no explicit `test_id`.
- Accept an optional experiment statistics ledger as canonical JSON or import CSV rows without discarding unknown columns.
- Require unique explicit `test_id` values for reconciliation across figures and the experiment ledger.
- Retain ledger tests not displayed in any figure and mark them `displayed=false`.
- Link one shared test to every figure/panel occurrence when its values agree.
- Fail when the same explicit test identifier has conflicting scientific values.
- Define `figure_complete`, `analysis_complete`, `incomplete` and `not_applicable` coverage decisions.
- Represent multiple-comparison families separately from individual rows.

## Out of scope

- Do not independently recalculate tests; proof-carrying Stages 05-08 will later add specifications and reference calculations.
- Do not judge whether the chosen statistical test is scientifically appropriate.
- Do not infer that two records are the same test merely because their values and labels match.
- Do not write Excel sheets; Stage 04 owns worksheet rendering.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/workbook/statistics.py` | NEW | Normalize records, import ledgers and reconcile test identities. |
| `src/reprofig/workbook/models.py` | MODIFY | Finalize statistic, test-family and coverage fields. |
| `src/reprofig/workbook/__init__.py` | MODIFY | Export statistics-ledger types inside the subsystem. |
| `tests/test_publication_statistics.py` | NEW | Cover exact values, aliases, reconciliation and coverage honesty. |
| `docs/publication_workbook_schema.md` | MODIFY | Publish the ledger columns and completeness semantics. |

## Implementation sketch

The canonical row contains at least:

```text
test_id, analysis_id, figure_ids, panel_ids, claim_ids, displayed,
outcome, group_a, group_b, unit_of_analysis,
n_total, n_group_a, n_group_b, n_pairs, n_excluded,
test_name, test_version, paired, alternative, alpha,
statistic_name, statistic_exact, statistic_numeric,
df_exact, df1_exact, df2_exact,
p_raw_exact, p_raw_numeric, p_adjusted_exact, p_adjusted_numeric,
p_displayed, correction, correction_family_id,
ci_level, ci_low_exact, ci_high_exact, ci_method,
effect_size_name, effect_size_exact, effect_ci_low_exact, effect_ci_high_exact,
missing_policy, model_formula, covariates_json,
random_seed, resamples, producer_package, producer_version,
source, reconciliation_status, raw_record_json
```

Preserve exact and displayed values independently:

```python
PublicationStatistic(
    test_id="welch-control-treatment",
    normalized={
        "p_raw_exact": "0.0000001234567890123",
        "p_raw_numeric": 1.234567890123e-7,
        "p_displayed": "p < 0.001",
        "alternative": "two_sided",
    },
    raw_record={...},
)
```

The canonical experiment-ledger form is:

```json
{
  "schema": "reprofig-statistics-ledger/1",
  "analysis_id": "experiment-2026-08",
  "coverage": "complete",
  "statistics": [{"test_id": "test-001", "test_name": "Welch t-test"}],
  "families": [{"family_id": "family-001", "correction": "Holm"}]
}
```

A bare CSV may be imported, but it earns `analysis_complete` only when the caller makes and records an explicit completeness declaration. Reconciliation rules are:

```text
displayed test_id absent from declared-complete ledger -> error
same test_id with differing normalized/raw values       -> error
ledger-only test                                       -> retain, displayed=false
same test_id in several panels with agreeing values    -> one row, several occurrences
figure statistic without test_id                       -> unique figure occurrence, no cross-figure merge
```

## Exit gate

1. Existing nested and flat ReproFig statistic fixtures normalize without losing any original field.
2. Probability values with more than 15 significant digits survive in exact-text columns unchanged.
3. `p_raw_exact`, `p_adjusted_exact` and `p_displayed` cannot overwrite one another.
4. A shared explicit test used in several panels becomes one row with all occurrences.
5. Conflicting values under one explicit test identifier fail deterministically.
6. An experiment-complete ledger retains unplotted tests and rejects displayed tests absent from the ledger.
7. A figure-only batch never reports `analysis_complete`.
8. CSV and JSON ledger imports preserve unknown fields in `raw_record_json`.

## Known risks

- Current arbitrary statistics dictionaries cannot guarantee every journal field. Leave unavailable values blank and report them; never infer them from names.
- Python floats may already have lost producer precision before ReproFig receives them. Preserve the received lexical representation and document that limitation.
- A completeness declaration is an assertion, not proof that undisclosed analyses never occurred. Record who or what made the declaration.
