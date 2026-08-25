# Stage 22 — Make every PyMicroglia figure action proof-carrying

## Why this stage exists

PyMicroglia already has one ReproFig render path and requires every figure to provide its exact plotted table. Its smaller, action-registered architecture can demonstrate that proof policy is discoverable and consistent across a complete scientific package. This stage upgrades the central save route and all six quality-control/overlay callers without letting catalogue generation erase the new contract.

## Prerequisites

- Stages 06 through 18 must all be `_COMPLETED`.

## Read first

For this stage, use the local **PyMicroglia repository root** and the local **shared-skills root**; neither absolute development path belongs in the public plan.

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stages 06–18
- `docs/publication-workbook/07_python-and-cli-interfaces_COMPLETED.md:1-end`
- PyMicroglia repository root `src/pymicroglia/visualisation/panels.py:333-583`
- PyMicroglia repository root `src/pymicroglia/visualisation/qc.py:125-473`
- PyMicroglia repository root `src/pymicroglia/visualisation/overlays.py:56-225`
- PyMicroglia repository root `tools/regenerate_catalogue.py:395-566`
- PyMicroglia repository root `tests/test_reprofig_adapter.py:1-142`
- PyMicroglia repository root `tests/test_visualisation_limits.py:120-205`
- shared-skills root `pymicroglia/SKILL.md:1-272`

## Scope

- Raise the dependency to the proof-capable ReproFig version.
- Extend the single `panels.save` route with semantic capture, verification policy, signing and encrypted-section options.
- Bind exact plotted rows/series and descriptive annotations for registration, cosmic-ray, channel, frame, cell and region figures.
- Preserve `statistics_status=not_applicable` where a figure makes no inferential claim.
- Map trace-panel statistics and claims into typed specifications when present without inventing tests.
- Expose the complete proof policy in every registered figure action through the catalogue generator.
- Regenerate `actions.json` from source rather than editing it by hand.
- Preserve master bundles and public/minimal-public privacy behavior.
- Keep current exact-table figure actions working with no proof policy; advanced verification fields remain optional catalogue parameters with inert defaults.
- Expose publication-workbook construction as a separate batch action rather than generating a workbook for each saved figure.
- Update the installed PyMicroglia skill to request required grades and handle protected key references safely.

## Out of scope

- Do not add new scientific analyses or change image-processing outputs.
- Do not give descriptive quality-control figures artificial probability values.
- PyFLASH and general plotting work belongs to Stages 21 and 23.
- The package must continue to import without plotting/statistics extras until a figure action runs.

## Files touched

| path | change | reason |
|---|---|---|
| PyMicroglia repository root `src/pymicroglia/visualisation/panels.py` | MODIFY | Central proof record, semantic capture, verification and broker policy. |
| PyMicroglia repository root `src/pymicroglia/visualisation/qc.py` | MODIFY | Bind quality-control marks and annotations to exact evidence. |
| PyMicroglia repository root `src/pymicroglia/visualisation/overlays.py` | MODIFY | Bind labels, regions and outlines to table/object identities. |
| PyMicroglia repository root `tools/regenerate_catalogue.py` | MODIFY | Define proof policy parameters as the source of truth. |
| PyMicroglia repository root `src/pymicroglia/data/actions.json` | MODIFY | Regenerated action catalogue containing the new parameters. |
| PyMicroglia repository root `tests/test_reprofig_adapter.py` | MODIFY | Verify proof grades, encryption privacy, signatures and tampering. |
| PyMicroglia repository root `pyproject.toml` | MODIFY | Require the proof-capable ReproFig version. |
| shared-skills root `pymicroglia/SKILL.md` | MODIFY | Require and explain proof-carrying figure output. |

## Implementation sketch

Extend the central save contract:

```python
panels.save(
    figure,
    path,
    table=exact_table,
    statistical_specs=(),
    semantic_bindings=bindings,
    required_grades=(),
    signing_key=None,
    trust_policy=None,
    encrypted_sections=(),
    recipients=None,
    broker_policy=None,
    ...,
)
```

The generator must define the shared policy once and add it to every figure action:

```text
required_grades
signing_key_path
trust_policy_path
encrypt_sections
recipient_file
broker_policy_path
```

Paths are references resolved by the local runner; passwords and key bytes are never catalogue parameters.

Add one explicit batch action that accepts existing figure artifact paths, an output workbook path and an optional statistics-ledger path, then delegates to `build_publication_workbook`. Do not add workbook generation to the six individual figure actions.

Object overlays should bind each label/region record to its visible outline and tag. Trace panels bind each displayed series to its prepared table rows. Image panels record source frame/channel identities and image normalization as render facts.

## Exit gate

1. Every registered figure action accepts exactly the generated proof-policy parameters.
2. The sole ReproFig save path remains structurally enforced by tests.
3. Trace, registration, image and overlay fixtures bind their visible evidence to exact table/object identities.
4. Descriptive figures achieve internal/display grades without inventing inferential statistics.
5. Public bundles contain no source path, subject value, key material or decrypted protected section.
6. Catalogue regeneration and installed skill references are current.
7. PyMicroglia doctor reports no catalogue complaints or pending actions.
8. The complete PyMicroglia test suite passes with unchanged scientific outputs.
9. Existing figure actions with no advanced policy require no proof, cryptographic or Excel extras.

## Known risks

- Generated catalogues will erase hand edits. Update `tools/regenerate_catalogue.py` first and regenerate.
- Image normalization and colour maps can vary without changing data. Record them as render facts and use appropriate raster tolerances.
- The existing repository may contain unrelated refactors. Preserve them and do not commit or publish without scoped approval.
