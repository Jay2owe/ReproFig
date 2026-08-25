# Stage 05 — Define the versioned statistical specification registry

## Why this stage exists

An exact probability value cannot be independently checked from a test name alone. Pairing, tails, missing data, tie rules, variance assumptions and correction families all change the answer. This stage defines a closed, versioned vocabulary that records the complete statistical question before any reference calculation is added.

## Prerequisites

- Stages 01 and 03 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 01 and Stage 03 files
- `docs/publication-workbook/03_statistics-ledger_COMPLETED.md:1-end`
- `src/reprofig/schema.py:1-353` plus completed schema additions
- `src/reprofig/workbook/models.py:1-end`
- `src/reprofig/workbook/statistics.py:1-end`
- `src/reprofig/tables.py:1-277`
- `src/reprofig/validation.py:1-246`
- `tests/test_profiles_publication.py:66-94`
- `docs/schema.md:1-27` plus completed additions

## Scope

- Define a registry of statistical algorithm specifications, separate from their implementations.
- Require stable algorithm identifiers such as `welch-t/v1` rather than free-text names.
- Declare required input roles, parameters, intermediate values and expected outputs for each algorithm.
- Record independent unit, grouping, pairing, missing-value, alternative-hypothesis and confidence-level choices.
- Represent multiple-comparison families explicitly.
- Record exact unrounded results separately from display formatting.
- Record numerical comparison tolerances by output field.
- Validate that every displayed statistical annotation refers to one registered result identity.
- Preserve unknown producer statistics as untyped legacy results without promoting them to independently verifiable specifications.
- Reuse each publication ledger `test_id` as the statistical specification identity and retain blank journal fields when no specification supplies them.

## Out of scope

- Calculation implementations belong to Stages 06–08.
- Visual position and geometry links belong to Stage 09.
- Judging whether a test is scientifically appropriate remains human review.
- Do not infer a specification by parsing plot labels.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/stats/__init__.py` | NEW | Public statistical specification namespace. |
| `src/reprofig/stats/specs.py` | NEW | Typed input, parameter, result and display specifications. |
| `src/reprofig/stats/registry.py` | NEW | Versioned algorithm registry and capability discovery. |
| `src/reprofig/schema.py` | MODIFY | Bind proof-carrying records to typed statistical specifications. |
| `src/reprofig/workbook/statistics.py` | MODIFY | Attach optional typed specifications to publication tests without changing loose-record imports. |
| `src/reprofig/validation.py` | MODIFY | Validate registry identity, completeness and result bindings. |
| `tests/test_statistical_specs.py` | NEW | Freeze complete and incomplete specification behavior. |
| `docs/statistical-verification.md` | NEW | Document meanings, requirements and unsupported legacy records. |

## Implementation sketch

```python
@dataclass(frozen=True)
class StatisticalAlgorithm:
    algorithm: str
    input_roles: tuple[str, ...]
    required_parameters: tuple[str, ...]
    required_intermediates: tuple[str, ...]
    required_outputs: tuple[str, ...]
    supports_pairing: bool = False
    supports_exact: bool = False

class StatisticalRegistry:
    def register(self, definition: StatisticalAlgorithm) -> None: ...
    def get(self, algorithm: str) -> StatisticalAlgorithm: ...
    def describe(self) -> list[dict[str, Any]]: ...
```

A complete record should resemble:

```json
{
  "statistic_id": "comparison-01",
  "algorithm": "welch-t/v1",
  "inputs": {
    "table_id": "analysis-table",
    "value_column": "amplitude",
    "group_column": "treatment",
    "groups": ["control", "treated"]
  },
  "parameters": {
    "alternative": "two_sided",
    "missing": "drop_per_group",
    "confidence_level": 0.95,
    "variance_ddof": 1
  },
  "expected": {
    "n": [12, 11],
    "means": [1.214, 1.531],
    "difference": 0.317,
    "statistic": 3.214582,
    "degrees_of_freedom": 19.7341,
    "p_unadjusted": 0.004182,
    "p_adjusted": 0.012546
  },
  "display": {
    "annotation_id": "comparison-01-label",
    "text": "p = 0.0125",
    "format": "p_equals_4dp/v1"
  }
}
```

Correction specifications identify the entire family by statistic identities and preserve family order where the method uses it. Formatting is also versioned so the verifier can distinguish an exact calculation mismatch from a text-rounding mismatch.

## Exit gate

1. Registry discovery lists every supported specification without importing calculation dependencies.
2. A Welch test missing its alternative, missing-value rule or variance convention fails specification validation.
3. A paired test without a pairing identity fails validation.
4. An adjusted probability without a complete correction-family reference fails validation.
5. Exact numeric results and display text remain separate fields.
6. Legacy opaque statistics remain readable and report `unsupported` for independent verification.
7. `pytest tests/test_statistical_specs.py tests/test_profiles_publication.py -q` passes.
8. A publication workbook built from loose statistics remains valid with independent verification marked unsupported rather than failing construction.

## Known risks

- Library function names are not stable scientific definitions. Use ReproFig algorithm identities and map producer calls to them.
- Defaults hidden in producer libraries will cause false disagreements. Required parameters must include every answer-changing choice.
- A registry can accidentally imply methodological endorsement. State that it defines computation, not scientific suitability.
