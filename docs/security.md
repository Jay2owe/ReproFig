# Security model

Think of a signature as a sealed envelope and a trust store as the address
book: the seal can be mathematically intact even when the signer is unknown.
ReproFig reports those questions separately.

## Guarantees

- SHA-256 evidence roots detect changes, omissions, duplicate identities,
  missing dependencies and dependency cycles in canonical evidence sections.
- Ed25519 signatures bind the figure ID, record schema, evidence root, policy
  context and carrier-specific visual-reference hash.
- Trust policies require active signer fingerprints, scopes, minimum signer
  counts and optional exact signer sets. Unknown, expired, revoked, forged or
  out-of-scope keys fail trust.
- AES-256-GCM authenticates each encrypted evidence section. Content keys are
  wrapped either by Argon2id plus AES-GCM for a password or X25519, HKDF and
  AES-GCM for named recipients.
- The output broker verifies a contained candidate and atomically promotes an
  unchanged byte copy into a non-symlink destination.

These mechanisms prove integrity, authorization according to a local policy,
and internal consistency. They do not prove experimental truth, author
identity outside the trust-store enrollment process, statistical suitability,
or freedom from malicious but internally consistent source data.

## Key lifecycle

Create separate signing and recipient keys; never use either as a registry or
package-upload credential.

```console
reprofig key generate --kind signing --output signing.pem \
  --password-env REPROFIG_SIGNING_PASSWORD
reprofig key generate --kind recipient --output reviewer.pem \
  --password-env REPROFIG_RECIPIENT_PASSWORD
reprofig key public --kind recipient --key reviewer.pem \
  --password-env REPROFIG_RECIPIENT_PASSWORD
```

Private keys use encrypted PKCS #8 files, are written atomically and request
owner-only permissions where supported. Back up the encrypted key and its
password separately. Enroll the public fingerprint through an authenticated
out-of-band route. Record activation and expiry, revoke a compromised key, and
optionally name its replacement. Old signatures remain mathematically valid
but fail a policy evaluated after revocation.

## Selective encryption

List section IDs with `reprofig inspect`, then encrypt explicitly:

```console
reprofig encrypt Figure.svg --section table:SHA256 \
  --password-env REPROFIG_DATA_PASSWORD --output Figure.protected.svg
reprofig decrypt Figure.protected.svg --password-env REPROFIG_DATA_PASSWORD \
  --output recovered-evidence.json
```

Named recipients use a JSON mapping from label to Base64 X25519 public key.
Encryption hides plaintext but exposes section type, ciphertext size,
plaintext SHA-256, figure identity and recipient fingerprints. A low-entropy or
already-known table could therefore be guessed by hashing candidates. Do not
treat encryption as anonymization.

Password envelopes enforce bounded Argon2id memory, time and parallelism before
allocation. Ciphertext, plaintext, recipient counts and decoded field lengths
are bounded. Nonces are random per section. Additional authenticated data binds
the section to its figure, schema, section identity and public descriptor, so
ciphertext cannot be swapped between figures.

Public derivatives have three explicit protected-section policies:

- `drop`: omit protected parent evidence.
- `retain_ciphertext`: retain opaque parent ciphertext under a derivative ID.
- `decrypt_transform_reencrypt`: decrypt with authority, apply public column
  filtering, then encrypt the transformed evidence to new credentials.

The last route never reuses the master ciphertext or master password
implicitly. Every derivative has a new evidence root and lineage to the parent.

## Attestations and limitations

A verification attestation is an Ed25519 signature whose policy context binds
the deterministic SHA-256 of a verification report. It proves that the key
attested that report hash; the recipient must possess or reproduce the report
and independently apply trust policy.

Parsers reject unsafe SVG entities, duplicate carrier manifests, oversized
payloads, unsafe archive paths, uncontrolled broker paths and symlinked guard
components. The Python save guard is scoped and advisory inside one process;
code can bypass it through an unpatched writer or a separate process. Use the
controlled-output broker and operating-system/container permissions when hard
enforcement is required.
