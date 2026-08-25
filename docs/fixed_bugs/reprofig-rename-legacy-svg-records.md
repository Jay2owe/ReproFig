# ReproFig rename preserves legacy SVG records
**Date**: 2026-08-24
**Files changed**: `src/reprofig/schema.py`, `src/reprofig/svg.py`
**Guard**: `tests/test_roundtrip.py::test_reprofig_rename_keeps_development_era_svg_records_readable`

## What went wrong
Renaming the schema and Extensible Markup Language (XML) namespace to ReproFig
would have made SVG files written under the two development names unreadable.
Their compressed records still declare `figure-artifact/1` or `metafig/1` and
use the corresponding earlier namespace.

## The broken pattern

```python
if not schema.startswith("reprofig/"):
    raise ValueError("Unsupported figure record schema")  # rejected old records
```

## The fix

```python
if not schema.startswith(("reprofig/", "metafig/", "figure-artifact/")):
    raise ValueError("Unsupported figure record schema")
```

The SVG reader likewise accepts all three namespaces, while every newly embedded
record uses the ReproFig schema and namespace.

## Why it matters
Figures are intended to remain self-describing after they move between folders
and software versions. A package rename must not strand records already saved
inside existing figures.
