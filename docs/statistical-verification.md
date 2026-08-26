# Independent statistical verification

ReproFig recalculates a declared numerical problem. It does not infer a test
from a label and does not judge whether the declared test was scientifically
appropriate.

Install the complete verifier with `pip install "reprofig[proof]"`.

## Supported versioned algorithms

- Descriptive summaries: `descriptive/v1`.
- t tests: `one-sample-t/v1`, `paired-t/v1`, `student-t/v1`, `welch-t/v1`.
- Rank tests: `mann-whitney/v1`, `wilcoxon/v1`, `kruskal-wallis/v1`.
- Analysis of variance: `one-way-anova/v1`, `welch-anova/v1`.
- Regression: `ols/v1` over an explicit frozen design matrix.
- Resampling: `bootstrap-mean/v1`, `permutation-mean-difference/v1`.
- Multiplicity: `bonferroni/v1`, `holm/v1`, `benjamini-hochberg/v1`.

Unknown versions are `unsupported`; they are never matched approximately to a
known implementation.

## Complete specification

Each typed specification records input values or table/column selectors,
every answer-changing parameter, expected exact outputs, tolerances and an
optional versioned display formatter. Required choices include missing-value
policy, alternative hypothesis, confidence level, pairing identity, rank-test
method and continuity rules, correction-family identity and complete members,
regression covariance/missing/rank conventions, and the exact resampling plan
or named generator plus seed.

```python
from reprofig import StatisticalSpecification

spec = StatisticalSpecification(
    statistic_id="comparison-01",
    algorithm_id="welch-t/v1",
    inputs={
        "values_a": [1.2, 1.4, 1.7],
        "values_b": [2.0, 2.1, 2.5],
    },
    parameters={
        "alternative": "two_sided",
        "missing_policy": "omit",
        "confidence_level": 0.95,
    },
    expected={"statistic": -4.160251, "p_value": 0.016219},
    tolerances={"*": {"absolute": 1e-12, "relative": 1e-9}},
    display={
        "field": "p_value",
        "format": "p_equals_4dp/v1",
        "text": "p = 0.0162",
    },
)
```

Table selectors bind an input to an exact table SHA-256, optional column and
explicit row condition. Protected input reports `inaccessible` until an
authorized decryption key is supplied.

## Meanings

`statistics_independently_verified` means the reference implementation matched
all declared expected fields within visible tolerances.
`statistics_reproduced` is used when the producer declares the same ReproFig
reference implementation, so numerical agreement is not presented as an
independent route. These meanings concern numbers, not whether a second figure
was saved; that separate operation is `figure_reproduced`. A missing typed
specification is `unavailable`; an unknown algorithm is `unsupported`.

Rank results expose tie groups, zero handling and rank sums. Analysis of
variance exposes group sizes, means, variances and degrees of freedom.
Regression exposes coefficients, standard errors, residual variance and
contrasts. Correction outputs map adjusted values back to stable member IDs;
removing a family member makes the declared result fail.

Embedded resampling index plans are portable. Seed-only plans explicitly name
`python-mt19937/v1` and reproduce that generator rather than claiming general
cross-runtime independence. Iteration, matrix and index-plan limits are checked
before large allocation.

SciPy supplies maintained distribution-tail and rank routines; ReproFig owns
the declared formulas, inputs, intermediate comparisons and verification
report. Numerical agreement still cannot establish data truth, causal meaning,
absence of selection bias or method suitability.
