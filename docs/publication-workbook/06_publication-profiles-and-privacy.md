# Stage 06 — Apply publication profiles and privacy rules to workbooks

## Why this stage exists

A master workbook may legitimately contain participant-level data and private provenance, while a journal upload must contain only approved material. This stage applies ReproFig's one-way profiles before any cells or embedded records are written, preventing hidden sheets or metadata from leaking excluded values.

## Prerequisites

- Stages 01 through 05 must be `_COMPLETED`.

## Read first

- `docs/publication-workbook/00_overview.md:1-74`
- `docs/publication-workbook/02_batch-record-collection_COMPLETED.md:1-end`
- `docs/publication-workbook/05_embedded-evidence-and-validation_COMPLETED.md:1-end`
- `src/reprofig/profiles.py:1-187`
- `src/reprofig/validation.py:17-97`
- `src/reprofig/validation.py:99-126`
- `src/reprofig/validation.py:213-246`
- `src/reprofig/artifacts.py:579-723`
- `tests/test_profiles_publication.py:20-171`
- `tests/test_multiformat.py:169-197`

## Scope

- Accept `master`, `public` and `minimal_public` workbook profiles.
- Apply existing `derive_profile` rules to every source record before collection and rendering.
- Support per-table approved-column mappings, including duplicate table names in different figures through fully qualified keys.
- Make the master workbook contain all available embedded row-level data.
- Make the public workbook contain only explicitly approved safe columns in visible sheets and its aggregate record.
- Make the minimal-public workbook contain no row-level table contents or data worksheets while retaining table identities, dimensions, statistics, public source links and coverage.
- Filter or scrub imported experiment-ledger fields under the same public-safety rules.
- Ensure removed material does not remain in hidden worksheets, shared strings, comments, document properties, relationships or embedded records.
- Validate public workbook package text and embedded records for private paths and credential-shaped strings.
- Refuse attempts to recreate a richer profile from public or minimal-public inputs.
- Preserve a clear derivation record: source profile, target profile, approved fields and source evidence hashes.
- Reserve manifest section names for later selective encryption without exposing placeholder plaintext.

## Out of scope

- Do not implement encryption; proof-carrying Stage 15 will protect selected workbook evidence sections.
- Do not treat encryption as a substitute for removing data from public worksheets.
- Do not automatically classify unknown columns as safe.
- Command-line option design belongs to Stage 07.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/workbook/profiles.py` | NEW | Transform collected records and ledgers before workbook construction. |
| `src/reprofig/workbook/evidence.py` | MODIFY | Embed only profile-approved tables, statistics and manifest fields. |
| `src/reprofig/workbook/writer.py` | MODIFY | Omit unavailable/private data sheets and label profile behavior. |
| `src/reprofig/workbook/validation.py` | MODIFY | Scan visible and hidden Office package content for excluded material. |
| `src/reprofig/workbook/__init__.py` | MODIFY | Export profile-aware build primitives. |
| `tests/test_publication_workbook_profiles.py` | NEW | Test master/public/minimal outputs and leak resistance. |

## Implementation sketch

Transform before collection so unsafe bytes never enter a public dataset:

```python
def prepare_records_for_workbook(
    records: Sequence[FigureRecord],
    *,
    profile: str,
    safe_columns: Mapping[str, Sequence[str]] | None = None,
    public_sources: Mapping[str, str] | None = None,
) -> list[FigureRecord]:
    return [
        derive_profile(
            record,
            profile,
            safe_columns=qualified_safe_columns(record, safe_columns),
            public_sources=public_sources,
        )
        for record in records
    ]
```

Fully qualified table keys use `figure_id/table_name`; an exact qualified key wins over a table-name key, then `*` may provide an explicit fallback.

Profile behavior:

```text
master          visible exact data + embedded exact data + complete internal provenance
public          visible approved data + embedded approved data + public-safe provenance
minimal_public  no row-level data sheets or contents; statistics, hashes and links only
```

For public profiles, imported ledger rows pass through a field allowlist plus recursive private-string scrubbing. The original private ledger is never placed into `raw_record_json` in the public dataset.

## Exit gate

1. Master workbook extraction reproduces all supplied embedded table bytes.
2. Public workbook extraction and visible sheets contain exactly the approved columns and public names.
3. Minimal-public workbooks contain no row-level values in sheets, shared strings or embedded records.
4. Private absolute paths, credentials and excluded subject columns are absent from the entire public Office ZIP package.
5. An unclassified non-empty table fails public generation unless columns are explicitly approved.
6. Public/minimal inputs cannot generate a master workbook.
7. Statistics and test coverage remain present when permitted and are clearly marked when data are unavailable.
8. Workbook-specific and existing public-safety validation both pass on safe fixtures.

## Known risks

- Hidden worksheets and Office shared strings can retain deleted values. Generate each profile from a fresh workbook rather than deleting from a master copy.
- Statistics records can contain participant labels or local paths. Treat them as data, not automatically public metadata.
- Qualified table names must remain stable across duplicate display names; use figure identifiers rather than worksheet names.
