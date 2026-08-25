# Stage 16 — Preserve honest lineage across public profiles, signatures and encryption

## Why this stage exists

Master-to-public conversion deliberately removes or transforms evidence, so the master signature cannot simply be copied and claimed to cover the derivative. Encrypted sections add choices: retain ciphertext, decrypt and redact, or remove it. This stage makes every derivative’s lineage and verification limits explicit while preserving ReproFig’s one-way privacy boundary.

## Prerequisites

- Stages 13, 14 and 15 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stages 13–15
- `docs/publication-workbook/06_publication-profiles-and-privacy_COMPLETED.md:1-end`
- `src/reprofig/workbook/api.py:1-end`
- `src/reprofig/workbook/profiles.py:1-end`
- `src/reprofig/profiles.py:1-187`
- `src/reprofig/artifacts.py:579-747`
- `src/reprofig/publication.py:1-667`
- `src/reprofig/validation.py:1-246` plus completed proof checks
- `tests/test_profiles_publication.py:1-171`
- `docs/security.md` in its completed form

## Scope

- Define derivative lineage from master evidence root to public/minimal-public evidence root.
- Invalidate the assumption that a master signature directly signs changed derivative bytes.
- Preserve the signed master-root statement as lineage evidence without calling the derivative signed by that key.
- Permit an authorized publication key to sign the derivative’s own root.
- Add explicit encrypted-section policies: retain ciphertext, decrypt-transform-reencrypt, or drop.
- Default public derivation to dropping protected sections not explicitly approved.
- Re-run privacy validation over public manifest, encryption metadata, recipient labels and carrier surfaces.
- State which proof checks remain public, inaccessible or removed.
- Ensure publication-safe comma-separated value outputs are derived only from approved plaintext fields.
- Keep conversion one-way and atomic.
- Extend the explicit publication-workbook build call with optional signing and protected-section policies; omit both by default.
- Omit protected row-level worksheets from encrypted workbooks and provide a separate authorized decrypt-to-new-workbook operation that never modifies the protected original in place.

## Out of scope

- This stage does not grant decryption access or trust a recipient automatically.
- A public derivative cannot independently verify claims that require removed private evidence.
- Identity registry publishing belongs to Stage 20.
- Downstream package integration belongs to Stages 21–23.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/profiles.py` | MODIFY | Apply proof, signature and encrypted-section derivative policies. |
| `src/reprofig/artifacts.py` | MODIFY | Publish atomic derivatives with lineage and optional re-signing. |
| `src/reprofig/publication.py` | MODIFY | Describe public verification limits in captions/manifests. |
| `src/reprofig/evidence.py` | MODIFY | Bind parent and derivative roots without recursive signatures. |
| `src/reprofig/validation.py` | MODIFY | Audit public cryptographic metadata and proof accessibility. |
| `src/reprofig/workbook/api.py` | MODIFY | Accept optional signing and encrypted-section policy without changing default workbook output. |
| `tests/test_secure_profiles.py` | NEW | Test signature lineage, encryption choices and leak prevention. |
| `docs/security.md` | MODIFY | Document safe publication workflows and limits. |

## Implementation sketch

Derivative lineage record:

```json
{
  "derivation_schema": "reprofig-derivation/1",
  "parent_figure_id": "fig-...",
  "parent_evidence_root_sha256": "...",
  "parent_profile": "master",
  "derived_profile": "public",
  "transformations": [
    "table:plotted_data -> approved columns",
    "section:private_sources -> removed",
    "section:review_notes -> encrypted section removed"
  ]
}
```

Signature behavior:

```text
master signature -> remains evidence that a trusted key signed the master root
profile transform -> creates a different derivative root
derivative signature -> optional new signature over the derivative root
```

Encrypted-section policy is explicit per section:

```python
class EncryptedSectionPolicy(str, Enum):
    DROP = "drop"
    RETAIN_CIPHERTEXT = "retain_ciphertext"
    DECRYPT_TRANSFORM_REENCRYPT = "decrypt_transform_reencrypt"
```

The last route requires decryption authority, a defined redaction transform and new recipients. It always produces new ciphertext and a new evidence root.

## Exit gate

1. Public and minimal-public derivatives have roots distinct from their master whenever evidence changes.
2. A copied master signature is shown only as parent-lineage evidence and never as a signature over derivative bytes.
3. A newly signed derivative verifies against its own root and trust scope.
4. The default public route drops unapproved encrypted sections and leaks no recipient labels, local paths or private table values.
5. Retained ciphertext remains signature-covered but its plaintext-dependent checks report inaccessible without a key.
6. Safe companion tables contain only approved plaintext columns.
7. `pytest tests/test_secure_profiles.py tests/test_profiles_publication.py -q` passes for every supported carrier profile route.
8. Workbook construction with no security policy produces the same logical dataset and requires no key or cryptographic extra.
9. Searching every Office package part finds no plaintext from protected workbook sections; an authorized derivative reconstructs the exact sheets in a new file.

## Known risks

- Copying a trusted master signature onto a derivative would falsely imply approval of changed content. Keep signed roots explicit.
- Recipient labels and encrypted-section names can leak sensitive context. Apply the same publication audit used for other metadata.
- Decrypt-transform-reencrypt is high risk. Require explicit section approval, fail atomically and retain a non-sensitive transformation audit.
