# Stage 24 — Harden proof verification against tampering and carrier transformations

## Why this stage exists

Proof features are security boundaries: a false pass is worse than a clear unsupported result. The component tests from earlier stages are necessary but do not cover interactions between carriers, signatures, trust, encryption, visual tolerances and hostile input. This stage attacks those boundaries before release.

## Prerequisites

- Stages 01 through 23 must all be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- all completed stage files 01–23
- `docs/publication-workbook/08_end-to-end-hardening-and-documentation_COMPLETED.md:1-end`
- `tests/test_multiformat.py:1-197`
- `tests/test_roundtrip.py:1-160`
- `src/reprofig/carriers/base.py:1-104`
- `src/reprofig/carriers/manifest.py:1-191`
- `src/reprofig/carriers/bundle.py:1-236`
- `docs/carrier_survival.md:1-42`

## Scope

- Build a threat matrix covering record, graph, statistics, rendering, signature, trust, encryption, archive and broker attacks.
- Mutate every signed evidence section and prove the expected check fails.
- Test signature substitution, removal, duplicate signers, unknown keys, revoked keys and altered attestations.
- Test wrong passwords/recipients, nonce/tag/ciphertext corruption, envelope swaps and resource-exhaustion parameters.
- Test source/table transformations that preserve appearance while changing scientific meaning.
- Test visual changes small enough to challenge global raster thresholds but large enough to change a data mark.
- Round-trip signed and encrypted records through all sixteen carriers.
- Attack publication workbook cells, aggregate records, statistics ledgers, signatures and selectively encrypted sections as one cross-layer fixture.
- Exercise documented editor/re-encoding transformations where tools are available.
- Fuzz or property-test parsers and canonicalizers under strict input/resource limits.
- Test archive traversal, decompression bombs, links and broker races.
- Update survival documentation only from measured outcomes.

## Out of scope

- This stage does not expand scientific algorithms or add new carriers.
- It does not host a public registry.
- Failures found here are fixed in their owning module with a regression test; do not weaken policy to make tests pass.
- Formal cryptographic proof remains the responsibility of the selected maintained primitives.

## Files touched

| path | change | reason |
|---|---|---|
| `tests/test_proof_multiformat.py` | NEW | Signed/encrypted/verified round trips across every carrier. |
| `tests/test_adversarial_evidence.py` | NEW | Graph, statistic and signature mutation matrix. |
| `tests/test_adversarial_encryption.py` | NEW | Ciphertext, recipient, password and resource-limit attacks. |
| `tests/test_adversarial_visual.py` | NEW | False-positive and false-negative visual cases. |
| `tests/test_adversarial_broker.py` | NEW | Traversal, link, race and bypass attacks. |
| `tests/fixtures/adversarial/README.md` | NEW | Document generated fixture provenance and expected failures. |
| `pyproject.toml` | MODIFY | Add test-only property/fuzz dependencies if selected. |
| `docs/carrier_survival.md` | MODIFY | Record measured proof/signature/encryption survival. |

## Implementation sketch

Threat matrix columns:

```text
attack_id
target boundary
mutation
expected failing check code
must remain readable?
must leave destination unchanged?
carrier coverage
```

Representative cases:

```text
change exact p value but leave label
change label but leave exact p value
move one point within a permissive global image threshold
replace ciphertext section between figures
replace embedded public key and add attacker signature
remove trusted signature and retain attacker signature
raise Argon2id cost beyond configured limit
swap correction-family membership
change source row while preserving aggregate mean
modify candidate after broker verification
embed archive member traversal path
```

Generate large or hostile fixtures during tests where possible; do not commit sensitive or huge binary blobs.

## Exit gate

1. Every threat-matrix row has a deterministic expected check code and passes on all eligible carriers.
2. No forged key or self-signed replacement satisfies a trusted-signer policy.
3. No corrupted encrypted section returns plaintext or a passing dependent grade.
4. Scientific mark mutations fail stricter region checks even when global raster comparison passes.
5. Every carrier retains the same signed evidence root unless the documented transformation strips metadata, in which case recovery behavior is tested.
6. Parser, decompression and broker resource limits fail before unsafe allocation/promotion.
7. The complete ReproFig test suite passes repeatedly on Windows and Linux.
8. Edited, stripped, forged and encrypted workbooks never pass a stronger grade than their surviving evidence supports.

## Known risks

- Flaky visual tests undermine trust. Pin deterministic fixtures and separate environment-unavailable outcomes from mismatches.
- Fuzzing can consume unbounded time. Use reproducible seeds and bounded continuous-integration budgets.
- A passing threat matrix is not a permanent security guarantee. Preserve regression cases and publish the threat model.
