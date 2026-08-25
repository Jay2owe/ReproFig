# Stage 17 — Intercept common Python plot-saving routes

## Why this stage exists

Agent instructions can be forgotten, and individual plotting libraries expose different save functions. This stage creates an explicitly activated language-level enforcement layer that routes common Python saves through ReproFig policy and rejects outputs that do not achieve the requested proof grade. Normal Python and ReproFig saving remain untouched outside that guard; Stage 18 supplies the filesystem boundary needed against deliberate bypass.

## Prerequisites

- Stages 03 and 10 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 03 and Stage 10 files
- `src/reprofig/artifacts.py:748-900`
- `src/reprofig/api.py:1-428`
- `src/reprofig/cli.py:1-214`
- `src/reprofig/render/matplotlib.py` in its completed form
- `tests/test_api_compat.py:1-73`
- `pyproject.toml:1-71`

## Scope

- Define a reusable Python figure-output policy: permitted carriers, profile, required grades, signing, encryption and destination.
- Add an explicit context manager for in-process enforcement.
- Keep hooks inert on import and outside the context manager or explicit guarded subprocess launcher.
- Add a subprocess launcher that installs hooks before user plotting code imports libraries.
- Intercept Matplotlib `Figure.savefig` and `pyplot.savefig`.
- Add optional hooks for Plotly image/web export and Altair save when those packages are installed.
- Route supported live figures through semantic capture and ReproFig save/verification.
- Restore patched functions reliably after the guarded context exits.
- Refuse unknown output extensions or grades under a strict policy.
- Produce a deterministic audit log without private data or keys.
- State clearly that direct byte/file writes can bypass this layer.

## Out of scope

- Hard filesystem enforcement belongs to Stage 18.
- Other languages belong to Stage 19.
- This stage does not monkeypatch every Python image-writing package.
- It does not infer missing data or statistical specifications from rendered pixels.
- It does not change `save_figure`, `save_svg` or plotting-library behavior for callers that did not activate a guard.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/guard/__init__.py` | NEW | Public Python guard namespace. |
| `src/reprofig/guard/policy.py` | NEW | Typed output and proof requirements. |
| `src/reprofig/guard/python.py` | NEW | Context manager, startup hooks and library interception. |
| `src/reprofig/api.py` | MODIFY | Export guarded-run and policy operations. |
| `src/reprofig/cli.py` | MODIFY | Add `guard python` launcher and policy input. |
| `tests/test_python_guard.py` | NEW | Test interception, restoration, bypass disclosure and failures. |
| `docs/agent-enforcement.md` | NEW | Document soft versus hard enforcement and supported libraries. |

## Implementation sketch

```python
@dataclass
class OutputPolicy:
    output_root: Path
    formats: tuple[str, ...]
    profile: str
    required_grades: set[VerificationGrade]
    required_signer_scopes: set[str] = field(default_factory=set)
    encrypted_sections: dict[str, Any] = field(default_factory=dict)
    strict: bool = True

@contextmanager
def enforce_python_plots(policy: OutputPolicy):
    patches = install_plot_hooks(policy)
    try:
        yield
    finally:
        restore_plot_hooks(patches)
```

Launcher shape:

```text
reprofig guard python analysis.py --policy proof-policy.json -- arg1 arg2
```

The hook workflow is:

```text
library save request
  -> resolve target under allowed temporary root
  -> capture live semantic evidence when supported
  -> save through ReproFig
  -> verify required policy
  -> return only after success
```

Plotly and Altair routes that do not expose Matplotlib artists must attach an adapter-supplied manifest or receive a lower grade. Do not pretend that file stamping creates semantic proof.

## Exit gate

1. Matplotlib object and pyplot save routes are intercepted before writing a final target.
2. Installed Plotly and Altair fixtures follow their declared supported routes; absent optional libraries do not break import.
3. Hooks restore original functions after success, exception and nested contexts.
4. A required-grade failure leaves no final output.
5. Paths outside the policy root and unknown extensions fail before writing.
6. A raw `open(..., "wb")` bypass is demonstrated and explicitly labelled as requiring Stage 18.
7. `pytest tests/test_python_guard.py tests/test_api_compat.py -q` passes.
8. Outside a guarded context, current save routes are byte-for-byte and exception-for-exception compatible with their pre-stage behavior.

## Known risks

- Monkeypatching private plotting internals is fragile. Patch documented public save entry points and maintain version fixtures.
- Libraries may cache functions before hooks install. The subprocess launcher must activate before user imports.
- Same-process code can deliberately undo patches. Never call this hard enforcement.
