# Stage 04 — Render the publication dataset as readable Excel worksheets

## Why this stage exists

The canonical dataset must become a workbook that researchers and journals can inspect without ReproFig. This stage builds readable sheets while keeping the archival CSV and statistical values untouched for the embedding and verification stage that follows.

## Prerequisites

- Stages 01 through 03 must be `_COMPLETED`.

## Read first

- `docs/publication-workbook/00_overview.md:1-74`
- `docs/publication-workbook/01_publication-dataset-contract_COMPLETED.md:1-end`
- `docs/publication-workbook/03_statistics-ledger_COMPLETED.md:1-end`
- `src/reprofig/tables.py:27-159`
- `src/reprofig/carriers/office.py:1-211`
- `src/reprofig/carriers/registry.py:22-67`
- `pyproject.toml:1-71`
- `tests/test_multiformat.py:68-84`

## Scope

- Add an optional `excel` dependency group using a maintained `.xlsx` library; use `openpyxl` unless repository compatibility testing identifies a blocker.
- Create a new workbook from `PublicationDataset` without macros, formulas, external links or external data connections.
- Write sheets in this fixed order: `README`, `Figures`, `Data_Index`, `Statistics`, `Test_Families`, `Verification`, `Dictionary`, then data sheets.
- Assign deterministic, Excel-safe data sheet names such as `D001_<slug>` and map them in `Data_Index`.
- Write one sheet for each unique embedded CSV table and preserve every figure occurrence in the index.
- Write normalized statistical columns in a documented stable order, with exact text next to optional numeric convenience columns.
- Use explicit text cells for formula-shaped source values so spreadsheet software cannot execute them.
- Add minimal journal-friendly formatting: frozen headers, filters, readable widths, wrapped explanatory text and no decorative charting.
- Set stable document properties and deterministic logical ordering.
- Detect Excel row, column, cell-length and worksheet-name limits before writing; fail without partial output.
- Treat a missing row-level table as an indexed unavailable table, not as an empty dataset.

## Out of scope

- Do not embed ReproFig records yet; Stage 05 owns package embedding.
- Do not compare worksheets back to evidence yet; Stage 05 owns validation.
- Do not remove private columns; Stage 06 transforms profiles before this writer runs.
- Do not create one enormous long-format sheet by default. The workbook is the combined file; unique tables remain separate readable sheets.
- Do not add charts or figures to the workbook.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/workbook/writer.py` | NEW | Render deterministic worksheet structures and safe cells. |
| `src/reprofig/workbook/__init__.py` | MODIFY | Export the workbook renderer inside the subsystem. |
| `pyproject.toml` | MODIFY | Add optional Excel and development dependencies. |
| `tests/test_publication_workbook_writer.py` | NEW | Check sheet layout, exact fields, safety and Excel limits. |

## Implementation sketch

Keep rendering separate from final embedding:

```python
@dataclass
class WorkbookRenderResult:
    path: Path
    sheet_map: dict[str, str]       # table_id -> worksheet name
    logical_fingerprint: str

def render_workbook(
    dataset: PublicationDataset,
    output_path: str | os.PathLike[str],
    *,
    overwrite: bool = False,
) -> WorkbookRenderResult:
    ...
```

Sheet rules:

```text
README         publication identity, profile, coverage and usage notes
Figures        one row per source figure record
Data_Index     one row per unique table plus occurrence links
Statistics     one row per reconciled test
Test_Families  one row per correction family
Verification   collection and later workbook checks
Dictionary     stable field definitions and units
D001_*         visible projection of the first unique embedded CSV
```

Use the original CSV parser to read visible data, then write values according to declared column types only when safe. Always keep source text available to Stage 05 through the dataset. Exact statistics use text cells:

```python
write_text(cell, statistic.normalized.get("p_raw_exact"))
write_optional_number(next_cell, statistic.normalized.get("p_raw_numeric"))
```

Any input cell starting with `=`, `+`, `-` or `@` is forced to a literal string cell. Generate to a temporary sibling path and replace the destination only after the library can reopen the workbook.

## Exit gate

1. A representative dataset opens with `openpyxl` and contains the fixed sheet order.
2. Every unique embedded table has exactly one visible sheet and every occurrence appears in `Data_Index`.
3. Exact probability and statistic text is unchanged, including values beyond Excel's numeric precision.
4. Formula-shaped CSV values reopen as literal strings and no workbook formula or external link exists.
5. Sheet names are unique, stable, valid and at most 31 characters.
6. Inputs exceeding an Excel limit fail before replacing the destination and identify the offending table/cell.
7. Regenerating from the same canonical dataset produces the same logical sheet map and cell values.
8. Importing `reprofig` without the Excel extra remains successful.

## Known risks

- Excel stores numbers with limited precision. Exact text is authoritative; numeric columns are convenience only.
- Spreadsheet libraries can add volatile package metadata. Do not use the raw `.xlsx` checksum as scientific identity.
- CSV formula injection is possible even in locally generated workbooks. Force dangerous prefixes to literal text and test reopening.
