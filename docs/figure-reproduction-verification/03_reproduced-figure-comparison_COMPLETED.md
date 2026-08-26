# Compare the reproduced carrier and issue the figure grade

## Why this stage exists

Successfully running a script only proves that it ran. The saved output earns
`figure_reproduced` only when its embedded data, statistics and proof-relevant
visible content agree with the master.

## Prerequisites

- `02_isolated-reproduction-runner_COMPLETED.md`

## Read first

- `docs/figure-reproduction-verification/00_overview.md`
- `AGENTS.md`
- `src/reprofig/reproduction.py`, complete file
- `src/reprofig/verification.py`, lines 1-318
- `src/reprofig/render/svg_verify.py`, complete file
- `src/reprofig/render/raster_verify.py`, complete file
- `src/reprofig/evidence.py`, complete file
- `tests/test_proof_visual_hardening.py`, complete file

## Scope

- Add deterministic master-versus-reproduced record comparison.
- Compare canonical data-table hashes and normalized statistical records.
- Compare semantic render bindings for vector output.
- Compare canonical raster reference or declared pixel tolerances where supported.
- Record the reproduced-carrier hash and relative saved path.
- Write `verification/reproduction-report.json` beside the output.
- Return `figure_reproduced=pass` only when execution and every required comparison pass.
- Support explicit reproduction-report input to `verify_proof` without executing code.
- Make unavailable, unsupported and mismatch states precise.

## Out of scope

- Do not run code from ordinary `verify`; Stage 02's explicit runner remains the only executor.
- Do not sign or trust the reproduced output automatically.
- Do not add public command syntax; Stage 04 owns that interface.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/reproduction.py` | MODIFY | Comparison and deterministic report serialization. |
| `src/reprofig/verification.py` | MODIFY | Consume an explicit reproduction report. |
| `src/reprofig/render/svg_verify.py` | MODIFY | Reuse normalized semantic comparison. |
| `src/reprofig/render/raster_verify.py` | MODIFY | Reuse bounded raster comparison where supported. |
| `tests/test_reproduction.py` | MODIFY | Data, statistics and visible mismatch coverage. |
| `tests/test_proof_visual_hardening.py` | MODIFY | Figure-reproduction tamper failures. |

## Implementation sketch

```json
{
  "schema": "reprofig/figure-reproduction-report/1",
  "source_figure_id": "rf-...",
  "master_sha256": "...",
  "reproduced_path": "verification/reproduced/Figure.reproduced.svg",
  "reproduced_sha256": "...",
  "execution": {"status": "pass", "return_code": 0},
  "comparisons": {
    "data_tables": "pass",
    "statistics": "pass",
    "display": "pass"
  },
  "valid": true
}
```

```python
verify_proof(
    master,
    required=["figure_reproduced"],
    reproduction_report="verification/reproduction-report.json",
)
```

Verification must check the report schema, master hash, reproduced hash and all
comparison statuses. Merely loading a JSON file that says `valid=true` is not
sufficient.

## Exit gate

1. A regenerated equivalent fixture receives `figure_reproduced=pass`.
2. Changed plotted data fails the data comparison.
3. Changed exact p-value fails the statistics comparison.
4. Changed bound label or geometry fails the display comparison.
5. A report copied from another master fails its master-hash binding.
6. The reproduced carrier remains available at the reported path.
7. Focused reproduction and visual-hardening tests pass.

## Known risks

- Metadata such as timestamps and random figure identifiers must not cause false visual or evidence mismatches.
- Stochastic producers require recorded seeds or must report unsupported rather than pass.
- Pixel comparison should be tolerant only where a declared renderer difference justifies it.
