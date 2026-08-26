# Stage 21 — Make PyFLASH figures proof-carrying and policy-enforced

## Why this stage exists

PyFLASH already attaches exact plotted tables, statistics and provenance to every saved figure through ReproFig 0.2. It is therefore the best full scientific integration for typed statistical specifications, semantic annotations and agent-enforced output policy. This stage upgrades the existing integration without changing plot appearance or analysis results.

## Prerequisites

- Stages 06 through 18 must all be `_COMPLETED`.

## Read first

For this stage, use the local **PyFLASH repository root** and the local **shared-skills root**; neither absolute development path belongs in the public plan.

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stages 06–18
- `docs/publication-workbook/07_python-and-cli-interfaces_COMPLETED.md:1-end`
- PyFLASH repository root `PyFLASH/provenance.py:1-778`
- PyFLASH repository root `PyFLASH/utils.py:1250-1604`
- PyFLASH repository root `PyFLASH/plotting.py:1-180`
- PyFLASH repository root `tests/test_reprofig_integration.py:1-318`
- shared-skills root `pyflash/scripts/pyflash_runner.py:69-158`
- shared-skills root `pyflash/scripts/pyflash_runner.py:486-659`
- shared-skills root `pyflash/SKILL.md:1-426`

## Scope

- Raise the PyFLASH dependency to the first ReproFig version that contains completed proof features.
- Translate existing PyFLASH statistics attachments into versioned statistical specifications where the method is supported.
- Preserve opaque legacy results honestly when no normative specification exists.
- Bind points, lines, bars, intervals, brackets and statistical text to table rows or statistic identities.
- Use Matplotlib semantic capture at the existing single save choke point.
- Add explicit semantic adapters or lower-grade behavior for Altair and Plotly outputs.
- Keep one figure identity and one evidence root across all requested direct carriers.
- Keep the current exact-data and rederivation save behavior as the default; typed proof, signing, encryption and strict grades activate only when `figure_output` requests them.
- Expose the completed publication-workbook operation as an explicit post-hoc batch action, not an automatic side effect of saving each plot.
- Expose required proof grades, signing, trust, selective encryption and broker policy through the existing `figure_output` runner object.
- Accept key/trust paths or protected descriptors, never literal passwords/private-key contents in requests.
- Report achieved grades and verification receipts alongside generated figure paths.
- Update the installed PyFLASH skill so agent-created plots request and report proof rather than only metadata presence.

## Out of scope

- Do not change statistical methods, plot aesthetics or existing result values.
- Do not independently implement PyFLASH statistics inside PyFLASH; use ReproFig’s reference registry.
- Unsupported PyFLASH models remain statistics-reproduced or internally consistent, not independently verified.
- PyMicroglia and general plotting skill changes belong to Stages 22 and 23.

## Files touched

| path | change | reason |
|---|---|---|
| PyFLASH repository root `PyFLASH/provenance.py` | MODIFY | Map attached data/statistics/claims into typed proof evidence. |
| PyFLASH repository root `PyFLASH/utils.py` | MODIFY | Capture semantics, verify policy and retain one root across carriers. |
| PyFLASH repository root `PyFLASH/plotting.py` | MODIFY | Bind plot-specific statistical annotations and non-Matplotlib outputs. |
| PyFLASH repository root `pyproject.toml` | MODIFY | Require the proof-capable ReproFig version. |
| PyFLASH repository root `tests/test_reprofig_integration.py` | MODIFY | Cover independent statistics, visual bindings, profiles and tampering. |
| shared-skills root `pyflash/scripts/pyflash_runner.py` | MODIFY | Add proof policy, broker inputs and result reporting. |
| shared-skills root `pyflash/SKILL.md` | MODIFY | Require verification for agent-produced saved plots. |
| shared-skills root `pyflash/references/reprofig-output.md` | MODIFY | Document safe keys, grades, encryption and publication behavior. |

## Implementation sketch

Extend the existing attachment contract rather than creating another save path:

```python
_attach_reprofig(
    figure,
    plotted_data=table,
    statistics=legacy_records,
    statistical_specs=typed_specs,
    claims=claims,
    semantic_bindings=bindings,
)
```

Runner request extension:

```json
{
  "figure_output": {
    "formats": ["svg", "pdf", "png"],
    "profile": "master",
    "required_grades": ["internally_consistent", "statistics_independently_verified", "display_verified"],
    "signing_key_path": "approved-key-reference",
    "trust_policy_path": "approved-trust-policy.json",
    "encrypt_sections": ["source_data", "participant_table"],
    "recipient_file": "approved-recipients.json",
    "broker_policy_path": "publication-policy.json"
  }
}
```

An explicit batch request may additionally contain:

```json
{
  "publication_workbook": {
    "artifacts": ["approved-output-directory"],
    "output_path": "Publication-source-data.xlsx",
    "statistics_ledger_path": "all-tests.json",
    "profile": "master"
  }
}
```

The runner calls ReproFig's completed workbook interface after the plot batch; absence of this object preserves current behavior.

Equivalent-script output must preserve these settings without printing secrets. The resident worker restores every temporary policy after a request.

For each plot family, tests should assert the strongest honest grade. Descriptive plots with no inferential statistics can be independently checked for data/geometry while reporting statistics as not applicable.

## Exit gate

1. Representative bar, scatter, line, matrix, regression and statistical-annotation figures bind visible objects to exact table/statistic identities.
2. Supported common tests independently reproduce; unsupported methods receive an explicit lower status.
3. Altering a displayed probability value, moving a bracket or changing a source row causes the expected verification failure.
4. Every requested carrier shares one evidence root and its appropriate visual-verification status.
5. Public and minimal-public outputs reveal no local paths, private columns, key material or decrypted sections.
6. Runner policy is scoped per request and reports achieved grades/receipts without leaking secrets.
7. The PyFLASH skill validator passes and its discovery/runner tests expose no undocumented output fields.
8. The complete PyFLASH test suite passes with no changed scientific results or visual baselines.
9. Existing PyFLASH calls with no proof or workbook policy produce the same outputs and require no proof, cryptographic or Excel extras.

## Known risks

- PyFLASH has many plot families and heterogeneous legacy statistics. Convert only methods with complete specifications and report the rest honestly.
- Broad automatic artist capture may misbind reused axes. Plot-specific tests must check row/statistic identity, not only manifest presence.
- Existing worktrees may contain unrelated changes. Preserve them and do not commit or publish without scoped approval.
