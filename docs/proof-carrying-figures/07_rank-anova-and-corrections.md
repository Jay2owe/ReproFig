# Stage 07 — Verify rank tests, one-way analysis of variance and corrections

## Why this stage exists

Many publication figures use non-parametric comparisons, more than two groups or adjusted probability values. Those results depend on tie behavior, exact-versus-asymptotic choices and the complete correction family. This stage extends the reference engine without allowing an isolated adjusted value to masquerade as independently checked.

## Prerequisites

- Stages 05 and 06 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 05 and Stage 06 files
- `docs/publication-workbook/03_statistics-ledger_COMPLETED.md:1-end`
- `src/reprofig/stats/specs.py` in its completed form
- `src/reprofig/stats/registry.py` in its completed form
- `src/reprofig/stats/engine.py` in its completed form
- `tests/fixtures/statistics-common-v1.json` in its completed form
- `docs/statistical-verification.md` in its completed form

## Scope

- Add Mann–Whitney, Wilcoxon signed-rank and Kruskal–Wallis specifications and reference calculations.
- Add one-way ordinary and Welch analysis-of-variance calculations.
- Record and verify ranking, zero-difference, tie, continuity and exact/asymptotic choices.
- Add Bonferroni, Holm and Benjamini–Hochberg correction families.
- Require every member and ordering input needed by the selected correction.
- Compare raw and adjusted values separately.
- Preserve test statistics, degrees of freedom and correction intermediates.
- Add deterministic cross-implementation fixtures with ties, zeros and duplicated probability values.
- Report each check under the publication ledger's existing test and correction-family identities.

## Out of scope

- Post-hoc procedures not named in the approved scope remain unsupported rather than inferred.
- Regression and resampling belong to Stage 08.
- The verifier does not decide whether parametric or rank testing was scientifically preferable.
- Plot geometry remains Stages 09–12.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/stats/rank.py` | NEW | Reference rank-test calculations and tie rules. |
| `src/reprofig/stats/anova.py` | NEW | Ordinary and Welch one-way analysis of variance. |
| `src/reprofig/stats/corrections.py` | NEW | Complete-family probability corrections. |
| `src/reprofig/stats/registry.py` | MODIFY | Register new versioned algorithms and parameters. |
| `tests/fixtures/statistics-groups-v1.json` | NEW | Freeze edge cases from an independent implementation. |
| `tests/test_statistics_groups.py` | NEW | Exercise calculations and correction-family integrity. |
| `docs/statistical-verification.md` | MODIFY | Document supported methods and exact limitations. |

## Implementation sketch

Correction family representation:

```json
{
  "family_id": "all-treatment-comparisons",
  "algorithm": "holm/v1",
  "members": ["comparison-01", "comparison-02", "comparison-03"],
  "expected_raw": [0.004182, 0.031, 0.42],
  "expected_adjusted": [0.012546, 0.062, 0.42]
}
```

Rank algorithms must emit the actual rank sums, tie groups, zero-difference handling and selected probability route. Exact calculation is permitted only when its declared preconditions hold; otherwise the specification must select the asymptotic route explicitly.

```python
def verify_family(
    family: CorrectionFamily,
    raw_results: Mapping[str, float],
) -> tuple[dict[str, float], list[VerificationCheck]]: ...
```

Never verify an adjusted probability in isolation. If one family member is missing or inaccessible, mark the adjustment unavailable unless the method specification explicitly supports the remaining declared family.

## Exit gate

1. Rank fixtures cover ties, zero differences, exact eligibility, asymptotic behavior and one-sided alternatives.
2. Analysis-of-variance fixtures expose all group counts, means, variances, numerator/denominator degrees of freedom and test statistics.
3. Reordering a Holm or Benjamini–Hochberg family does not change correctly identity-mapped outputs.
4. Removing one correction-family member prevents an independently verified adjusted result.
5. Raw and adjusted display annotations bind to distinct expected fields.
6. Unsupported method variants report `unsupported` with the missing algorithm identity.
7. `pytest tests/test_statistics_groups.py tests/test_statistics_common.py -q` passes.

## Known risks

- “Mann–Whitney” and “Wilcoxon” names are used inconsistently across libraries. Versioned specifications must define the precise calculation.
- Exact algorithms can become expensive. Enforce size limits and report when the declared route exceeds them.
- False-discovery corrections depend on the scientific family definition, which software cannot infer. Require the producer to declare it.
