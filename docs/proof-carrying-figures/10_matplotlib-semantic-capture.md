# Stage 10 — Capture semantic evidence from Matplotlib figures

## Why this stage exists

The render manifest is useful only if plotting packages can populate it without reconstructing the figure after saving. Matplotlib is the first capture target because PyFLASH, PyMicroglia and many Python plotting libraries build on it. This stage records what the live artists mean before the carrier is written.

## Prerequisites

- Stage 09 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 09 file
- `src/reprofig/api.py:1-428`
- `src/reprofig/artifacts.py:748-900`
- `src/reprofig/schema.py:1-353` plus completed additions
- `tests/test_api_compat.py:1-73`
- `pyproject.toml:1-71`
- `docs/render-verification.md` in its completed form

## Scope

- Add a Matplotlib adapter that walks live figures and axes before save.
- Capture stable identities and geometry for lines, scatter collections, bars, filled areas, intervals, brackets and text.
- Preserve explicit artist identifiers when producers set them.
- Add helpers that bind artists to table rows, columns, statistical results and roles.
- Capture axes transforms, scales, limits and physical figure geometry after layout has settled.
- Attach the completed render manifest to the same master record used for every output carrier.
- Mark unsupported artist classes explicitly rather than dropping them silently.
- Keep ordinary `save_figure` calls compatible when no semantic bindings are supplied.

## Out of scope

- Inferring a t-test from annotation text is forbidden.
- Vector and raster comparison belongs to Stages 11 and 12.
- Plotly and Altair adapters are handled through downstream integration work after this contract is stable.
- Save interception belongs to Stage 17.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/render/matplotlib.py` | NEW | Artist capture and explicit binding helpers. |
| `src/reprofig/render/__init__.py` | MODIFY | Export the Matplotlib adapter lazily. |
| `src/reprofig/api.py` | MODIFY | Add public capture/binding entry points. |
| `src/reprofig/artifacts.py` | MODIFY | Capture after layout and before rendering all carriers. |
| `src/reprofig/schema.py` | MODIFY | Store producer/render implementation facts if needed. |
| `tests/test_matplotlib_capture.py` | NEW | Test artist types, geometry and unsupported reporting. |
| `pyproject.toml` | MODIFY | Extend the existing Matplotlib optional extra if required. |

## Implementation sketch

```python
def bind_artist(
    artist: Any,
    *,
    mark_id: str,
    table_id: str | None = None,
    row_ids: Sequence[str] = (),
    columns: Mapping[str, str] | None = None,
    statistic_id: str | None = None,
    role: str = "evidence",
) -> Any: ...

def bind_annotation(
    artist: Any,
    *,
    annotation_id: str,
    statistic_id: str,
    formatter: str,
) -> Any: ...

def capture_matplotlib(figure: Any) -> RenderManifest: ...
```

Capture routes should cover at least:

```text
Line2D -> ordered line/marker geometry
PathCollection -> point collection with row order
Rectangle containers -> bars
PolyCollection -> filled interval/area
errorbar containers -> center, lower and upper geometry
Text -> label/annotation text and anchor
Patch/Line2D combinations explicitly tagged as brackets -> comparisons
```

Use Matplotlib transforms to record both data coordinates and normalized figure coordinates after a canvas draw. Do not use generated memory addresses or backend-specific object representations as identities.

## Exit gate

1. A line, scatter, bar-plus-points, interval and statistical bracket fixture each produce deterministic semantic records.
2. Every bound point retains its table row identity after capture.
3. The same figure saved to multiple carriers receives one identical render-manifest hash.
4. Layout changes update presentation geometry without changing data/statistical bindings.
5. Unsupported evidence-role artists prevent strong display verification and identify their class.
6. Unbound ordinary figures still save through the existing ReproFig 0.2 path.
7. `pytest tests/test_matplotlib_capture.py tests/test_api_compat.py -q` passes.

## Known risks

- Matplotlib artist structures differ across versions. Capture public properties where possible and test the supported version range.
- Calling a draw can mutate layout. Capture once after the established save geometry has been applied.
- A producer may bind rows in the wrong order. Later visual verification can prove consistency, not producer intent; integration tests must check adapters carefully.
