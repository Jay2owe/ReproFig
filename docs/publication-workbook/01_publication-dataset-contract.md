# Stage 01 — Define the canonical publication dataset contract

## Why this stage exists

Every later collector, worksheet and verifier needs one stable description of a publication's figures, unique tables, statistical tests and coverage. Defining that contract first prevents Excel layout decisions from becoming the scientific data model and gives the later proof-carrying plan a clear extension point.

## Prerequisites

- None.

## Read first

- `docs/publication-workbook/00_overview.md:1-74`
- `src/reprofig/schema.py:1-353`
- `src/reprofig/tables.py:1-277`
- `src/reprofig/carriers/manifest.py:1-191`
- `src/reprofig/artifacts.py:35-69`
- `pyproject.toml:1-71`

## Scope

- Create a workbook subpackage that imports without Excel or dataframe dependencies.
- Define `reprofig-publication-workbook/1` as the logical dataset schema identifier; do not change `SCHEMA_ID` or supported figure-record schemas.
- Model the publication, source figures, unique data tables, table occurrences, statistics, test families, verification rows and coverage declaration.
- Give every logical object a stable identifier or deterministic fingerprint.
- Derive a default publication identifier from sorted input evidence rather than output path or creation time.
- Preserve the original source-record fingerprint, table hash, table name, purpose, column metadata and every occurrence.
- Separate `figure_complete`, `analysis_complete`, `incomplete` and `not_applicable` coverage meanings.
- Provide deterministic `to_dict`, `from_dict`, `to_json`, `from_json`, `fingerprint` and structural validation methods.
- Document the logical schema, including which values are archival and which are display conveniences.

## Out of scope

- Artifact discovery and deduplication belong to Stage 02.
- Statistical field normalization and experiment-ledger reconciliation belong to Stage 03.
- Excel creation belongs to Stage 04.
- Do not change `FigureRecord`, `DataTable` or `CarrierManifest` wire formats.
- Do not add signatures, encryption or independent statistical calculation; those belong to the later proof-carrying plan.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/workbook/__init__.py` | NEW | Define the dependency-light workbook subsystem boundary. |
| `src/reprofig/workbook/models.py` | NEW | Hold canonical publication dataset dataclasses and validation. |
| `tests/test_publication_dataset.py` | NEW | Lock deterministic identities, serialization and coverage rules. |
| `docs/publication_workbook_schema.md` | NEW | Document the logical workbook schema and field meanings. |

## Implementation sketch

Use dataclasses and existing deterministic JSON helpers:

```python
WORKBOOK_SCHEMA = "reprofig-publication-workbook/1"

CoverageStatus = Literal[
    "incomplete",
    "figure_complete",
    "analysis_complete",
    "not_applicable",
]

@dataclass
class TableOccurrence:
    figure_id: str
    figure_record_sha256: str
    table_name: str
    table_index: int

@dataclass
class PublicationTable:
    table_id: str                  # "table:" + DataTable.sha256
    sha256: str
    contents: str | None
    format: str
    columns: list[ColumnSpec]
    row_count: int
    column_count: int
    occurrences: list[TableOccurrence]

@dataclass
class PublicationStatistic:
    test_id: str
    raw_record: dict[str, Any]
    occurrences: list[dict[str, Any]]
    displayed: bool
    source: str                    # figure | experiment_ledger | both
    normalized: dict[str, Any] = field(default_factory=dict)

@dataclass
class PublicationDataset:
    publication_id: str
    profile: str
    figures: list[PublicationFigure]
    tables: list[PublicationTable]
    statistics: list[PublicationStatistic]
    test_families: list[TestFamily]
    verification: list[dict[str, Any]]
    statistics_coverage: CoverageStatus
    schema: str = WORKBOOK_SCHEMA

    def evidence_dict(self) -> dict[str, Any]: ...  # excludes build time/path
    def fingerprint(self) -> str: ...               # SHA-256 of evidence_dict
    def validate(self) -> list[str]: ...
```

Identifiers must be namespaced and stable:

```text
publication:<first 24 hexadecimal characters of evidence hash>
table:<full embedded CSV SHA-256>
figure-stat:<figure_id>:<zero-based record index>
```

Do not assign a content-derived identifier to a statistic that already has an explicit `test_id`; Stage 03 owns reconciliation. Serialization sorts figures by `figure_id`, tables by `table_id`, occurrences by figure/table index and statistics by `test_id`.

## Exit gate

1. Importing `reprofig.workbook.models` succeeds with no optional packages installed.
2. Round-tripping a representative `PublicationDataset` through deterministic JSON preserves equality.
3. Reordering input lists does not change its evidence fingerprint after canonical sorting.
4. Changing a table hash, raw statistic or figure-record fingerprint changes the evidence fingerprint.
5. Build time, absolute output path and worksheet styling do not affect the evidence fingerprint.
6. Duplicate identifiers and invalid coverage values produce precise validation failures.
7. Existing schema and application programming interface tests still pass unchanged.

## Known risks

- Treating workbook ZIP bytes as identity would make harmless Excel rewrites appear to change scientific evidence. Keep logical evidence identity separate.
- Overloading `FigureRecord` now would couple this plan to the later schema expansion. Keep these models additive.
- Sorting must not discard display order. Store explicit order fields where journal presentation order matters.
