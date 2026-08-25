# Stage 05 — Embed exact evidence and validate the completed workbook

## Why this stage exists

Readable worksheets alone are not archival because Excel may reinterpret values and users may edit cells. This stage makes the workbook a ReproFig carrier: exact unique CSV bytes, normalized statistics and the publication manifest remain extractable, while a workbook-specific validator detects disagreement between visible cells and embedded evidence.

## Prerequisites

- Stages 01 through 04 must be `_COMPLETED`.

## Read first

- `docs/publication-workbook/00_overview.md:1-74`
- `docs/publication-workbook/01_publication-dataset-contract_COMPLETED.md:1-end`
- `docs/publication-workbook/02_batch-record-collection_COMPLETED.md:1-end`
- `docs/publication-workbook/03_statistics-ledger_COMPLETED.md:1-end`
- `docs/publication-workbook/04_excel-rendering_COMPLETED.md:1-end`
- `src/reprofig/artifacts.py:35-209`
- `src/reprofig/artifacts.py:228-293`
- `src/reprofig/schema.py:119-353`
- `src/reprofig/validation.py:99-126`
- `src/reprofig/carriers/office.py:40-211`
- `src/reprofig/carriers/manifest.py:1-191`
- `tests/test_multiformat.py:68-84`

## Scope

- Convert `PublicationDataset` into one aggregate `FigureRecord` compatible with `reprofig/1`.
- Give every unique publication table a unique aggregate table name while preserving original names and occurrences in metadata.
- Store the reconciled normalized statistics in the aggregate record and preserve their raw records in deterministic JSON fields.
- Store publication schema, logical fingerprint, source figure fingerprints, coverage, table/sheet mapping and verification summary in `extensions["publication_workbook"]`.
- Embed that aggregate record into the rendered `.xlsx` through the existing Office carrier adapter.
- Ensure `extract_artifact` regenerates every unique exact CSV and the complete normalized statistics table from the workbook.
- Add workbook validation that compares the visible data/statistics/index sheets to the embedded aggregate record.
- Detect changed cells, removed rows, renamed/missing sheets, altered mappings and replaced embedded records.
- Keep generic `validate_artifact` behavior compatible while exposing workbook-specific checks separately.
- Use a temporary sibling file and promote only after embedding, extraction and worksheet comparison all pass.

## Out of scope

- Do not sign or encrypt the aggregate record; the later proof-carrying plan owns cryptography.
- Do not embed every original figure record and duplicate its data. Preserve source record fingerprints and selected provenance in the aggregate manifest.
- Do not claim that matching visible cells independently verifies a statistical calculation.
- Public/minimal data removal belongs to Stage 06.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/workbook/evidence.py` | NEW | Build the aggregate `FigureRecord` and embed it into Excel. |
| `src/reprofig/workbook/validation.py` | NEW | Compare workbook sheets with embedded canonical evidence. |
| `src/reprofig/workbook/writer.py` | MODIFY | Hand the stable sheet map and cell projections to embedding/validation. |
| `src/reprofig/workbook/__init__.py` | MODIFY | Export evidence construction and workbook validation. |
| `tests/test_publication_workbook_roundtrip.py` | NEW | Prove extraction, cell comparison and tamper detection. |

## Implementation sketch

Build one compatible aggregate record:

```python
def publication_record(dataset: PublicationDataset) -> FigureRecord:
    tables = [
        DataTable(
            name=f"D{index:03d}_{safe_filename_token(original_name)}",
            purpose="publication_source_data",
            sha256=table.sha256,
            row_count=table.row_count,
            column_count=table.column_count,
            columns=table.columns,
            contents=table.contents,
            metadata={
                "publication_table_id": table.table_id,
                "original_names": sorted({o.table_name for o in table.occurrences}),
                "occurrences": [o.to_dict() for o in table.occurrences],
            },
        )
        for index, table in enumerate(dataset.tables, start=1)
    ]
    return FigureRecord(
        figure_id=dataset.publication_id,
        title="Publication source data workbook",
        distribution_profile=dataset.profile,
        producer={"package": "reprofig", "package_version": __version__},
        analysis={"statistics_coverage": dataset.statistics_coverage},
        data_status="complete" if all(t.contents is not None for t in tables) else "incomplete",
        data_tables=tables,
        statistics=[s.to_record() for s in dataset.statistics],
        statistics_status=("complete" if dataset.statistics_coverage != "incomplete" else "incomplete"),
        extensions={"publication_workbook": dataset.manifest_dict()},
    )
```

The validator returns the existing report shape:

```python
def validate_publication_workbook(
    path: str | os.PathLike[str],
    *,
    require_complete: bool = True,
    public_safety: bool | None = None,
) -> ValidationReport:
    ...
```

Validation order:

```text
open valid Excel package
extract and validate aggregate ReproFig record
verify publication manifest fingerprint
verify expected worksheets and headers
compare Data_Index mappings
compare each data sheet to embedded canonical CSV values
compare Statistics and Test_Families to embedded records
run privacy checks when requested
```

The comparison normalizes only the documented display projection, not the embedded CSV bytes. A deliberate Excel numeric convenience cell may differ in representation while its paired exact-text field must match.

## Exit gate

1. Building and extracting a workbook reproduces every unique source CSV byte-for-byte.
2. Extracted normalized statistics reproduce the workbook's complete statistics ledger.
3. The aggregate record fingerprint, publication fingerprint and worksheet mapping agree.
4. Altering a data value, exact probability value, test identifier or index mapping fails workbook validation.
5. Removing or renaming an expected worksheet fails with a precise location.
6. Altering the embedded record fails existing carrier validation before worksheet comparison.
7. No partial destination survives a failed embed or validation.
8. Existing Excel carrier round-trip behavior remains backward compatible.

## Known risks

- Spreadsheet applications may strip unknown package parts on save. A stripped record is reported as missing; the later identity registry provides recovery rather than a false pass.
- Visible numeric cells and exact CSV lexemes have different representations. Compare through explicit projection rules, never ad hoc coercion.
- The aggregate record represents a publication rather than one visual figure. Mark it unambiguously in its extension and preserve `reprofig/1` compatibility until the later schema revision.
