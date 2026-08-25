# Stage 25 — Document, migrate and release proof-carrying ReproFig

## Why this stage exists

The system is useful only if researchers can understand exactly what each proof grade, signature and encrypted section means. A security-sensitive release also needs a migration path, reproducible build and public record of limitations. This stage turns the completed implementation into a versioned, citable release without overstating what it proves.

## Prerequisites

- Stages 01 through 24 must all be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- all completed stage files 01–24
- `README.md:1-115`
- `CHANGELOG.md:1-17`
- `pyproject.toml:1-71`
- `CITATION.cff:1-12`
- `docs/schema.md:1-27` plus completed proof additions
- `docs/security.md:1-end` in its completed form
- `docs/carrier_survival.md:1-42` plus Stage 24 results
- `docs/publication_workbook.md:1-end`
- `.github/workflows/release.yml:1-49`

## Scope

- Choose the next package version from the final compatibility decision and update package/citation metadata consistently.
- Keep the main installation choices to three: base ReproFig, `[excel]` for workbooks alone, and `[proof]` for the complete rigorous path including Excel, independent verification, visual checking and cryptography. Existing carrier-format extras remain secondary reference material.
- Write one user-facing guide from source data through independent statistics, visual verification, signing, trust, encryption and broker enforcement.
- Document every verification grade and its non-guarantees.
- Document safe key creation, backup, rotation, revocation and selective decryption workflows.
- Add `reprofig/1` migration and mixed-version compatibility guidance.
- Publish the measured carrier-survival and adversarial-test results.
- Add concise examples for ordinary researchers and agent/tool integrators.
- Lead with the unchanged base save-and-extract workflow, then show publication workbooks, independent verification and cryptography as progressively deeper opt-in levels.
- Run complete tests, clean builds, metadata checks and install-from-wheel smoke tests.
- Run the repository’s publication-safety guard before commit or push.
- Require explicit user approval before GitHub tag/push or Python Package Index upload.
- After approval, publish, verify the live package in a clean environment and record the release.

## Out of scope

- No new algorithm, carrier, adapter or feature enters this stage.
- Documentation must not call source data true or a test scientifically appropriate merely because it verifies.
- Do not expose real private keys, passwords or confidential example data.
- Hosting a public identity registry remains separate operational work.

## Files touched

| path | change | reason |
|---|---|---|
| `README.md` | MODIFY | Present the proof-carrying workflow and quickest safe examples. |
| `CHANGELOG.md` | MODIFY | Record every new schema, verifier, security and compatibility change. |
| `pyproject.toml` | MODIFY | Set release version, extras and metadata. |
| `CITATION.cff` | MODIFY | Keep citable version and release date current. |
| `docs/proof-carrying-verification.md` | NEW | Complete user and integrator guide. |
| `docs/schema.md` | MODIFY | Publish final schema/version and migration details. |
| `docs/security.md` | MODIFY | Publish threat model, key/encryption operations and limitations. |
| `PUBLISHING_AUDIT.md` | MODIFY | Record final release-readiness audit and resolved blockers. |

## Implementation sketch

The guide should lead with an end-to-end command sequence using non-sensitive fixtures:

```text
create proof-carrying master
verify source reconstruction
verify supported statistics
verify visible output
encrypt selected sections
sign evidence root
verify signature and trust policy
derive and sign public copy
promote through controlled broker
recover stripped metadata by trusted identity
```

Release gate commands must use the project’s actual supported environment and include at minimum:

```text
pytest -q
python -m build
python -m twine check dist/*
clean-environment wheel install
reprofig formats
reprofig verify signed-encrypted-fixture --require internally_consistent
```

Before external publication, invoke the available `push-guard`, `publish-audit`, `pypi-publisher` and `pypi-upload` workflows according to their instructions. Do not place credentials in configuration committed to the repository.

## Exit gate

1. Version, changelog and citation metadata agree.
2. The guide explains valid-versus-trusted signatures and ciphertext-versus-decrypted verification with runnable examples.
3. Existing `reprofig/1` examples still work and migration is explicit.
4. Every advertised grade and carrier capability has an automated test reference.
5. Full tests, build checks and clean wheel installation pass.
6. Publication audit and push guard report no secrets, private paths or unsafe tracked files.
7. After explicit approval, the GitHub release/tag and Python Package Index version are live and installable from a clean environment.
8. The release record preserves exact commit, artifacts, hashes and citation metadata.
9. A clean base-only install passes the original simple save, inspect and extraction workflow without Excel, statistics, visual or cryptographic dependencies.

## Known risks

- Marketing language can overstate proof. Use the exact grade vocabulary and repeat that verification proves consistency, not experimental truth or methodological suitability.
- Release credentials and private keys are separate secrets. Never reuse signing keys as registry-upload credentials.
- A version may already exist on the package index and cannot be overwritten. Verify availability before tagging and build once from the exact release commit.
