# Canonical publication workbook from ReproFig figure batches

## End goal

A researcher who explicitly opts into the publication workflow can give ReproFig a mixed batch of supported figure files and receive one journal-ready Excel workbook. The workbook contains readable source-data sheets, one complete statistics table, figure-to-evidence links, verification results and the exact CSV evidence embedded in the Excel file. Ordinary figure saving, inspection and CSV extraction remain unchanged; an optional experiment statistics ledger lets the workbook distinguish every test represented in the figures from every test declared by the analysis, including unplotted results.

## Why we're doing this

ReproFig currently extracts exact CSV tables and structured statistics from one or many figure records, but batch output remains a collection of separate files. Preparing journal source-data workbooks and exhaustive statistical-test tables is therefore still manual, error-prone and difficult to audit. This work turns those existing records into one stable publication deliverable without treating Excel's interpreted cell values as the archival originals.

## Architecture overview

```text
figures, bundles and optional experiment statistics ledger
                            |
                  collect and validate records
                            |
              deduplicate tables and reconcile tests
                            |
                canonical PublicationDataset
                   /                   \
        readable Excel sheets     aggregate ReproFig record
                   \                   /
             Publication-source-data.xlsx
                            |
              round-trip workbook verification
```

`PublicationDataset` is the logical, format-independent publication model. Excel worksheets are readable projections of that model; an aggregate `reprofig/1` record embedded after workbook creation preserves the unique CSV bytes, normalized statistics and source-record fingerprints. The workbook's logical evidence fingerprint, rather than its mutable Office ZIP bytes, is the stable identity.

## Stage map

| NN | name | one-line goal | rough size | depends on |
|---:|---|---|---|---|
| 01 | publication dataset contract | Define stable publication, figure, table, statistic and coverage records without changing the `reprofig/1` schema | 1 day | none |
| 02 | batch record collection | Collect supported artifacts, validate records, detect conflicts and index every unique table and occurrence | 2 days | 01 |
| 03 | statistics ledger | Normalize exact statistical fields and reconcile figure tests with an optional experiment-complete ledger | 2 days | 01, 02 |
| 04 | Excel rendering | Render the canonical dataset into safe, readable and deterministic worksheet structures | 2 days | 01, 03 |
| 05 | embedded evidence and validation | Embed an aggregate ReproFig record and prove worksheets round-trip to the embedded evidence | 2 days | 02, 03, 04 |
| 06 | publication profiles and privacy | Produce master, public and minimal-public workbooks without leaking excluded data | 2 days | 05 |
| 07 | Python and command-line interfaces | Expose one atomic batch API and a `reprofig publication-workbook` command | 1 day | 05, 06 |
| 08 | end-to-end hardening and documentation | Prove mixed-format workflows, document journal handoff and validate the installable package | 2 days | 01-07 |

Stages 02 and 03 are kept separate because carrier discovery and statistical meaning require different source context. Stage 04 creates ordinary Excel content; Stage 05 embeds and verifies ReproFig evidence only after the workbook bytes exist. This plan is implemented before `docs/proof-carrying-figures/`; the later plan adds independent statistical recalculation, signatures, trust and selective encryption to this completed workbook pipeline.

## House rules

- Preserve all current `reprofig/1` reading, extraction, publication and carrier behavior.
- Keep the beginner path unchanged: base installation, `save_figure`, `extract` and existing loose statistics records gain no new required arguments, prompts, dependencies or failure conditions.
- Generate no workbook automatically. Workbook behavior begins only when the caller installs the `excel` extra and invokes its dedicated Python function or command.
- The exact embedded UTF-8 CSV bytes remain canonical. Excel cell values are readable projections and must never replace or rewrite those bytes.
- Define workbook identity from canonical logical evidence, not from the full `.xlsx` ZIP byte stream, because spreadsheet software rewrites package metadata.
- Use stable identifiers and SHA-256 hashes for deduplication. Never deduplicate tables or tests solely by a display label.
- The same figure identifier with different record content is an error. The same table hash with different bytes is an error.
- Do not silently truncate rows, columns, text, probability values or worksheets to fit Excel limits. Fail with a precise diagnostic and preserve the ReproFig ZIP fallback.
- Preserve exact probability and statistic lexemes as text. Numeric Excel cells may be added only as convenience columns.
- A figure batch can claim `figure_complete` only for tests represented by its supplied figure records. It can claim `analysis_complete` only when an explicitly complete experiment ledger reconciles with every displayed test.
- Tests without a shared explicit `test_id` are separate occurrences. Do not guess that visually similar tests are duplicates.
- Retain unrecognized statistical fields losslessly in deterministic JSON rather than dropping them.
- Workbooks contain no macros, formulas, executable links or external data connections. Strings beginning with formula characters are written as literal text.
- `master`, `public` and `minimal_public` remain one-way profiles. Public workbooks contain only approved columns; minimal-public workbooks contain no row-level data.
- Keep Excel support optional so importing core ReproFig still requires only the Python standard library.
- Missing optional journal fields remain blank and documented; only an explicitly requested completeness policy may reject them.
- Create output atomically and refuse overwrite unless the caller explicitly requests it.
- This plan adds encryption-ready section boundaries but no cryptography. Signatures, trust and selective encryption belong to `docs/proof-carrying-figures/`.
- Do not commit, push, tag or publish without the user's explicit instruction at that execution stage.

## Known open questions

None. The initial format, coverage vocabulary, input contracts and failure behavior are fixed by this plan. Later proof-carrying stages may extend the records without changing these workbook interfaces.

## How to run a stage

Run `/do-step docs/publication-workbook/`; it selects the lowest numbered stage without `_COMPLETED`.
