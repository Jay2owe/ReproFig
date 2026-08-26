# Run a recorded producer and preserve its output safely

## Why this stage exists

A meaningful reproduced figure must come from an actual producer run, not a
statistical recalculation. This stage creates the explicit execution boundary
that later comparison and reporting can trust.

## Prerequisites

- `01_verification-terminology_COMPLETED.md`

## Read first

- `docs/figure-reproduction-verification/00_overview.md`
- `AGENTS.md`
- `src/reprofig/schema.py`, lines 420-510
- `src/reprofig/artifacts.py`, lines 228-293
- `src/reprofig/guard/broker.py`, complete file
- `src/reprofig/guard/policy.py`, complete file
- `src/reprofig/guard/python.py`, complete file
- `tests/test_broker_and_registry.py`, complete file

## Scope

- Add a reproduction policy with runtime, output-count and output-size limits.
- Require explicit invocation; never hook reproduction into ordinary verification.
- Materialize the embedded producer and data tables in a temporary workspace.
- Copy and hash declared bundle-relative source inputs when a bundle root is supplied.
- Parse command arguments without a shell.
- Run the producer with a controlled working directory and environment.
- Require the declared output path to exist.
- Copy the output atomically to `verification/reproduced/<stem>.reproduced.<ext>`.
- Capture bounded standard output, standard error, return code, duration and dependency facts.
- Never overwrite the master.

## Out of scope

- Do not claim the output matches the master; Stage 03 owns comparison.
- Do not expose the command publicly; Stage 04 owns interfaces.
- Do not add network or operating-system container guarantees that are unavailable in-process.
- Do not regenerate demonstration bundles; Stage 05 owns them.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/reproduction.py` | NEW | Policy, workspace materialization, execution and result model. |
| `src/reprofig/schema.py` | MODIFY | Validate structured reproduction metadata where needed. |
| `src/reprofig/artifacts.py` | MODIFY | Reuse safe extraction and atomic output helpers. |
| `tests/test_reproduction.py` | NEW | Runner success, failure, limits and overwrite protection. |

## Implementation sketch

```python
@dataclass(frozen=True)
class ReproductionPolicy:
    timeout_seconds: float = 120.0
    max_output_bytes: int = 100_000_000
    max_log_bytes: int = 1_000_000
    allow_network: bool = False
    allowed_executables: tuple[str, ...] = ("python", "python3")

@dataclass
class FigureReproductionResult:
    source_figure_id: str
    master_path: str
    reproduced_path: str | None
    command: list[str]
    return_code: int | None
    duration_seconds: float
    stdout: str
    stderr: str
    output_sha256: str | None
    status: str
    message: str

def run_figure_reproduction(
    artifact,
    *,
    output_dir,
    bundle_root=None,
    policy=ReproductionPolicy(),
) -> FigureReproductionResult: ...
```

The command must use `subprocess.run(..., shell=False, cwd=workspace,
timeout=...)`. The copied destination is new or explicitly overwrite-enabled;
it is never the master path.

## Exit gate

1. A fixture producer writes a separate reproduced Scalable Vector Graphics file.
2. The master hash is unchanged before and after reproduction.
3. Missing script, command, input or output returns an explicit unavailable/fail result.
4. Timeouts and oversized outputs fail closed.
5. Shell metacharacters are passed as arguments and never interpreted by a shell.
6. `tests/test_reproduction.py` passes.

## Known risks

- A Python subprocess is not a full security sandbox. Keep execution explicit, bounded and documented as trusted-code execution.
- Old producers may rely on absolute paths. Refuse or require an explicit bundle-root mapping rather than guessing.
- Cloud-synced folders may briefly lock atomic candidates; use bounded retries without hiding other errors.
