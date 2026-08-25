# Stage 15 — Encrypt selected evidence sections without breaking public verification

## Why this stage exists

Master figures may contain subject-level data, local sources or confidential reproduction details that should travel only to authorized reviewers. Whole-file encryption would also hide the public figure identity and non-sensitive evidence. This stage encrypts selected sections independently while leaving a signed public manifest that states exactly what is protected and what remains verifiable.

## Prerequisites

- Stages 02 and 13 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 02 and Stage 13 files
- `docs/publication-workbook/05_embedded-evidence-and-validation_COMPLETED.md:1-end`
- `src/reprofig/workbook/evidence.py:1-end`
- `src/reprofig/evidence.py` in its completed form
- `src/reprofig/crypto/signatures.py` and `src/reprofig/crypto/keys.py` in their completed forms
- `src/reprofig/schema.py:1-353` plus completed proof schema additions
- `src/reprofig/carriers/payload.py:1-89`
- `src/reprofig/carriers/bundle.py:1-236`
- `docs/security.md` in its completed form

## Scope

- Record a focused decision selecting maintained authenticated-encryption and recipient-envelope implementations.
- Encrypt individual evidence sections rather than the entire carrier.
- Generate an independent random content key and nonce according to the selected algorithm’s requirements for every encrypted section.
- Support password access using Argon2id key derivation with stored salt and cost parameters.
- Support named-recipient access using a maintained public-key envelope standard or library selected by the decision record.
- Bind figure identity, section identity, schema and public envelope metadata as authenticated additional data.
- Hash ciphertext in the public evidence graph and verify plaintext identity only after successful decryption.
- Sign after encryption so signatures cover the exact ciphertext and recipient envelopes.
- Prevent plaintext, passwords, private recipient keys and decrypted temporary files from leaking into logs or artifacts.
- Enforce decompression, recipient-count, ciphertext-size and key-derivation resource limits.
- Let publication workbooks select aggregate source-data tables, raw statistical records or provenance as encryptable sections while keeping their public index explicit.
- Never leave plaintext from an encrypted workbook section in a visible worksheet, shared string, comment, property or parallel embedded record.

## Out of scope

- Do not design a new cipher, key-exchange protocol or recipient-envelope format.
- Public-profile transformations and re-encryption belong to Stage 16.
- Trusting an encryption recipient as a signer is forbidden without Stage 14 policy.
- Full disk, directory or carrier encryption remains outside ReproFig.

## Files touched

| path | change | reason |
|---|---|---|
| `docs/decisions/encryption-envelope.md` | NEW | Choose maintained algorithms/libraries and record threat assumptions. |
| `src/reprofig/crypto/encryption.py` | NEW | Section authenticated encryption and decryption. |
| `src/reprofig/crypto/recipients.py` | NEW | Password and named-recipient content-key envelopes. |
| `src/reprofig/evidence.py` | MODIFY | Hash ciphertext/envelopes and validate decrypted section identity. |
| `src/reprofig/api.py` | MODIFY | Export explicit encrypt/decrypt operations. |
| `src/reprofig/cli.py` | MODIFY | Add non-leaking section encryption and decryption commands. |
| `tests/test_encryption.py` | NEW | Test access, corruption, wrong keys, limits and leakage. |
| `docs/security.md` | MODIFY | Document confidentiality, metadata leakage and key handling. |

## Implementation sketch

```python
@dataclass
class EncryptedSection:
    section_id: str
    envelope_schema: str
    cipher: str
    nonce: str
    ciphertext: str
    ciphertext_sha256: str
    recipients: list[dict[str, Any]]
    associated_data_sha256: str

def encrypt_section(
    record: FigureRecord,
    section_id: str,
    *,
    recipients: Sequence[Recipient] = (),
    password_source: PasswordSource | None = None,
) -> EncryptedSection: ...
```

Encryption order:

```text
canonical plaintext section
  -> random content key and nonce
  -> authenticated encryption with figure/section context
  -> wrap content key for each recipient or password-derived key
  -> replace plaintext with ciphertext envelope
  -> rebuild evidence graph over ciphertext
  -> sign the new evidence root
```

Do not expose a public plaintext hash when low-entropy or guessable data could be tested against it. The ciphertext hash is public; plaintext verification information may remain inside the encrypted payload and is checked after decryption.

Passwords must be read through non-echoing input or an explicit descriptor. They must never be accepted directly as a command-line argument.

## Exit gate

1. Authorized password and named recipients recover exact canonical section bytes.
2. Wrong keys, changed ciphertext, changed associated metadata and changed authentication tags fail closed.
3. Two encryptions of the same section produce different ciphertext and nonces.
4. No nonce or content key is reused in stress tests.
5. A verifier without a key can verify ciphertext hash and signature coverage but reports plaintext checks inaccessible.
6. Artifact inspection, logs and process arguments contain no password, private key or plaintext protected section.
7. Official algorithm test vectors and `pytest tests/test_encryption.py tests/test_signatures.py -q` pass.
8. Building or opening an ordinary unencrypted workbook requires no key, cryptographic dependency or new prompt.

## Known risks

- Encryption metadata can reveal section existence, approximate size and recipient count. Document this; padding is a separate explicit policy if later required.
- Password security depends on strength and Argon2id cost. Store parameters and enforce safe minimums without exhausting verifier resources.
- Re-encrypting content changes the evidence root and requires a new signature. Stage 16 defines derivative behavior.
