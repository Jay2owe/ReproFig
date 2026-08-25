# Publication workbook

The workbook is an optional journal handoff built from existing ReproFig
artifacts. It does not change ordinary figure saving and requires only
`pip install "reprofig[excel]"`.

```python
from reprofig import build_publication_workbook

result = build_publication_workbook(
    "figures/",
    "Publication-source-data.xlsx",
    experiment_statistics="analysis/all-tests.json",
)
```

The same operation is available from the command line:

```console
reprofig publication-workbook figures/ --output Publication-source-data.xlsx \
  --statistics-ledger analysis/all-tests.json
```

## What is canonical

Excel cells are a readable projection. The embedded `reprofig/1` aggregate
record is canonical: it contains exact UTF-8 CSV bytes, normalized statistical
records, worksheet mapping, source-figure identities and a deterministic
publication fingerprint. Validation compares every projected cell with that
record. Editing a value requires rebuilding the workbook; direct edits fail
validation.

Duplicate copies of one figure and byte-identical CSVs are deduplicated by
figure identity and SHA-256 content identity. Absolute input paths are used
only while collecting and are never serialized.

## Worksheets

- `README`: publication identity, profile, coverage and evidence fingerprint.
- `Figures`: every unique figure record and its source labels.
- `Data_Index`: each canonical CSV, its data worksheet and every figure use.
- `Statistics`: one row per declared test with exact and numeric projections.
- `Test_Families`: multiple-comparison family membership and method.
- `Verification`: integrity and reconciliation outcomes.
- `Dictionary`: field meanings and which exact fields are authoritative.
- `D###_*`: one formula-free worksheet for each included canonical CSV.

The statistics table retains test identity, outcome, groups, analysis unit,
all sample sizes, exclusions, pairing, alternative hypothesis, alpha,
statistic, degrees of freedom, exact raw and adjusted probability values,
displayed text, correction family, confidence interval, effect size, missing
policy, model formula, covariates, random seed, resamples and producer version
when supplied. Missing facts stay blank; ReproFig never guesses them.

## Complete analysis ledger

Figure records can prove which tests they display. To include unplotted tests,
provide an experiment ledger:

```json
{
  "schema": "reprofig-statistics-ledger/1",
  "analysis_id": "experiment-2026-01",
  "coverage": "analysis_complete",
  "statistics": [
    {
      "test_id": "primary-comparison",
      "test_name": "Welch t-test",
      "n_a": 12,
      "n_b": 11,
      "statistic": "3.214582",
      "p": "0.004182000000000000",
      "alternative": "two_sided"
    }
  ]
}
```

`analysis_complete` is an author declaration that the ledger contains every
analysis. It cannot prove that an undisclosed analysis never occurred.
Without that declaration, coverage is `figure_complete`, `incomplete`, or
`not_applicable` according to the source records.

## Profiles and protected evidence

- `master` includes every exact source table and may contain confidential data.
- `public` includes only explicitly approved columns.
- `minimal_public` retains indexes, provenance and statistics without row data.

Use a safe-column allowlist for public outputs. Package-wide privacy validation
checks worksheets and embedded Office parts.

With `reprofig[proof]`, individual table sections or the full reported-statistics
section can be encrypted. The visible redacted dataset has its own signed
fingerprint, so redaction does not leave editable unsigned worksheet content.
`publication:aggregate` itself remains public because validation needs its
worksheet mapping and visible fingerprint.

```console
reprofig publication-workbook figures/ --output Reviewer-data.xlsx \
  --protect-section table:SHA256 \
  --encryption-password-env REPROFIG_DATA_PASSWORD \
  --signing-key publication-signing.pem \
  --signing-password-env REPROFIG_SIGNING_PASSWORD \
  --require signature_valid
```

Passwords are read only from explicitly named environment variables. A failed
validation or required proof policy leaves an existing destination unchanged.

## Journal handoff

1. Keep the master workbook and original figure masters in controlled storage.
2. Upload the public workbook when row-level data are permitted.
3. Upload the minimal-public workbook plus repository links when journals do
   not accept row-level data in the figure-source workbook.
4. Supply a protected workbook only when the recipient has an agreed key route.
5. Send a `.reprofig.zip` alongside Excel if the archive is the long-term source
   of truth; Office applications may remove custom package parts.
6. Run `reprofig validate Publication-source-data.xlsx` after any editor or
   upload/download round trip.
