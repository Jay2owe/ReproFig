# Stage 14 — Decide whether a valid signer is trusted

## Why this stage exists

Anyone can generate a key and add a valid signature. The proof becomes attributable only when the verifier already trusts that key through an independent route. This stage adds local trust policy, scope, rotation and revocation so a forged self-signed figure cannot impersonate a researcher, laboratory or automated release service.

## Prerequisites

- Stage 13 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 13 file
- `src/reprofig/crypto/signatures.py` in its completed form
- `src/reprofig/crypto/keys.py` in its completed form
- `src/reprofig/verification.py` in its completed Stage 03 form
- `src/reprofig/cli.py:1-214` plus completed signature commands
- `docs/security.md` in its completed form

## Scope

- Define a deterministic local trust-store format outside figure artifacts.
- Trust keys by fingerprint and scope: individual, laboratory, project, automated verifier or publisher.
- Add policies requiring one or more trusted signatures for named operations.
- Support key activation, rotation, expiration and revocation metadata.
- Keep signature validity separate from current trust status.
- Report the limits of historical validity when no independent trusted timestamp exists.
- Allow a trusted signer to attest to a verification-report hash and achieved grades.
- Add non-networked trust commands suitable for automated and offline use.
- Reserve extension points for Stage 20 registries without requiring network access.
- Load trust stores only for explicit signature/trust verification and never consult them during ordinary save, inspect or extraction calls.

## Out of scope

- This stage does not create a public registry or certificate authority.
- It does not claim a self-reported signing time predates compromise.
- Encryption recipients belong to Stage 15 and are not automatically trusted signers.
- Institutional identity-proofing procedures remain deployment policy.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/crypto/trust.py` | NEW | Trust store, scopes, policy evaluation and lifecycle. |
| `src/reprofig/crypto/attestations.py` | NEW | Signed verification-report attestations. |
| `src/reprofig/verification.py` | MODIFY | Add signer-trusted and attested checks. |
| `src/reprofig/api.py` | MODIFY | Export trust and attestation operations. |
| `src/reprofig/cli.py` | MODIFY | Add trust list/add/remove/revoke and attest commands. |
| `tests/test_trust.py` | NEW | Test unknown, scoped, rotated, revoked and compromised-key behavior. |
| `docs/security.md` | MODIFY | Document how trust is established and what it cannot prove. |

## Implementation sketch

```json
{
  "trust_schema": "reprofig-trust/1",
  "keys": [
    {
      "fingerprint": "sha256:...",
      "label": "Brancaccio Lab release key",
      "scopes": ["project:pyflash", "role:release"],
      "active_from": "2026-08-25T00:00:00Z",
      "expires_at": null,
      "revoked_at": null,
      "source": "local_admin"
    }
  ]
}
```

```python
@dataclass
class TrustPolicy:
    required_scopes: set[str]
    minimum_trusted_signatures: int = 1
    require_attested_grades: set[VerificationGrade] = field(default_factory=set)

def evaluate_trust(
    signatures: Sequence[SignatureEnvelope],
    store: TrustStore,
    policy: TrustPolicy,
) -> list[VerificationCheck]: ...
```

Attestations sign the canonical hash of a completed verification report, verifier implementation identity, figure evidence root and achieved grades. They do not modify the underlying calculation evidence.

Without a trusted timestamp, revocation policy can state only current trust. If historical validity is permitted, the report must identify the external timestamp evidence used; otherwise a signature made with a now-revoked key cannot be proven to predate compromise.

## Exit gate

1. A valid signature from an unknown embedded key reports valid but untrusted.
2. A trusted key passes only within its declared scope.
3. Rotated and revoked keys follow the explicit active policy and never rely solely on self-reported artifact time.
4. A policy requiring a laboratory release signature fails when only a personal key is present.
5. A trusted attestation binds exactly one verification-report hash and evidence root.
6. Trust evaluation works offline from an explicitly selected trust store.
7. `pytest tests/test_trust.py tests/test_signatures.py -q` passes.
8. No trust file, network connection or signer identity is required when no trust policy is requested.

## Known risks

- Trust-store modification is a security boundary. Document ownership and permission expectations and support read-only deployment.
- Revocation without trusted timestamps cannot establish historical validity. Report this limitation instead of inventing certainty.
- A trusted signer can still approve fabricated inputs. Signatures establish attribution and integrity, not truth.
