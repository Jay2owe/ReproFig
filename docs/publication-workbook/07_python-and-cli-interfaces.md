# Stage 07 — Expose one atomic publication-workbook interface

## Why this stage exists

Researchers and downstream plotting tools need one supported operation rather than manually calling collection, reconciliation, rendering and embedding functions. This stage provides a Python function and command-line command that produce a verified workbook or no output at all.

## Prerequisites

- Stages 01 through 06 must be `_COMPLETED`.

## Read first

- `docs/publication-workbook/00_overview.md:1-74`
- `docs/publication-workbook/05_embedded-evidence-and-validation_COMPLETED.md:1-end`
- `docs/publication-workbook/06_publication-profiles-and-privacy_COMPLETED.md:1-end`
- `src/reprofig/api.py:1-35`
- `src/reprofig/api.py:410-428`
- `src/reprofig/cli.py:1-214`
- `src/reprofig/__init__.py:1-105`
- `src/reprofig/artifacts.py:557-723`
- `tests/test_sources_cli.py:1-54`
- `tests/test_profiles_publication.py:95-151`

## Scope

- Add `build_publication_workbook` as the supported high-level Python interface.
- Return a result object containing output path, publication identifier, logical fingerprint, counts, coverage and validation report.
- Add `reprofig publication-workbook` for paths, directories and mixed carrier batches.
- Leave every existing save, extract, publish and bundle interface unchanged; none invokes this operation implicitly.
- Accept optional canonical JSON or CSV experiment-statistics ledgers.
- Require an explicit recorded declaration before a bare CSV ledger can claim analysis completeness.
- Accept profile, approved-column mapping, public-source mapping, publication identifier and overwrite policy.
- Validate the completed workbook by default and return nonzero from the command if it fails.
- Print structured output under the existing global `--json` behavior and concise paths otherwise.
- Keep secrets and future key material out of command arguments and logs.
- Preserve atomic output behavior across every failure.

## Out of scope

- Do not add signing or encryption options before the later proof-carrying stages implement them.
- Do not automatically publish or upload the workbook.
- Do not silently downgrade requested completeness or profile.
- PyFLASH, PyMicroglia and `plot-that` adoption remains in the later proof-carrying integration stages.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/workbook/api.py` | NEW | Orchestrate collection through validated atomic output. |
| `src/reprofig/workbook/__init__.py` | MODIFY | Export the supported high-level function and result. |
| `src/reprofig/api.py` | MODIFY | Re-export workbook construction through the main application programming interface. |
| `src/reprofig/cli.py` | MODIFY | Add the `publication-workbook` command and arguments. |
| `src/reprofig/__init__.py` | MODIFY | Expose public workbook symbols at package level. |
| `tests/test_publication_workbook_api.py` | NEW | Cover Python orchestration, atomicity and result fields. |
| `tests/test_publication_workbook_cli.py` | NEW | Cover command parsing, JSON output and failure codes. |

## Implementation sketch

Public Python contract:

```python
@dataclass
class PublicationWorkbookResult:
    path: Path
    publication_id: str
    evidence_sha256: str
    figure_count: int
    unique_table_count: int
    statistic_count: int
    statistics_coverage: str
    validation: ValidationReport

def build_publication_workbook(
    artifacts: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    output_path: str | os.PathLike[str],
    *,
    profile: str = "master",
    publication_id: str | None = None,
    experiment_statistics: str | os.PathLike[str] | Sequence[Mapping[str, Any]] | None = None,
    declare_ledger_complete: bool = False,
    safe_columns: Mapping[str, Sequence[str]] | None = None,
    public_sources: Mapping[str, str] | None = None,
    overwrite: bool = False,
) -> PublicationWorkbookResult:
    ...
```

Command-line contract:

```text
reprofig publication-workbook FIGURE_OR_DIRECTORY [...] \
  --output Publication-source-data.xlsx \
  [--profile master|public|minimal-public] \
  [--publication-id ID] \
  [--statistics-ledger ledger.json|ledger.csv] \
  [--declare-ledger-complete] \
  [--safe-columns-json approved-columns.json] \
  [--public-source KEY=URI ...] \
  [--overwrite]
```

`--declare-ledger-complete` without a ledger is an error. Canonical JSON carrying `coverage: complete` does not need the flag; the result records the declaration source. On success, the command prints the workbook and validation outcome. On failure it follows the existing `--json` error structure and leaves no destination.

## Exit gate

1. One Python call builds a validated workbook from a mixed path list and from a directory.
2. The command creates the same logical evidence fingerprint as the equivalent Python call.
3. JSON output reports every count, coverage status, logical hash and validation issue deterministically.
4. A CSV ledger cannot report analysis completeness without the explicit declaration flag.
5. Invalid artifacts, conflicts, privacy failures and existing destinations return nonzero without partial output.
6. `minimal-public` spelling is normalized to `minimal_public` consistently.
7. Package-level imports remain dependency-light until the function is called.
8. Existing commands and public exports remain backward compatible.
9. The base package's normal save/extract tests behave identically when the Excel extra is absent.

## Known risks

- Long command lines make privacy mappings error-prone. Use JSON mapping files rather than comma-separated qualified table rules.
- A directory can contain multiple versions of one figure. Conflict errors must list safe filenames and record fingerprints.
- Optional dependency errors should state the exact installation extra, for example `pip install reprofig[excel]`.
