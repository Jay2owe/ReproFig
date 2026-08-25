# Stage 04 — Reconstruct plotted tables from declared sources and transformations

## Why this stage exists

Independent statistics are meaningless if the verifier cannot recover the same analysis rows from the declared source. ReproFig currently fingerprints files and embeds plotted tables, but it does not execute a safe, declarative transformation chain. This stage proves whether the source content actually produces the table used by the figure.

## Prerequisites

- Stages 02 and 03 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 02 and Stage 03 files
- `docs/publication-workbook/02_batch-record-collection_COMPLETED.md:1-end`
- `src/reprofig/workbook/models.py:1-end`
- `src/reprofig/tables.py:1-277`
- `src/reprofig/sources.py:1-94`
- `src/reprofig/schema.py:1-353` plus completed schema additions
- `src/reprofig/verification.py` in its completed Stage 03 form
- `tests/test_sources_cli.py:1-54`
- `tests/test_roundtrip.py:28-159`

## Scope

- Distinguish raw/source tables, analysis tables and plotted tables by explicit identities and purposes.
- Canonicalize source tables while retaining original-byte checksums.
- Add stable row identities that survive deterministic filtering and sorting.
- Implement a safe transformation registry with versioned operations.
- Support the first common deterministic operations: select, rename, cast, filter, drop-missing, sort, group and aggregate.
- Require explicit missing-value and numeric-conversion rules.
- Reconstruct a target table by topologically executing its declared transformation dependencies.
- Compare reconstructed columns, row identities, values, types and canonical hash with the embedded target.
- Emit detailed verification checks at the first divergent operation.
- Reconstruct publication tables through their existing `table_id` and occurrences so duplicate workbook sheets do not create new scientific evidence.

## Out of scope

- Arbitrary embedded Python, R, shell or notebook execution is forbidden.
- Statistical tests belong to Stages 05–08.
- Reproduction of an original producer script remains a separate, weaker future route.
- Privacy-profile handling of encrypted or removed tables belongs to Stage 16.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/transformations.py` | NEW | Versioned safe operation registry and executor. |
| `src/reprofig/tables.py` | MODIFY | Canonical table and stable-row identity helpers. |
| `src/reprofig/sources.py` | MODIFY | Resolve and verify embedded or supplied source content. |
| `src/reprofig/schema.py` | MODIFY | Add table lineage and transformation references if Stage 01 left placeholders. |
| `src/reprofig/verification.py` | MODIFY | Add source-link and reconstructed-table checks. |
| `tests/test_transformations.py` | NEW | Test each operation, lineage and failures. |
| `docs/schema.md` | MODIFY | Document transformation semantics and row identity. |

## Implementation sketch

```python
@dataclass(frozen=True)
class TransformDefinition:
    algorithm: str
    input_count: int | None
    execute: Callable[[list[CanonicalTable], Mapping[str, Any]], CanonicalTable]

TRANSFORMS = Registry()
TRANSFORMS.register("select/v1", select_columns)
TRANSFORMS.register("rename/v1", rename_columns)
TRANSFORMS.register("cast/v1", cast_columns)
TRANSFORMS.register("filter/v1", filter_rows)
TRANSFORMS.register("drop-missing/v1", drop_missing)
TRANSFORMS.register("sort/v1", sort_rows)
TRANSFORMS.register("group-aggregate/v1", group_aggregate)

def reconstruct_table(
    record: FigureRecord,
    table_id: str,
    *,
    supplied_sources: Mapping[str, bytes | Path] | None = None,
) -> ReconstructionResult: ...
```

Filtering must use structured predicates, not evaluated code:

```json
{
  "algorithm": "filter/v1",
  "parameters": {
    "all": [
      {"column": "quality_control_pass", "operator": "eq", "value": true},
      {"column": "amplitude", "operator": "not_missing"}
    ]
  }
}
```

Every operation records its input hashes, parameters, output hash and row-identity behavior. Comparisons report exact string/type mismatches and use explicit numerical tolerances only when the transformation specification allows them.

## Exit gate

1. A source table reconstructs the expected plotted table through a multi-step chain.
2. Changing a filter, missing-value rule, cast, group key or aggregate changes the output hash and fails the expected check.
3. Stable row identities identify which source rows contributed to every unaggregated output row.
4. Aggregate outputs record the contributing row identities or a deterministic contributor-set hash.
5. Unsupported transformation algorithms report `unsupported`; they never execute embedded code.
6. Missing encrypted/private sources report `inaccessible`, not failure or pass.
7. `pytest tests/test_transformations.py tests/test_sources_cli.py -q` passes.
8. A workbook aggregate table and its originating figure table produce one reconstruction result linked to every occurrence.
9. Transformation execution occurs only through an explicit verification request and never during ordinary extraction.

## Known risks

- Spreadsheet-like expression languages easily become arbitrary code. Keep predicates and operations closed, typed and versioned.
- Locale-dependent numeric parsing can produce silent differences. Record decimal, thousands, date and missing-value rules explicitly.
- Aggregation can discard row lineage. Preserve contributor identities or their deterministic set hash with each aggregate.
