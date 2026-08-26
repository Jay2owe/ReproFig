# Code-figure registration survives a Dropbox file lock

**Date**: 2026-08-26
**Files changed**: `examples/diverse-verification-workflows/code/build_examples.py`, `tests/test_diverse_examples.py`
**Guard**: `test_code_figure_registration_retries_a_transient_dropbox_lock`

## What went wrong

Rebuilding the diverse examples stopped while registering the second code figure. Dropbox briefly held the SVG while ReproFig attempted its atomic replacement, causing Windows to report that access was denied. The main plot registration already retried this transient condition, but the new code-figure registration did not.

## The broken pattern

```python
result = subprocess.run(command, text=True, capture_output=True)
if result.returncode != 0:
    raise RuntimeError(...)  # A temporary file lock aborted the whole rebuild.
```

## The fix

Code-figure registration now retries bounded `PermissionError` and `Access is denied` failures, using the same twelve-attempt policy as main figure registration. Other failures still stop immediately with their complete output.

The temporary record used only to seed a permanent figure identity is also marked with incomplete data. This prevents plot-that from treating it as authoritative; registration replaces it with the complete per-line table and current bundle hashes while retaining the seeded identity.

## Why it matters

Dropbox synchronization can briefly lock a newly written carrier on Windows. Without the retry, a valid multi-example rebuild can fail nondeterministically after partially updating its output folders.
