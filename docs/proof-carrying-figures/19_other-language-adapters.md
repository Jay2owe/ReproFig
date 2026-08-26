# Stage 19 — Provide the enforcement contract to R, Julia, JavaScript and MATLAB

## Why this stage exists

Proof-carrying figures are a general scientific need, not a Python-only feature. Reimplementing schemas and cryptography in every language would create incompatible evidence. This stage defines a thin adapter protocol in which other languages describe a figure and hand candidates to the same ReproFig verifier and output broker.

## Prerequisites

- Stages 03, 05, 09 and 18 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stages 03, 05, 09 and 18
- `src/reprofig/cli.py:1-214` plus completed verification/broker commands
- `src/reprofig/schema.py:1-353` plus completed proof schema additions
- `src/reprofig/guard/broker.py` in its completed form
- `docs/agent-enforcement.md` in its completed form
- `docs/schema.md:1-27` plus completed proof schema documentation

## Scope

- Define a language-neutral adapter request/response schema over standard input/output and files.
- Keep canonicalization, verification, signing and encryption in ReproFig rather than reimplementing them in each adapter.
- Add one thin reference adapter for R graphics/`ggsave` routes.
- Add one thin reference adapter for Julia `savefig` routes.
- Add one thin reference adapter for JavaScript server-side figure export.
- Add one thin reference adapter for MATLAB `exportgraphics`/`saveas` routes.
- Keep every adapter separately opt-in; installing base ReproFig neither installs language runtimes nor intercepts their save functions.
- Require adapters to provide exact plotted tables, declared statistics and semantic bindings rather than inferred labels.
- Send candidate outputs to the Stage 18 broker.
- Add contract tests using fixtures; skip language-runtime execution honestly when a runtime is unavailable.

## Out of scope

- Exhaustive support for every plotting library in each language is follow-on work.
- Browser-only untrusted JavaScript sandboxing is not implemented here.
- Adapters do not implement cryptography independently.
- An adapter without semantic bindings cannot obtain strong visual verification.

## Files touched

| path | change | reason |
|---|---|---|
| `adapters/contract/reprofig-adapter-v1.json` | NEW | Freeze the language-neutral request/response contract. |
| `adapters/r/reprofig_adapter.R` | NEW | Reference R save and broker route. |
| `adapters/julia/ReproFigAdapter.jl` | NEW | Reference Julia save and broker route. |
| `adapters/javascript/reprofig-adapter.mjs` | NEW | Reference server-side JavaScript route. |
| `adapters/matlab/reprofig_adapter.m` | NEW | Reference MATLAB route. |
| `tests/test_adapter_contract.py` | NEW | Validate fixtures and available runtime smoke tests. |
| `docs/language-adapters.md` | NEW | Document integration requirements and honest capability levels. |

## Implementation sketch

Adapter request:

```json
{
  "adapter_schema": "reprofig-adapter/1",
  "language": {"name": "R", "version": "..."},
  "candidate_path": "run/candidates/Figure1.svg",
  "record_path": "run/candidates/Figure1.record.json",
  "policy_path": "run/policy.json",
  "semantic_capabilities": ["points", "lines", "text", "statistics"]
}
```

Adapter response:

```json
{
  "ok": true,
  "candidate_sha256": "...",
  "record_sha256": "...",
  "broker_receipt": "run/receipts/Figure1.json",
  "achieved_grades": ["internally_consistent", "statistics_independently_verified"]
}
```

Each language helper may wrap its common save function, but the broker remains the hard boundary. The adapter must never report a grade itself; it returns the grades in the ReproFig verification report.

## Exit gate

1. The same contract fixture validates identically from every adapter implementation.
2. Each available language runtime can submit one figure to the broker and receive a deterministic response.
3. Missing runtimes produce explicit skips and do not mark the adapter verified.
4. Unknown contract fields remain forward-compatible; missing required identities fail.
5. No adapter contains signature, encryption or statistical reference algorithms.
6. Direct writes outside the candidate workspace are refused in hard broker mode.
7. `pytest tests/test_adapter_contract.py -q` passes, including every runtime installed in continuous integration.
8. Missing R, Julia, JavaScript or MATLAB runtimes do not affect base installation, imports or Python figure workflows.

## Known risks

- Save-function APIs and runtime packaging differ. Keep adapters thin and test the contract more strongly than convenience wrappers.
- Standard-output logging can corrupt the protocol. Reserve standard output for one deterministic response and send diagnostics to standard error.
- MATLAB licensing and graphical runtime availability may limit automated tests. Report that capability separately.
