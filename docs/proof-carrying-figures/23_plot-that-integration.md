# Stage 23 — Make `plot-that` require and report proof grades

## Why this stage exists

`plot-that` is the general route through which agents create scientific figures outside PyFLASH and PyMicroglia. Updating it turns proof-carrying output from a package feature into an everyday agent behavior. The skill must still be honest: it can require evidence and verification, but it cannot invent missing source lineage or statistical specifications.

## Prerequisites

- Stages 17, 18, 21 and 22 must be `_COMPLETED`.

## Read first

For this stage, the **shared-skills root** is `C:/Users/Owner/UK Dementia Research Institute Dropbox/Brancaccio Lab/Jamie/Macros and Scripts/Claude/shared-skills`.

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stages 17, 18, 21 and 22
- `docs/publication-workbook/07_python-and-cli-interfaces_COMPLETED.md:1-end`
- shared-skills root `plot-that/SKILL.md:1-117`
- shared-skills root `plot-that/scripts/reprofig_bundle.py:1-606`
- shared-skills root `plot-that/scripts/plot_style.py:1-349`
- shared-skills root `plot-that/scripts/register.py:1-1021`
- shared-skills root `plot-that/scripts/recipes/review-template.json:1-12`
- shared-skills root `plot-that/scripts/tests/test_multiformat_reprofig.py:1-195`
- shared-skills root `plot-that/references/reprofig-formats.md:1-72`

## Scope

- Require exact plotted data and declared statistics before saving inferential figures.
- Add proof-policy fields to the review recipe.
- Route saved figures through semantic capture and the controlled broker when required.
- Verify source reconstruction, supported statistics and visual output before registration.
- Support signing and selective encrypted evidence through file/key references, never literal secrets in prompts.
- Record achieved grades, signer trust and inaccessible evidence in the figure registry.
- Refuse a requested proof grade when evidence is missing; do not silently downgrade.
- Preserve all sixteen current ReproFig carriers and publication profiles.
- Teach the skill to describe lower grades plainly for unsupported tests or raster-only evidence.
- Preserve today's audited ReproFig bundle as the default path; strict grades, signing, encryption and publication-workbook creation require explicit recipe fields.

## Out of scope

- The skill does not implement new statistical algorithms.
- It does not claim that a scientifically inappropriate test is appropriate because it reproduces.
- It does not expose private keys or request passwords in ordinary conversation.
- Package-specific bindings stay in Stages 21 and 22.

## Files touched

| path | change | reason |
|---|---|---|
| shared-skills root `plot-that/SKILL.md` | MODIFY | Require proof workflow and honest grade reporting. |
| shared-skills root `plot-that/scripts/reprofig_bundle.py` | MODIFY | Build typed evidence, sign/encrypt and call verification/broker APIs. |
| shared-skills root `plot-that/scripts/plot_style.py` | MODIFY | Apply semantic artist bindings at the plotting choke point. |
| shared-skills root `plot-that/scripts/register.py` | MODIFY | Store proof grades, evidence roots, signer trust and receipts. |
| shared-skills root `plot-that/scripts/recipes/review-template.json` | MODIFY | Add non-secret proof-policy fields. |
| shared-skills root `plot-that/scripts/tests/test_multiformat_reprofig.py` | MODIFY | Test all carriers with shared roots and required grades. |
| shared-skills root `plot-that/scripts/tests/test_register.py` | MODIFY | Test registry proof fields and downgrade behavior. |
| shared-skills root `plot-that/references/reprofig-formats.md` | MODIFY | Document verification, signatures, encryption and carrier limits. |

## Implementation sketch

Review recipe extension:

```json
{
  "required_grades": ["internally_consistent", "display_verified"],
  "independent_statistics_required": true,
  "signing_key_path": null,
  "trust_policy_path": null,
  "encrypt_sections": [],
  "recipient_file": null,
  "broker_policy_path": null,
  "publication_workbook": null
}
```

When `publication_workbook` is an object, it supplies an output path and optional experiment-ledger path and is processed once after every requested figure succeeds. When it is `null` or absent, the current figure-bundle workflow is unchanged.

Output report shown to the agent/user:

```text
figure: Figure 1.svg
evidence root: sha256:...
source-linked: pass
independent statistics: pass (4/4)
display verification: pass
signature: valid
signer trust: trusted under project policy
protected sections: 1 (not inspected without key)
```

If a test is unsupported, show `independent statistics: unsupported` and fail only when the recipe requires that grade.

## Exit gate

1. A supported statistical plot cannot be registered until required source, statistical and display checks pass.
2. A descriptive plot records statistics as not applicable and receives only appropriate grades.
3. Altered data, annotation text or geometry prevents registration under a strict recipe.
4. Signing/encryption configuration uses paths/descriptors and never serializes secrets into prompts or logs.
5. All sixteen carrier tests retain one evidence root and report carrier-appropriate visual grades.
6. Registry search can filter by achieved grade, trusted signer and inaccessible evidence.
7. The skill validator passes and every script test passes.
8. A recipe without advanced proof fields follows the current simple bundle workflow and never asks the user for a key or journal metadata.

## Known risks

- A skill instruction is not itself enforcement. Strict recipes must use the Stage 18 broker.
- Generic plots may not supply enough semantic meaning automatically. Refuse strong grades rather than guessing.
- Registry records can leak source context. Apply profile/privacy rules before registration.
