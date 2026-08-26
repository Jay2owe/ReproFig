# Publish the completed reproduction release

## Why this stage exists

The new meanings and explicit reproduction workflow change ReproFig's public
contract. A clean versioned release must reach GitHub and the Python Package
Index together, followed by a fresh-install check so users do not receive stale
documentation or code.

## Prerequisites

- `05_integrations-and-examples_COMPLETED.md`

## Read first

- `docs/figure-reproduction-verification/00_overview.md`
- `AGENTS.md`
- `pyproject.toml`, complete file
- `src/reprofig/__init__.py`, complete file
- `CHANGELOG.md`, top release sections
- `CITATION.cff`, complete file
- `.github/workflows/ci.yml`, complete file
- `PUBLISHING_AUDIT.md`, after regenerating it

## Scope

- Select the next available semantic version after checking the Python Package Index.
- Update package, citation, changelog and continuous-integration version assertions.
- Run the complete tests, clean build, metadata check and wheel smoke install.
- Audit wheel and source archive contents for private paths, secrets and generated junk.
- Run publish-audit and resolve every release blocker.
- Run push-guard against the staged and committed public tree.
- Commit the complete change set and push the main branch.
- Upload wheel and source archive to the real Python Package Index.
- Create and push a matching Git tag and GitHub release if the repository's existing release pattern uses them.
- Verify the registry page and install the published version in a fresh environment.

## Out of scope

- Do not overwrite an existing Python Package Index version.
- Do not force-push or rewrite public history.
- Do not publish private master figures outside this explicitly synthetic example set.

## Files touched

| path | change | reason |
|---|---|---|
| `pyproject.toml` | MODIFY | Release version and metadata. |
| `src/reprofig/__init__.py` | MODIFY | Runtime version. |
| `CHANGELOG.md` | MODIFY | User-visible release notes. |
| `CITATION.cff` | MODIFY | Citable version and date. |
| `.github/workflows/ci.yml` | MODIFY | Version assertion. |
| `PUBLISHING_AUDIT.md` | MODIFY | Final release-readiness evidence. |

## Implementation sketch

Release order:

```text
tests -> build -> artifact audit -> publish audit -> stage -> push guard
-> commit -> push main -> upload Python Package Index -> tag/release
-> fresh install and registry verification
```

The Python Package Index upload must use the local token-file helper without
printing token contents. Uploaded releases are immutable; any partial failure
requires a new version.

## Exit gate

1. Full test suite passes.
2. `python -m twine check dist/*` passes.
3. Wheel smoke import reports the intended version and all sixteen formats.
4. Artifact and push-guard scans contain no blocking finding.
5. Main branch is pushed and clean relative to the public remote.
6. Python Package Index serves both wheel and source archive for the new version.
7. A fresh environment installs that exact version and passes import/command-line smoke tests.
8. Generated examples still verify with zero plot-that drift after the release version is embedded.

## Known risks

- Package publication cannot be rolled back. Stop before upload if any audit is unresolved.
- GitHub and the Python Package Index can become temporarily inconsistent if one succeeds first; complete post-release checks before reporting success.
- Token files must never be read into tool output or committed.
