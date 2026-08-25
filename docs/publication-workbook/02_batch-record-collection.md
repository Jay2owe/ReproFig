# Stage 02 — Collect and deduplicate evidence from a figure batch

## Why this stage exists

The workbook must accept the same mixed carriers and directories that ReproFig already understands, while preserving where every table appeared. This stage converts those inputs into the canonical dataset without silently accepting corrupt records, conflicting figure identities or accidental duplicates.

## Prerequisites

- Stage 01 must be `_COMPLETED`.

## Read first

- `docs/publication-workbook/00_overview.md:1-74`
- `docs/publication-workbook/01_publication-dataset-contract_COMPLETED.md:1-end`
- `src/reprofig/artifacts.py:35-69`
- `src/reprofig/artifacts.py:189-320`
- `src/reprofig/artifacts.py:322-482`
- `src/reprofig/artifacts.py:484-565`
- `src/reprofig/schema.py:119-353`
- `src/reprofig/validation.py:99-126`
- `src/reprofig/carriers/registry.py:74-149`
- `tests/test_multiformat.py:1-197`

## Scope

- Add a collector accepting one path, a sequence of paths or directories containing supported artifacts.
- Reuse ReproFig carrier detection and multi-record extraction, including ZIP/Research Object Crate bundles.
- Promote the current artifact-path expansion behavior to a supported internal helper rather than copying it.
- Validate every extracted record and table hash before adding it.
- Deduplicate byte-identical repetitions of the same figure record while retaining all carrier occurrences.
- Fail when one figure identifier points to different record fingerprints.
- Index unique CSV tables by their embedded SHA-256 hash while retaining each figure/table occurrence.
- Compare bytes as well as declared hashes before accepting a table deduplication.
- Preserve table names, purposes, column specifications and source record fingerprints in the occurrence index.
- Sort outputs deterministically and avoid embedding absolute local artifact paths in the logical dataset.
- Report unsupported, unreadable and incomplete inputs together rather than losing the rest of the batch context.

## Out of scope

- Do not normalize or deduplicate statistical tests; Stage 03 owns that logic.
- Do not create an Excel file; Stage 04 owns rendering.
- Do not derive public profiles; Stage 06 owns privacy transformations.
- Do not silently skip invalid artifacts under the default strict policy.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/artifacts.py` | MODIFY | Expose the existing supported-artifact path expansion as an internal reusable helper. |
| `src/reprofig/workbook/collect.py` | NEW | Extract, validate, deduplicate and index figure records and tables. |
| `src/reprofig/workbook/__init__.py` | MODIFY | Export the internal collector within the workbook subsystem. |
| `tests/test_workbook_collection.py` | NEW | Cover mixed carriers, directories, collisions and table occurrences. |

## Implementation sketch

The collector returns both canonical content and diagnostic provenance:

```python
@dataclass
class CollectedPublication:
    dataset: PublicationDataset
    records: list[FigureRecord]
    artifact_occurrences: list[ArtifactOccurrence]
    reports: list[ValidationReport]

def collect_publication(
    artifacts: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    *,
    publication_id: str | None = None,
    require_complete: bool = True,
) -> CollectedPublication:
    ...
```

Conflict rules:

```text
same figure_id + same record fingerprint    -> one figure, retain both carrier occurrences
same figure_id + different fingerprint      -> error
same table SHA-256 + same exact bytes        -> one table, retain every occurrence
same table SHA-256 + different exact bytes   -> error
missing table contents in required master    -> error
minimal-public table without contents        -> valid only when completeness is not required
```

Use carrier filename and format for human diagnostics, but store absolute resolved paths only in the returned runtime diagnostics. The serialized publication dataset stores safe occurrence labels, figure identifiers and hashes.

## Exit gate

1. One call collects representative SVG, PDF, PNG, Excel and ZIP carriers into a single dataset.
2. A directory and the equivalent explicit path list produce the same logical fingerprint.
3. Repeated copies of one identical figure do not duplicate its data but retain both carrier occurrences.
4. Conflicting records sharing one figure identifier fail before any output is written.
5. Reused identical tables appear once in `tables` and once per use in their occurrence list.
6. Corrupt table bytes or statistics hashes make collection fail with the figure and table identified.
7. No absolute local path enters `PublicationDataset.to_json()`.
8. Existing artifact scanning, extraction and bundle tests remain green.

## Known risks

- Directory recursion can encounter unrelated supported files. The final command must clearly list selected artifacts and fail visibly on invalid candidates.
- Hash equality is normally sufficient, but the collision guard must compare available bytes before merging.
- The same data may be serialized differently across figures. Different bytes remain separate tables even when their parsed values look equal.
