# Expose explicit reproduction through Python and the command line

## Why this stage exists

The runner and comparator need a discoverable, safe entry point. This stage
makes complete reproduction easy while keeping code execution visibly separate
from ordinary inspection and proof verification.

## Prerequisites

- `03_reproduced-figure-comparison_COMPLETED.md`

## Read first

- `docs/figure-reproduction-verification/00_overview.md`
- `AGENTS.md`
- `src/reprofig/reproduction.py`, complete file
- `src/reprofig/api.py`, lines 390-430
- `src/reprofig/__init__.py`, lines 1-140
- `src/reprofig/cli.py`, lines 80-390
- `tests/test_cli.py`, complete file if present; otherwise locate command-line tests before editing

## Scope

- Export the policy, result and high-level reproduction function.
- Add `reprofig reproduce MASTER --bundle-root ROOT --output-dir DIR`.
- Require an explicit acknowledgement flag for trusted producer execution.
- Add timeout, output-size and overwrite options with safe defaults.
- Write the reproduced carrier and JSON report paths to standard output.
- Return nonzero for execution or comparison failure.
- Add `--reproduction-report` to `reprofig verify` for checking an existing report without rerunning code.
- Include actionable error messages for missing bundle inputs or dependencies.

## Out of scope

- Do not silently reproduce during `save`, `inspect`, `extract` or `verify`.
- Do not regenerate project examples; Stage 05 owns them.
- Do not publish the package; Stage 06 owns release operations.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/api.py` | MODIFY | Public reproduction wrapper. |
| `src/reprofig/__init__.py` | MODIFY | Export public symbols. |
| `src/reprofig/cli.py` | MODIFY | Reproduce command and verify report option. |
| `tests/test_cli.py` | MODIFY or NEW | Command success, refusal and exit codes. |
| `tests/test_reproduction.py` | MODIFY | Public API coverage. |

## Implementation sketch

```text
reprofig reproduce Figure.svg \
  --bundle-root . \
  --output-dir verification/reproduced \
  --execute-trusted-producer
```

```python
result = reproduce_figure(
    "Figure.svg",
    bundle_root=".",
    output_dir="verification/reproduced",
    execute_trusted_producer=True,
)
```

The acknowledgement must be mandatory because the producer is arbitrary code.
No interactive prompt is used in library code or automation.

## Exit gate

1. `reprofig reproduce --help` documents execution risk and every output.
2. Omitting `--execute-trusted-producer` refuses to run.
3. Successful command writes one separate carrier and one report.
4. `reprofig verify --require figure_reproduced --reproduction-report ...` passes for the fixture.
5. Python API returns the same deterministic report fields as the command line.
6. CLI and reproduction tests pass.

## Known risks

- Long command help can obscure the security boundary; state it in the command summary and error.
- Windows executable names differ. Resolve only declared allowlisted Python executables and record the resolved runtime.
