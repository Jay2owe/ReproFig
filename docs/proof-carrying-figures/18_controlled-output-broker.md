# Stage 18 — Promote only verified figures through a controlled output broker

## Why this stage exists

Python hooks cannot stop an agent from manually writing image bytes or undoing a patch. Strong enforcement exists only when the plotting process cannot write to the publishable directory. This stage introduces an opt-in broker for strict agent or publication environments; ordinary saving never uses it implicitly.

## Prerequisites

- Stages 03 and 17 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 03 and Stage 17 files
- `src/reprofig/guard/policy.py` and `src/reprofig/guard/python.py` in their completed forms
- `src/reprofig/artifacts.py:106-188`
- `src/reprofig/artifacts.py:322-426`
- `src/reprofig/cli.py:1-214` plus completed guard commands
- `docs/agent-enforcement.md` in its completed form

## Scope

- Create a temporary run workspace with explicit input, scratch and candidate-output areas.
- Validate candidate paths, symlinks and resolved destinations before promotion.
- Run policy verification in a separate broker process.
- Promote passing artifacts atomically into a controlled destination.
- Produce a signed or hashed promotion receipt linking candidate hash, final hash, policy and verification report.
- Support an advisory same-user mode for development.
- Define hard mode requiring a separate operating-system identity, access-control list or container boundary so agent code cannot write the destination.
- Refuse time-of-check/time-of-use changes by reopening or promoting through held file handles where supported.
- Limit files, bytes, decompression, runtime and subprocess resources.
- Preserve failed candidates in a quarantine directory only when policy explicitly requests it.
- Require explicit broker invocation and destination configuration; installing or importing ReproFig never redirects ordinary output.

## Out of scope

- The broker is not a general arbitrary-code sandbox.
- Network isolation and container orchestration beyond the documented hard-mode contract are deployment concerns.
- Language-specific adapters belong to Stage 19.
- Remote registry upload belongs to Stage 20.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/guard/broker.py` | NEW | Candidate intake, verification and atomic promotion. |
| `src/reprofig/guard/workspace.py` | NEW | Safe workspace layout and resolved-path checks. |
| `src/reprofig/guard/receipts.py` | NEW | Deterministic promotion receipts. |
| `src/reprofig/cli.py` | MODIFY | Add broker/run/promote commands. |
| `src/reprofig/api.py` | MODIFY | Export broker policy and receipt inspection. |
| `tests/test_output_broker.py` | NEW | Test bypass, races, links, traversal and promotion. |
| `docs/agent-enforcement.md` | MODIFY | Document advisory and hard deployment modes. |

## Implementation sketch

```text
agent process identity
  writable: run/input, run/scratch, run/candidates
  denied:   publication-output

broker process identity
  readable: run/candidates
  writable: publication-output
```

```python
@dataclass
class PromotionReceipt:
    receipt_schema: str
    candidate_sha256: str
    final_sha256: str
    final_path: str
    policy_sha256: str
    verification_report_sha256: str
    promoted_at: str

def promote(candidate: Path, destination: Path, policy: OutputPolicy) -> PromotionReceipt: ...
```

The broker must resolve and validate both paths immediately before promotion. Never build destructive commands from untrusted strings. In hard mode, test that the agent identity receives an access-denied error when writing the final directory directly.

## Exit gate

1. A passing proof-carrying figure is atomically promoted with a deterministic receipt.
2. An unsigned, unverified, wrong-profile or insufficient-grade figure never appears at the destination.
3. Path traversal, junctions, symbolic links and destination swaps fail safely.
4. Modifying a candidate after verification cannot promote the changed bytes.
5. Advisory mode labels itself non-enforcing; hard mode demonstrates operating-system denial for direct agent writes.
6. Resource-limit failures leave the destination unchanged.
7. `pytest tests/test_output_broker.py -q` passes on supported Windows and Linux continuous-integration runners.
8. With no broker command or policy active, existing save and publication paths behave exactly as before.

## Known risks

- A broker running as the same unrestricted user cannot provide a hard boundary. The report must state the active isolation mode.
- Cross-platform file and link semantics differ. Resolve targets with native APIs and test Windows junctions separately.
- Quarantine may retain sensitive data. Default to deletion or a private, access-controlled location and record the policy.
