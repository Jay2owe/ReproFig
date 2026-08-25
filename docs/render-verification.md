# Visual verification

Visual verification asks whether the saved carrier still shows the declared
scientific marks and annotations. It is separate from data/statistics checks.

`bind_artist` assigns a stable semantic identity and optional table rows,
columns or statistic identity to a Matplotlib artist. `save_figure(...,
proof=True)` captures axes scales and limits, mark geometry, annotation text,
positions and rendering environment before saving.

For SVG, ReproFig binds stable element IDs and hashes normalized vector
subtrees. Moving, deleting, restyling or relabelling a bound mark fails its
named check. Unsupported artist types are reported as `unsupported` rather
than silently ignored.

For PNG, JPEG, TIFF, WebP, AVIF and HEIF, ReproFig embeds a compressed canonical
RGBA reference. Whole-image comparison permits a documented small tolerance
for lossy carriers, but every declared scientific mark and annotation has an
exact pixel region. A localized one-channel mutation inside that region fails
even if its contribution to whole-image error is tiny.

For a single-page PDF, `pypdfium2` renders page 1 at 144 dots per inch and uses
the same regional check. Without the optional renderer, PDF display status is
honestly `unavailable`; data and signature checks still operate.

Visual references are carrier-specific and sit outside the shared scientific
evidence root. Signatures bind both the shared root and the current carrier's
visual-reference hash. SVG, PDF and raster variants can therefore share one
scientific identity while a signature still detects substitution of a visual
binding.

A passing visual check does not show that an unbound decorative element is
scientifically meaningful, that the underlying data are true, or that the
graph design is non-misleading. Bind every proof-relevant mark and annotation.
