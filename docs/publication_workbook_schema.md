# Publication Workbook Logical Schema

The publication workbook model is a logical evidence contract, not an Excel
file format. Its schema identifier is `reprofig-publication-workbook/1`.
Existing figure records keep the separate `reprofig/1` schema.

## Identity

`PublicationDataset.fingerprint()` is the SHA-256 hash of the canonical
`evidence_dict()`. That evidence is sorted by stable identifiers and excludes
build time, output path and worksheet styling, because spreadsheet programs can
rewrite those details without changing scientific evidence.

When no `publication_id` is supplied, the default is
`publication:<first 24 hexadecimal characters of the evidence hash before the
identifier is inserted>`.

## Dataset Fields

- `schema`: always `reprofig-publication-workbook/1`.
- `publication_id`: namespaced stable publication identifier.
- `profile`: one of `master`, `public` or `minimal_public`.
- `figures`: source figure records represented by `figure_id` and the original
  source-record SHA-256 fingerprint.
- `tables`: unique canonical CSV tables identified as
  `table:<embedded CSV SHA-256>`.
- `statistics`: statistical test records identified by explicit `test_id`
  values, or by occurrence identifiers such as `figure-stat:<figure_id>:<index>`
  when no shared identifier exists.
- `test_families`: stable groupings of related tests.
- `verification`: deterministic workbook verification rows.
- `statistics_coverage`: one of `incomplete`, `figure_complete`,
  `analysis_complete` or `not_applicable`.
- `coverage`: the figure and test identifiers supporting the coverage claim,
  plus optional ledger fingerprint metadata.

## Archival Values

The archival values are the figure-record SHA-256 fingerprints, exact table
SHA-256 hashes, embedded UTF-8 CSV text, statistic `raw_record` dictionaries,
coverage status and explicit occurrence links. Later Excel worksheets are
readable projections of these values and must not rewrite the canonical CSV
bytes or exact probability/statistic lexemes.

## Display Conveniences

`display_order`, figure titles, source labels, normalized statistic fields and
verification messages exist to make workbook sheets readable. They are still
serialized deterministically. `build_metadata`, `output_path` and
`worksheet_style` are excluded from the evidence fingerprint.

## Validation

`PublicationDataset.validate()` returns precise structural errors for unsupported
schemas, invalid coverage statuses, duplicate identifiers, figure-record
fingerprint conflicts, table hash mismatches, missing table column metadata,
unknown occurrence references and invalid ledger hashes. It does not perform
artifact discovery, statistical normalization, ledger reconciliation, Excel
rendering, signing, encryption or independent statistical recalculation.

## Statistics projection

The normalized ledger has stable columns for test/analysis/panel/claim IDs,
display status, outcome, groups, analysis unit, all sample sizes and exclusions,
method/version, pairing, alternative, alpha, test statistic and degrees of
freedom, exact and numeric raw/adjusted probabilities, displayed annotation,
correction family, confidence interval, effect size and its interval, missing
policy, model formula, covariates, random seed, resamples, producer identity,
reconciliation status and the lossless raw JSON record.

Exact text fields are authoritative. Numeric cells are conveniences for Excel
users and may lose decimal lexical detail. Formula-shaped text is forced to a
string cell. Unknown fields remain in `raw_record_json`; blanks are never
inferred.

An experiment ledger uses `reprofig-statistics-ledger/1`. A test ID shared with
a figure is reconciled; conflicting scientific fields fail. Ledger-only tests
remain with `displayed=false`. `analysis_complete` requires every displayed
test to occur in the ledger, but remains a recorded declaration rather than a
proof against omissions.

## Protection and proof

The workbook aggregate can carry the optional `reprofig-evidence-graph/1` proof
extension. Exact tables and reported-statistics sections can be encrypted while
the readable redacted dataset retains a separately bound
`visible_logical_fingerprint`. Signatures bind the evidence root. Independent
statistical results remain optional annotations on existing test IDs; workbook
creation never requires the proof extra.
