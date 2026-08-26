# Unhashable Plotly figure save
**Date**: 2026-08-26
**Files changed**: `src/reprofig/api.py`, `tests/test_api_compat.py`
**Guard**: `test_save_figure_does_not_require_a_hashable_plotly_style_figure`

## What went wrong
Saving a Plotly figure through the high-level `save_figure` interface crashed
before rendering. Plotly figure objects are unhashable, but ReproFig always
looked for optional attached metadata in a weak-key dictionary that requires a
hashable key.

## The broken pattern
```python
attached = _ATTACHMENTS.get(figure, {})  # TypeError for a Plotly Figure
```

## The fix
```python
try:
    attached = _ATTACHMENTS.get(figure, {})
except TypeError:
    attached = {}
```

Unhashable figures now skip the optional attachment cache and use the metadata
passed directly to `save_figure`.

## Why it matters
Reintroducing the assumption would break the one-call workflow for Plotly and
any other plotting object that deliberately disables hashing.
