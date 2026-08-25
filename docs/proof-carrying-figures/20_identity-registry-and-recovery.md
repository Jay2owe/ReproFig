# Stage 20 — Recover proof after embedded metadata is stripped

## Why this stage exists

Websites, editors and publisher pipelines may remove metadata or recompress images. A local master still preserves evidence, but recipients need a route from a stripped visible figure back to its signed public record. This stage defines a signed identity registry protocol and an offline-capable client without putting private masters on a public service.

## Prerequisites

- Stages 13, 14 and 16 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stages 13, 14 and 16
- `src/reprofig/sources.py:1-94`
- `src/reprofig/publication.py:1-667`
- `src/reprofig/crypto/trust.py` in its completed form
- `src/reprofig/crypto/signatures.py` in its completed form
- `src/reprofig/artifacts.py:427-564`
- `docs/carrier_survival.md:1-42`

## Scope

- Define a signed registry-entry schema for public figure identity, evidence root, profile, carrier hashes, normalized visual fingerprint and recovery locations.
- Implement a local static registry for offline use and testing.
- Implement a read-only HyperText Transfer Protocol client behind explicit network calls.
- Verify registry-entry signatures and active trust policy before accepting recovery data.
- Resolve exact carrier hashes first, then normalized visual fingerprints with an explicit weaker confidence level.
- Link recovered evidence back to the local master or public bundle without modifying the stripped input silently.
- Support key rotation and signed revocation/update entries.
- Add commands to publish an entry file, resolve an identity and recover a companion bundle.
- Keep private profiles, local paths and encrypted plaintext out of public entries.
- Never perform registry lookup, publication or recovery during ordinary validation, inspection, opening or extraction.

## Out of scope

- Hosting and operating a public registry service is not implemented here.
- Visual fingerprints do not prove identity on their own and cannot replace signatures.
- Recovery does not restore metadata into an uploaded third-party copy without an explicit output path.
- Searching private evidence on public services is forbidden.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/registry.py` | NEW | Registry schema, local store and signed entry handling. |
| `src/reprofig/recovery.py` | NEW | Exact-hash and visual-fingerprint recovery workflow. |
| `src/reprofig/render/fingerprint.py` | NEW | Normalized public visual fingerprint with confidence metadata. |
| `src/reprofig/api.py` | MODIFY | Export explicit registry and recovery operations. |
| `src/reprofig/cli.py` | MODIFY | Add registry entry, resolve and recover commands. |
| `tests/test_registry_recovery.py` | NEW | Test exact, stripped, recompressed, forged and revoked entries. |
| `docs/registry.md` | NEW | Document protocol, privacy and hosting boundary. |

## Implementation sketch

```json
{
  "registry_schema": "reprofig-registry/1",
  "figure_id": "fig-...",
  "public_evidence_root_sha256": "...",
  "profile": "public",
  "carrier_hashes": [{"format": "svg", "sha256": "..."}],
  "visual_fingerprint": {"algorithm": "reprofig-render-fingerprint/v1", "value": "..."},
  "recovery": [{"kind": "bundle", "uri": "https://..."}],
  "signer_fingerprint": "sha256:...",
  "signature": "..."
}
```

Resolution order:

```text
embedded trusted identity -> exact carrier hash -> visible figure identity -> visual fingerprint candidate
```

Only the first three can establish direct identity under a trusted signature. Visual fingerprint matches return candidates requiring signature/evidence confirmation and an explicit confidence report.

## Exit gate

1. An exact copied carrier resolves to one trusted signed entry offline.
2. A metadata-stripped but visually unchanged fixture produces a candidate recovery and verifies the recovered record independently.
3. Recompressed or resized inputs never receive exact-hash status.
4. Forged, untrusted, expired or revoked registry entries fail policy.
5. Public entries contain no master profile, private path, recipient secret or encrypted plaintext.
6. Network access occurs only for explicit resolve/recover commands with size, timeout and content checks.
7. `pytest tests/test_registry_recovery.py -q` passes without network access.
8. Network clients are not imported or called unless the user invokes an explicit remote resolve/recover command.

## Known risks

- Visual fingerprints can collide or change after legitimate edits. Treat them as discovery hints, not cryptographic identity.
- A registry can become a tracking surface. Publish only approved public identifiers and permit offline operation.
- Recovery links can disappear. Registry entries should support multiple locations and content hashes.
