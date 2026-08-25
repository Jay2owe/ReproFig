# Stage 09 — Define the semantic render manifest

## Why this stage exists

A correct statistical result can still be drawn over the wrong groups, rounded incorrectly or paired with the wrong error bar. Image comparison alone cannot explain what each object means. This stage defines the machine-readable bridge from visible marks and annotations to data rows, estimates, intervals and statistical result identities.

## Prerequisites

- Stages 01, 02 and 03 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 01, Stage 02 and Stage 03 files
- `src/reprofig/schema.py:1-353` plus completed proof schema additions
- `src/reprofig/evidence.py` in its completed Stage 02 form
- `src/reprofig/verification.py` in its completed Stage 03 form
- `src/reprofig/api.py:1-428`
- `tests/test_api_compat.py:21-45`

## Scope

- Define stable semantic identities for axes, marks, collections and annotations.
- Support points, lines, bars, areas, intervals/error bars, comparison brackets and text.
- Record data-table, row, column and statistical-result bindings.
- Define figure, axes, data and display coordinate systems explicitly.
- Store intended geometry at a precision sufficient for normalized comparison.
- Store visible text and the formatter identity that generated statistical text.
- Represent derived graphical values such as means and confidence intervals without duplicating scientific calculations.
- Require every proof-relevant annotation to identify the result it displays.
- Permit unbound decorative elements while keeping them distinguishable from evidence marks.

## Out of scope

- Extracting objects from Matplotlib belongs to Stage 10.
- Comparing vector and raster output belongs to Stages 11 and 12.
- Optical character recognition cannot create strong semantic bindings.
- The manifest does not decide statistical correctness; it points to Stage 05–08 results.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/render/__init__.py` | NEW | Public render-semantics namespace. |
| `src/reprofig/render/schema.py` | NEW | Typed axes, mark, annotation and coordinate records. |
| `src/reprofig/schema.py` | MODIFY | Bind a render manifest into the proof-carrying record. |
| `src/reprofig/evidence.py` | MODIFY | Hash render semantics and their data/statistical dependencies. |
| `src/reprofig/validation.py` | MODIFY | Detect missing, duplicate and dangling render bindings. |
| `tests/test_render_manifest.py` | NEW | Freeze semantic identities, coordinates and references. |
| `docs/render-verification.md` | NEW | Document supported marks, bindings and coordinate meanings. |

## Implementation sketch

```python
@dataclass
class AxesSpec:
    axes_id: str
    bounds_figure_fraction: tuple[float, float, float, float]
    x_scale: dict[str, Any]
    y_scale: dict[str, Any]

@dataclass
class MarkSpec:
    mark_id: str
    kind: str
    axes_id: str
    geometry: dict[str, Any]
    table_id: str | None = None
    row_ids: list[str] = field(default_factory=list)
    column_bindings: dict[str, str] = field(default_factory=dict)
    statistic_id: str | None = None
    role: str = "evidence"

@dataclass
class AnnotationSpec:
    annotation_id: str
    kind: str
    axes_id: str
    text: str
    geometry: dict[str, Any]
    statistic_id: str | None = None
    formatter: str | None = None
```

Example relationships:

```text
point-series-1 -> plotted-table rows participant-01..participant-12
bar-control -> statistic control-mean field estimate
bar-control-error -> statistic control-mean field confidence_interval
comparison-bracket-1 -> comparison-01 and group marks control/treated
comparison-label-1 -> comparison-01 field p_adjusted
```

Use normalized figure coordinates for cross-size layout checks and retain data coordinates for scientific position checks. Store coordinate-system identity with every geometry field; never assume a bare number is a pixel or data value.

## Exit gate

1. A fixture can bind individual points to source row identities and a bar to a computed estimate.
2. Error-bar records identify interval type and the statistic fields used for lower and upper limits.
3. A comparison bracket identifies both compared group marks and one statistical result.
4. Duplicate mark identities, unknown axes, missing rows and unknown statistic references fail validation.
5. Decorative marks remain permitted but cannot satisfy evidence-mark requirements.
6. Canonical manifest serialization is deterministic and changes the evidence root when meaning changes.
7. `pytest tests/test_render_manifest.py tests/test_evidence_graph.py -q` passes.

## Known risks

- Geometry without coordinate systems is ambiguous. Make coordinate identity required.
- Automatically inferred meanings can be wrong. Allow capture helpers, but require explicit binding for proof-relevant statistics.
- Overly detailed geometry can vary across harmless renderer versions. Separate scientific geometry from presentation details needed only for visual comparison.
