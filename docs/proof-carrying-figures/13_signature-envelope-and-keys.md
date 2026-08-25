# Stage 13 — Sign evidence roots and manage signing keys safely

## Why this stage exists

Checksums detect changes but anyone can replace both content and checksums. A digital signature binds the canonical evidence root to control of a private key. This stage makes tampering detectable and establishes the crucial distinction that a mathematically valid signature is not automatically a trusted identity.

## Prerequisites

- Stages 02 and 03 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 02 and Stage 03 files
- `docs/publication-workbook/05_embedded-evidence-and-validation_COMPLETED.md:1-end`
- `src/reprofig/workbook/evidence.py:1-end`
- `src/reprofig/evidence.py` in its completed Stage 02 form
- `src/reprofig/schema.py:1-353` plus completed proof schema additions
- `src/reprofig/api.py:1-428`
- `src/reprofig/cli.py:1-214`
- `pyproject.toml:1-71`
- `docs/multiformat_embedding_plan.md:96-145`

## Scope

- Implement Ed25519 signing through a maintained cryptographic library following RFC 8032.
- Domain-separate ReproFig signature input from signatures used by other applications.
- Sign the figure identity, record schema, canonical evidence root and signature-policy context.
- Permit multiple signatures without making signatures part of their own recursive evidence root.
- Include the public key for portability while identifying it by a SHA-256 fingerprint.
- Create, import and export password-protected private keys through explicit commands.
- Never place private keys in figure records.
- Verify signature mathematics without claiming trust.
- Report missing, malformed, unsupported and tampered signatures through Stage 03 results.
- Preserve visible carrier content when adding a signature.
- Import cryptographic implementations lazily under the aggregate `[proof]` extra; schema inspection of signed or unsigned records remains dependency-light.
- Sign publication workbooks through their aggregate logical evidence root, not their mutable Office ZIP bytes.

## Out of scope

- Trust stores, key rotation and revocation belong to Stage 14.
- Section encryption belongs to Stage 15.
- Public-profile re-signing belongs to Stage 16.
- Remote identity services and stripped-metadata recovery belong to Stage 20.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/crypto/signatures.py` | NEW | Signature envelope, signing and mathematical verification. |
| `src/reprofig/crypto/keys.py` | NEW | Key generation, protected serialization and fingerprints. |
| `src/reprofig/evidence.py` | MODIFY | Produce the exact domain-separated bytes that signatures cover. |
| `src/reprofig/api.py` | MODIFY | Export signing and signature-verification operations. |
| `src/reprofig/cli.py` | MODIFY | Add key generation, sign and verify-signature commands. |
| `tests/test_signatures.py` | NEW | Test valid, altered, replaced, missing and multiple signatures. |
| `pyproject.toml` | MODIFY | Add maintained cryptographic dependencies beneath the aggregate `[proof]` extra. |
| `docs/security.md` | NEW | Document threat model, key handling and non-trust of embedded keys. |

## Implementation sketch

```python
@dataclass
class SignatureEnvelope:
    signature_schema: str              # reprofig-signature/1
    algorithm: str                     # ed25519
    key_fingerprint: str
    public_key: str                    # portable, not automatically trusted
    evidence_root_sha256: str
    signature: str
    claimed_signer: dict[str, Any]
    created_at: str                    # signer assertion, not trusted timestamp

def signature_input(record: FigureRecord) -> bytes:
    return deterministic_json({
        "domain": "reprofig-signature/v1",
        "figure_id": record.figure_id,
        "record_schema": record.schema,
        "evidence_root_sha256": record.evidence.root_sha256,
        "policy": "proof-carrying-figure",
    }).encode("utf-8")
```

Command shape:

```text
reprofig key generate --output researcher.key
reprofig key public researcher.key --output researcher.pub
reprofig sign Figure.svg --key researcher.key --output Figure.signed.svg
reprofig verify-signature Figure.signed.svg
```

Private-key files must use the cryptographic library’s protected serialization and restrictive local permissions where supported. Passwords come from a non-echoing prompt or file descriptor, never a command-line value, log or record.

An attacker may remove a signature and add one from their own key. Mathematical verification then reports `signature_valid=true` for the attacker’s signature but Stage 14 reports `signer_trusted=false`; a policy requiring the original trusted key fails because that signature is absent.

## Exit gate

1. A correctly signed evidence root verifies after movement and round trips through representative carriers.
2. Changing any signed section, dependency, figure identity or ciphertext byte invalidates the signature.
3. Adding an unrelated signature does not make it trusted and does not invalidate an existing valid signature.
4. Removing a required signer’s signature fails a required-signature policy once Stage 14 is present; this stage exposes the missing fingerprint now.
5. An embedded public key alone never produces `signer_trusted`.
6. Private-key plaintext and passwords never appear in artifacts, standard output, logs or tests.
7. Official Ed25519 test vectors and `pytest tests/test_signatures.py -q` pass.
8. Signing is never automatic: basic saving, extraction and workbook creation require no key and behave unchanged without the cryptographic extra.
9. A harmless Excel package rewrite leaves the signature check valid; changing visible cells fails the separate workbook-projection check even when the embedded-evidence signature remains valid.

## Known risks

- The most serious failure would be bespoke cryptography. Use maintained primitives and official test vectors only.
- Self-reported signing time is editable before signing and is not a trusted timestamp. Do not use it to defeat later revocation.
- Key loss prevents future signing; key compromise permits impersonation until trust policies revoke it. Stage 14 owns lifecycle controls.
