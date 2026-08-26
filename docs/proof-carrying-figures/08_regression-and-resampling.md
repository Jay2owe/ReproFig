# Stage 08 — Verify ordinary regression and deterministic resampling

## Why this stage exists

Regression, bootstrap intervals and permutation tests appear frequently in figures but have more hidden choices than simple group comparisons. This stage supports a bounded, explicit subset and establishes how ReproFig reports complex analyses it cannot independently reproduce. Honest unsupported status is part of the proof system.

## Prerequisites

- Stages 05 and 06 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 05 and Stage 06 files
- `docs/publication-workbook/03_statistics-ledger_COMPLETED.md:1-end`
- `src/reprofig/stats/specs.py` in its completed form
- `src/reprofig/stats/engine.py` in its completed form
- `src/reprofig/verification.py` in its completed form
- `docs/statistical-verification.md` in its completed form
- `pyproject.toml:1-71` plus Stage 06 optional dependencies

## Scope

- Add ordinary least-squares regression from an explicit design matrix.
- Record formula text as description but verify the frozen design matrix actually used.
- Verify coefficients, residual variance, standard errors, test statistics, degrees of freedom, confidence intervals and requested contrasts.
- Add deterministic bootstrap and permutation specifications.
- Prefer embedded resample/permutation index plans for cross-runtime independence.
- When only a random seed is stored, record the exact random-number generator and version and downgrade portability honestly.
- Enforce limits on rows, columns, iterations and embedded index-plan size.
- Define unsupported/statistics-reproduced-only reporting for mixed models, generalized models and optimizer-dependent fits not implemented by the reference engine.
- Preserve complete intermediate outputs needed to locate disagreement.
- Attach supported, statistics-reproduced-only or unsupported outcomes to existing publication test identifiers without changing workbook creation requirements.

## Out of scope

- Mixed-effects, generalized linear, survival and Bayesian models are not independently implemented in this stage.
- Model-choice appropriateness and causal interpretation remain human judgements.
- Visual regression-line geometry belongs to Stages 09–12.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/stats/regression.py` | NEW | Ordinary least-squares and contrast reference calculations. |
| `src/reprofig/stats/resampling.py` | NEW | Deterministic bootstrap and permutation plans. |
| `src/reprofig/stats/registry.py` | MODIFY | Register bounded regression and resampling specifications. |
| `src/reprofig/stats/engine.py` | MODIFY | Dispatch and independence-grade logic. |
| `src/reprofig/verification.py` | MODIFY | Report supported, statistics-reproduced-only and unsupported analyses. |
| `tests/test_statistics_models.py` | NEW | Cover design matrices, contrasts, resample plans and limits. |
| `docs/statistical-verification.md` | MODIFY | Publish supported boundaries and required evidence. |

## Implementation sketch

Regression evidence freezes the numerical problem:

```json
{
  "algorithm": "ordinary-least-squares/v1",
  "inputs": {
    "table_id": "analysis-table",
    "response": "amplitude",
    "design_matrix_table_id": "model-matrix",
    "coefficient_names": ["intercept", "treated", "age"]
  },
  "parameters": {
    "covariance": "classical",
    "missing": "complete_rows",
    "rank_tolerance": 1e-12
  }
}
```

Resampling evidence should carry the choices needed to select the same observations:

```json
{
  "algorithm": "bootstrap-percentile/v1",
  "iterations": 10000,
  "unit": "participant",
  "index_plan_table_id": "bootstrap-indices",
  "confidence_level": 0.95
}
```

If the index plan is too large, permit a generator identity and seed but mark cross-implementation independence according to whether the verifier implements that exact generator.

```python
SUPPORTED = {"ordinary-least-squares/v1", "bootstrap-percentile/v1", "permutation-label/v1"}
REPRODUCED_ONLY = {"mixed-model/*", "generalized-linear-model/*", "bayesian/*"}
```

Do not wildcard-match an unknown version into a supported calculation; the notation above is documentation shorthand only.

## Exit gate

1. Ordinary least-squares fixtures reproduce coefficients and all declared intermediate values from the frozen design matrix.
2. A changed category encoding or row order changes the design-matrix hash and fails before coefficient comparison.
3. Bootstrap and permutation results reproduce exactly when an index plan is embedded.
4. Seed-only reproduction records its generator dependency and never overstates portability.
5. Size and iteration limits fail before excessive allocation or execution.
6. A mixed-model record remains extractable and can be labelled statistics-reproduced, but cannot receive independent verification from this engine.
7. `pytest tests/test_statistics_models.py tests/test_statistics_common.py -q` passes.

## Known risks

- Formula parsers encode categories and interactions differently. Verify a frozen design matrix and retain formula text only as human context.
- Resampling index plans can be large. Compress at the carrier layer and enforce declared uncompressed limits.
- Optimizer-dependent models can agree numerically for the wrong reason or diverge harmlessly. Do not claim independent verification without a normative algorithm.
