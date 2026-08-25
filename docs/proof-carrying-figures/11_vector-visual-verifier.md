# Stage 11 — Verify Scalable Vector Graphics geometry and annotations

## Why this stage exists

Semantic capture records what the producer intended to draw; a strong verifier must compare that intent with the carrier that was actually saved. Scalable Vector Graphics exposes geometry and text without optical character recognition, making it the first strong visual-verification carrier. This stage detects missing, moved, relabelled or wrongly connected scientific marks.

## Prerequisites

- Stages 09 and 10 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stage 09 and Stage 10 files
- `src/reprofig/svg.py:1-265`
- `src/reprofig/validation.py:130-233`
- `src/reprofig/render/schema.py` in its completed form
- `src/reprofig/render/matplotlib.py` in its completed form
- `tests/test_inkscape_roundtrip.py:1-54`
- `docs/carrier_survival.md:1-42`

## Scope

- Parse saved Scalable Vector Graphics with the existing safe XML route.
- Normalize harmless generated identities, metadata order, transform composition and declared floating-point precision.
- Locate semantic elements through stable identifiers emitted by Stage 10.
- Compare lines, points, bars, areas, intervals, brackets and text with the render manifest.
- Compare scientific coordinates independently from presentation coordinates.
- Confirm that displayed statistical text matches the referenced exact result and formatter.
- Confirm that comparison brackets connect the marks named in the statistical specification.
- Report missing, extra, moved, relabelled and rebound elements separately.
- Define the honest status for vector carriers without supported semantic element identifiers.
- Invoke vector verification only through an explicit verification request or proof policy; ordinary saving and extraction never require semantic identifiers.

## Out of scope

- Raster and rendered-page comparison belongs to Stage 12.
- Optical character recognition is not a substitute for stable element binding.
- Generic hand-authored Scalable Vector Graphics without a render manifest cannot receive strong display verification.
- Portable Document Format object-level verification is not claimed in this stage; it may receive rendered comparison in Stage 12.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/render/vector.py` | NEW | Common normalized vector geometry model. |
| `src/reprofig/render/svg_verify.py` | NEW | Scalable Vector Graphics extraction and manifest comparison. |
| `src/reprofig/svg.py` | MODIFY | Preserve/expose stable semantic element identities. |
| `src/reprofig/verification.py` | MODIFY | Add display and annotation verification checks. |
| `tests/test_svg_visual_verification.py` | NEW | Test correct, moved, missing and relabelled marks. |
| `docs/render-verification.md` | MODIFY | Document normalization, supported geometry and limits. |

## Implementation sketch

```python
@dataclass
class ObservedVectorMark:
    element_id: str
    kind: str
    data_geometry: dict[str, Any] | None
    figure_geometry: dict[str, Any]
    text: str | None = None

def observe_svg(path: Path) -> list[ObservedVectorMark]: ...
def verify_svg_render(path: Path, manifest: RenderManifest) -> list[VerificationCheck]: ...
```

Normalize only presentation facts declared irrelevant by the manifest. Do not round a moved point back into place. The comparison order is:

```text
identity present
kind matches
scientific/data geometry matches
normalized presentation geometry matches within declared tolerance
visible text matches exactly
statistic and group bindings match
```

For a statistical annotation, independently regenerate the expected string from the verified exact result, then compare it with both the manifest and observed text.

## Exit gate

1. An untouched semantic Scalable Vector Graphics figure achieves display verification.
2. Moving a point, changing a bar height, altering an interval or deleting a bracket fails the corresponding mark check.
3. Replacing `p = 0.0125` with a different string fails even when the embedded statistic is unchanged.
4. Moving a correct bracket to the wrong groups fails its group-binding check.
5. Harmless generated element identifiers, metadata order and equivalent transforms do not cause false failures.
6. An ordinary untagged vector figure reports unsupported strong verification rather than passing through image similarity.
7. `pytest tests/test_svg_visual_verification.py tests/test_inkscape_roundtrip.py -q` passes.
8. Untagged figures continue to save, open and extract normally when no display-verification grade is requested.

## Known risks

- Renderer updates can change path decomposition without changing appearance. Prefer semantic element attributes and normalized high-level geometry over raw path-byte equality.
- Inkscape may rewrite transforms or group structure. Test equivalent transformations and report truly unrecognized rewrites honestly.
- Text-to-path conversion destroys textual evidence. Such output can use Stage 12 rendering comparison but cannot receive strong text-semantic verification.
