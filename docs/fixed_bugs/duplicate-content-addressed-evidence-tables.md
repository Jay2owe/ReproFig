# Duplicate content-addressed evidence tables
**Date**: 2026-08-26
**Files changed**: `src/reprofig/evidence.py`, `tests/test_proof_core.py`
**Guard**: `tests/test_proof_core.py::test_evidence_graph_deduplicates_identical_content_addressed_tables`

## What went wrong
When two named tables contained identical canonical comma-separated values,
both received the same content-addressed section identifier. The evidence
builder inserted both sections, so the graph rejected an otherwise valid
figure because section identities were duplicated.

## The broken pattern
```python
for index, table in enumerate(record.data_tables):
    section = EvidenceSection(section_id=f"table:{table.sha256}", ...)
    sections.append(section)  # repeated the same identity for identical bytes
```

## The fix
```python
table_id = f"table:{table.sha256}"
if table_id in table_ids:
    continue
```

One canonical table digest now creates one evidence node even when several
record-level names refer to those same bytes.

## Why it matters
Plotting integrations can legitimately attach the same data under producer and
analysis names. Reintroducing duplicate evidence nodes would make proof capture
fail for those figures despite their data being internally consistent.
