# Stage 12 — Verify raster figures and rendered pages against a canonical reference

## Why this stage exists

Portable Network Graphics, Joint Photographic Experts Group images and rendered document pages do not expose semantic vector objects reliably. They still need a defensible visual check, especially after journal conversion or upload recompression. This stage rerenders the proof record and compares pixels and declared evidence regions with format-aware tolerances.

## Prerequisites

- Stages 09, 10 and 11 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- completed Stages 09–11
- `src/reprofig/artifacts.py:748-900`
- `src/reprofig/carriers/registry.py:1-149`
- `src/reprofig/carriers/manifest.py:1-191`
- `tests/test_multiformat.py:36-168`
- `docs/carrier_survival.md:1-42`
- `docs/render-verification.md` in its completed form

## Scope

- Rerender a canonical reference from the verified data, statistics, render manifest and declared environment.
- Decode raster carriers without changing the original.
- Normalize colour mode, orientation and canvas dimensions under explicit rules.
- Compare exact pixels for lossless deterministic routes when eligible.
- Compare lossy carriers through documented absolute, root-mean-square and region-specific thresholds.
- Use semantic annotation regions to give stronger checks to points, bars, intervals, brackets and text areas.
- Support rendered-page comparison for Portable Document Format and Office containers where a deterministic renderer is available.
- Record renderer identity, font availability and all tolerance values.
- Load raster/page renderers only for an explicit visual-verification request; do not initialize them during ordinary carrier inspection.
- Distinguish “visually equivalent within tolerance” from vector-semantic verification.

## Out of scope

- Optical character recognition alone cannot prove statistical text.
- The stage does not promise deterministic page rendering across missing fonts or unsupported engines.
- Carrier metadata survival remains existing 0.2 behavior; this stage compares visible content.
- Perceptual matching is not allowed to conceal a scientifically meaningful changed mark.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/render/canonical.py` | NEW | Deterministic rerender orchestration and environment reporting. |
| `src/reprofig/render/raster_verify.py` | NEW | Pixel, region and tolerance comparisons. |
| `src/reprofig/verification.py` | MODIFY | Report raster/page visual checks and achieved grade. |
| `src/reprofig/artifacts.py` | MODIFY | Route eligible carriers to the visual verifier. |
| `tests/test_raster_visual_verification.py` | NEW | Cover lossless, lossy, changed-mark and missing-font cases. |
| `pyproject.toml` | MODIFY | Add visual-verification dependencies beneath the aggregate `[proof]` extra. |
| `docs/render-verification.md` | MODIFY | Publish comparison metrics, tolerances and grade differences. |

## Implementation sketch

```python
@dataclass
class RasterComparisonPolicy:
    exact_pixels: bool
    max_absolute_difference: float
    root_mean_square_limit: float
    changed_pixel_fraction_limit: float
    evidence_region_overrides: dict[str, dict[str, float]]

def render_reference(record: FigureRecord, *, environment: RenderEnvironment) -> RasterImage: ...
def compare_raster(actual: RasterImage, expected: RasterImage, policy: RasterComparisonPolicy) -> list[VerificationCheck]: ...
```

The manifest supplies normalized evidence regions. A global lossy-image tolerance must not excuse a moved point or changed label inside a small evidence region. Report both global and per-mark comparisons.

```text
canvas geometry                 pass
global visual difference       pass within JPEG policy
mark point-series-1 region      pass
bar treated region             fail: height mismatch
comparison-01 label region     pass visually; semantic text unavailable in raster
```

Strong text verification remains available only when the carrier retains the semantic text route from Stage 11 or when the raster is tied to a canonical render whose signed manifest contains the expected text. Do not promote optical character recognition output to an exact semantic pass.

## Exit gate

1. Deterministic lossless output passes exact comparison when produced in the recorded environment.
2. A normal Joint Photographic Experts Group recompression passes only its declared lossy policy.
3. Moving one scientific mark fails its evidence region even when global image difference remains small.
4. Missing fonts or unavailable renderers produce `unavailable`, not a false mismatch or pass.
5. Every comparison report records decoder, renderer, dimensions, colour normalization and thresholds.
6. Portable Document Format page rendering, when available, is labelled raster/page verification rather than vector-semantic verification.
7. `pytest tests/test_raster_visual_verification.py tests/test_multiformat.py -q` passes.
8. A base-only installation retains normal raster save, inspect and extraction behavior without a renderer.

## Known risks

- Permissive perceptual thresholds can hide small but important scientific changes. Evidence regions need stricter policies than decorative areas.
- Fonts and antialiasing vary across systems. A recorded container/environment may be needed for exact rerendering.
- Page renderers can execute unsafe content in hostile documents. Use a sandboxed, non-networked renderer with resource limits.
