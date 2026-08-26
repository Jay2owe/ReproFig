# Proof-carrying figures

A proof-carrying figure is like a worked answer attached to a result: a reader
can check each declared step without trusting the plotting program alone.

Install `pip install "reprofig[proof]"`. Ordinary `save_figure` behavior stays
unchanged until `proof=True` or a proof policy is supplied.

## Verification meanings

| Meaning | Passing claim | Does not claim |
|---|---|---|
| `internally_consistent` | Carrier, record, sections and evidence root agree. | Source truth or scientific suitability. |
| `source_linked` | Declared closed transformations reconstruct the exact target CSV. | That the supplied source was honestly collected. |
| `statistics_reproduced` | Expected numbers match the declared producer-equivalent route. | Independent implementation or a second figure. |
| `statistics_independently_verified` | A supported reference algorithm matches declared outputs and display text. | Correct choice of test. |
| `figure_reproduced` | An explicitly trusted producer rerun saved a separate figure whose data, statistics, and display match. | Source truth or producer safety. |
| `display_verified` | Bound scientific marks/annotations match the carrier reference. | Meaning of unbound decoration. |
| `signature_valid` | An Ed25519 signature is mathematically valid for this evidence and visual binding. | Trust in its key owner. |
| `signer_trusted` | A valid signer satisfies the supplied offline trust policy. | Universal or external identity. |
| `attested` | A valid signature binds a deterministic verification-report hash. | That the attested report was independently rerun now. |

Each check is `pass`, `fail`, `unavailable`, `inaccessible`, `unsupported` or
`not_requested`. A report is valid only when carrier integrity passes and every
explicitly required meaning is `pass`.

```console
reprofig verify Figure.svg \
  --require internally_consistent \
  --require statistics_independently_verified \
  --require display_verified
```

Protected evidence can be verified without creating a plaintext artifact:

```console
reprofig verify Figure.protected.svg \
  --password-env REPROFIG_DATA_PASSWORD \
  --require statistics_independently_verified
```

For a transformation whose source CSV is external, add `--source-table
source:raw=analysis/raw.csv`.

## Python workflow

1. Build or attach exact data, statistics and provenance as usual.
2. Add typed `TransformationSpec` and `StatisticalSpecification` values under
   the record's proof extension.
3. Bind proof-relevant artists with `bind_artist`.
4. Save with `proof=True`.
5. Verify required meanings from the completed carrier.
6. Optionally encrypt selected sections, sign, evaluate trust and attest the
   verification report.
7. Derive and separately sign public outputs; never publish a master by default.

```python
from reprofig import bind_artist, save_figure, verify_proof

bind_artist(
    points,
    semantic_id="participant-values",
    table_id="table:SHA256",
    row_ids=["row-01", "row-02"],
    columns=["condition", "value"],
)
record = save_figure(
    figure,
    "Figure-1.svg",
    record=record,
    proof=True,
)
report = verify_proof(
    "Figure-1.svg",
    required=[
        "internally_consistent",
        "source_linked",
        "statistics_independently_verified",
        "display_verified",
    ],
    source_tables={"source:raw": source_table},
)
```

## Signing and trust

Generate a password-protected signing key, sign only after every evidence and
visual reference is final, and add its public fingerprint to a local trust
store through a separate authenticated route.

```console
reprofig sign Figure.svg --key signing.pem \
  --password-env REPROFIG_SIGNING_PASSWORD --output Figure.signed.svg
reprofig trust add --store trust.json --fingerprint sha256:... \
  --label "Analysis release key" --scope figure
reprofig verify Figure.signed.svg --trust-store trust.json \
  --require signature_valid --require signer_trusted
```

Changing an evidence section, visible bound mark, signature context or embedded
public key invalidates the appropriate check. Adding an attacker's valid
self-signature does not satisfy a policy that requires the enrolled key.

## Controlled output

`guarded_python` intercepts Matplotlib `Figure.savefig` and `pyplot.savefig`
only inside its context and restores both functions on exit. It is convenient
for cooperative code. A language-neutral broker is the stronger boundary:
R, Julia, JavaScript or MATLAB writes into a contained candidate directory,
then the broker embeds the declared record, applies the central profile/
encryption/signing policy, verifies it, copies unchanged bytes and atomically
promotes the file.

See `docs/agent-enforcement.md`, `docs/language-adapters.md`,
`docs/statistical-verification.md`, `docs/render-verification.md` and
`docs/security.md` for the exact boundaries.

## Compatibility

The proof graph is an optional extension of `reprofig/1`; the schema identifier
does not change. Version 0.2 readers retain unknown extensions during a normal
round trip but cannot verify them. Legacy `figure-artifact/1` and `metafig/1`
records remain readable. Do not claim a proof meaning unless a 0.3 verifier
actually returns `pass` for it.
