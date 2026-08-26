# Introduce explicit statistical verification terminology

## Why this stage exists

The current `reproduced` name sounds like a complete figure rerun even though
the implementation only recalculates statistics. Clear canonical names are a
prerequisite for adding the real figure-reproduction grade without creating two
different meanings for the same label.

## Prerequisites

None.

## Read first

- `docs/figure-reproduction-verification/00_overview.md`
- `AGENTS.md`
- `src/reprofig/verification.py`, lines 1-318
- `src/reprofig/stats/engine.py`, lines 120-190
- `src/reprofig/guard/policy.py`, lines 1-45
- `tests/test_proof_core.py`, complete file
- `tests/test_statistics_matrix.py`, complete file

## Scope

- Replace canonical `reproduced` with `statistics_reproduced`.
- Replace canonical `independently_verified` with `statistics_independently_verified`.
- Add `figure_reproduced` to the canonical verification meanings.
- Normalize legacy required-meaning inputs to the new names.
- Normalize legacy embedded check meanings while reading old records.
- Make reports emit canonical names.
- Update all statistical engine statuses and tests.

## Out of scope

- Do not execute plotting code; Stage 02 owns execution.
- Do not compare a reproduced carrier; Stage 03 owns comparison.
- Do not change command-line interfaces beyond accepting aliases; Stage 04 owns public commands.
- Do not regenerate examples; Stage 05 owns examples.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/verification.py` | MODIFY | Canonical meanings and alias normalization. |
| `src/reprofig/stats/engine.py` | MODIFY | Emit explicit statistical meanings. |
| `src/reprofig/guard/policy.py` | MODIFY | Accept legacy policy names through normalization. |
| `tests/test_proof_core.py` | MODIFY | Assert canonical and legacy behavior. |
| `tests/test_statistics_matrix.py` | MODIFY | Assert independent-statistics naming. |
| `tests/test_broker_and_registry.py` | MODIFY | Update policy expectations. |

## Implementation sketch

```python
VERIFICATION_MEANINGS = (
    "display_verified",
    "internally_consistent",
    "statistics_reproduced",
    "statistics_independently_verified",
    "figure_reproduced",
    "source_linked",
    "signature_valid",
    "signer_trusted",
    "attested",
)

LEGACY_MEANING_ALIASES = {
    "reproduced": "statistics_reproduced",
    "independently_verified": "statistics_independently_verified",
}

def normalize_verification_meaning(value: str) -> str:
    return LEGACY_MEANING_ALIASES.get(value, value)
```

`ProofCheck` and required-policy parsing must normalize once at their boundary.
Do not emit both alias and canonical keys in new reports.

## Exit gate

1. Existing records containing either legacy meaning load without error.
2. `verify_proof(required=["reproduced"])` behaves like `statistics_reproduced`.
3. New reports contain the nine canonical meanings only.
4. Statistical checks emit `statistics_reproduced` or `statistics_independently_verified` correctly.
5. Focused proof, statistics and broker tests pass.

## Known risks

- Downstream consumers may index the old report keys. Preserve input compatibility and document the output migration.
- Alias normalization must happen before unknown-meaning validation or old policies will fail.
