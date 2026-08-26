# Update integrations and regenerate every verification example

## Why this stage exists

The public behavior is only understandable if the examples show the actual
saved reproduced carrier. Plotting integrations must also request the new
canonical statistical names so users do not receive stale or ambiguous grades.

## Prerequisites

- `04_public-api-and-cli_COMPLETED.md`

## Read first

- `docs/figure-reproduction-verification/00_overview.md`
- `AGENTS.md`
- `README.md`, complete file
- `docs/proof-carrying-verification.md`, complete file
- `docs/statistical-verification.md`, complete file
- `examples/general-figure-verification-demo/code/build_demo.py`, complete file
- `examples/general-figure-verification-demo/code/plot.py`, complete file
- plot-that `SKILL.md`, complete file

## Scope

- Update proof documentation to the nine formal meanings.
- Correct old prose that claimed `reproduced` already reran producer code.
- Update plot-that proof-policy names and require a standalone runnable producer for figure reproduction.
- Add a dedicated `figure_reproduced` demonstration folder.
- Rename demonstration layers to explicit statistical meanings.
- Run the reproduction API for the figure layer and preserve its carrier/report.
- Include `figure_reproduced` in the final attested full stack.
- Regenerate the overview timeline, all layer figures, reports and unpacked evidence.
- Register every private carrier and verify zero drift.
- Visually inspect the overview, statistical reproduction, figure reproduction and attested previews.

## Out of scope

- Do not publish or tag; Stage 06 owns release operations.
- Do not upload master example figures outside the approved public repository; they intentionally contain synthetic row-level data only.

## Files touched

| path | change | reason |
|---|---|---|
| `README.md` | MODIFY | Public terminology and reproduction quick start. |
| `docs/proof-carrying-verification.md` | MODIFY | Exact grade boundaries and command examples. |
| `docs/statistical-verification.md` | MODIFY | Explicit statistical grade names. |
| `examples/general-figure-verification-demo/**` | MODIFY | Ten-layer regenerated demonstration and saved reproduced carrier. |
| plot-that `SKILL.md` | MODIFY | Canonical meanings and explicit reproduction workflow. |

## Implementation sketch

The demonstration sequence becomes:

```text
00 traceable carrier
01 internally consistent
02 statistics reproduced
03 statistics independently verified
04 figure reproduced
05 display verified
06 source linked
07 signature valid
08 signer trusted
09 attested full stack
```

Layer 04 must contain:

```text
verification/reproduced/raw-user-input-comparison.reproduced.svg
verification/reproduction-report.json
```

The overview must say that Layers 02 and 03 are alternative statistical grades,
while Layer 04 is an actual producer rerun with a saved comparison artifact.

## Exit gate

1. All ten layer reports are valid and contain the expected canonical meaning.
2. Layer 04 retains the separate reproduced Scalable Vector Graphics carrier.
3. Layer 09 passes `figure_reproduced` plus internal, independent-statistics, display, source, signature, trust and attestation checks.
4. Every bundle has exact data, statistics, source index, standalone producer, preview and unpacked evidence.
5. Plot-that registry reports zero drift for every bundle and overview.
6. Privacy scan finds no private path, key or application-specific prerequisite.
7. Visual inspection finds no clipping, overlap or ambiguous layer title.

## Known risks

- Registering after signing must preserve the evidence root; the reproduction report binds that stable root so signature-only additions do not invalidate it.
- A reproduced output may receive a fresh figure identifier; comparisons bind the master evidence root and independently recomputed content rather than requiring identifier equality.
- Generated examples can bloat the repository; synthetic examples are explicitly approved for this release.
