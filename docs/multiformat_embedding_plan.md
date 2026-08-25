# ReproFig multi-format embedding plan

Status: planned  
Created: 2026-08-24  
Target: ReproFig 0.2 and later

## Outcome

Extend ReproFig from a Scalable Vector Graphics (SVG) carrier into a
format-neutral figure provenance system. The same `reprofig/1` scientific
record must be embeddable, extractable, privacy-transformable, and verifiable
in:

- SVG
- Portable Document Format (PDF)
- Portable Network Graphics (PNG)
- Tagged Image File Format (TIFF)
- Joint Photographic Experts Group images (JPEG)
- WebP
- AV1 Image File Format and High Efficiency Image File Format (AVIF/HEIF)
- PowerPoint, Word, and Excel Open XML files (`.pptx`, `.docx`, `.xlsx`)
- Hypertext Markup Language (HTML)
- Hierarchical Data Format version 5 (HDF5)
- Network Common Data Form version 4 (netCDF-4)
- Flexible Image Transport System (FITS)
- deterministic ZIP bundles and Research Object Crate (RO-Crate) packages

Every carrier must preserve the same figure identity, exact comma-separated
values (CSV), structured statistics, producer information, source hashes,
reproduction instructions, and `master`, `public`, or `minimal_public`
distribution profile.

## Decisions fixed before implementation

1. **One scientific schema.** Do not create a PDF schema, PNG schema, or Office
   schema. All formats carry `reprofig/1`; format-specific details live in a
   small carrier manifest.
2. **One or many records per carrier.** A raster image normally contains one
   figure. A PDF, Office document, HTML page, scientific container, or bundle
   may contain several. The carrier manifest indexes records by stable
   `figure_id` and identifies the page, slide, shape, sheet, frame, or HTML
   element to which each record belongs.
3. **Exact bytes remain canonical.** Native table views may be added for HDF5,
   netCDF-4, or FITS, but the canonical record still contains the exact UTF-8
   CSV bytes and their SHA-256 hashes.
4. **No silent downgrade.** If the requested format adapter is unavailable,
   exceeds its configured safety limit, or cannot preserve the file safely,
   ReproFig fails without writing a partial carrier.
5. **Profiles behave identically everywhere.** `master -> public ->
   minimal_public` stays one-way. Public allowlists, path scrubbing, safe source
   links, and companion CSV behavior cannot vary by format.
6. **Embedding does not imply encryption.** A master in any format is private
   data. Validation and documentation must make this visible.
7. **Copying is distinct from re-rendering.** Byte-for-byte sending preserves
   a record. Editing, optimizing, converting, or uploading may strip it. Every
   adapter ships with measured survival results rather than a generic promise.
8. **Visual content must not change merely to add metadata.** Where the format
   permits it, embedding rewrites only container structures. Tests compare
   decoded pixels, JPEG scan data, PDF page renders, or Office document content
   before and after embedding.
9. **Scripts are inert data.** Extraction may restore a producer script, but
   inspection, validation, and extraction never execute it.
10. **Existing SVG users do not migrate.** `save_svg`, `read_svg`,
    `validate_svg`, `publish_figures`, and current command-line calls remain
    compatible.

## Carrier privacy boundary

A public ReproFig record does not automatically make the rest of its carrier
public-safe. PDF files can contain unrelated attachments or actions; raster
images can contain location and device metadata; Office documents can contain
comments, speaker notes, hidden slides or sheets, tracked changes, external
links, and document properties; HTML can contain unrelated scripts and links.

Therefore:

- master embedding preserves unrelated carrier metadata;
- public publishing audits both the ReproFig record and known carrier privacy
  surfaces;
- `strict=True` fails if carrier material may leak private information;
- optional `sanitize_carrier=True` removes only well-defined metadata classes
  and records every removal in the validation report;
- unknown attachments, custom parts, active content, and hidden Office content
  are reported rather than silently deleted; and
- a result is labelled `record_public` rather than `carrier_public` until the
  whole-carrier audit passes.

## Common carrier representation

### Canonical record bytes

All adapters use the same deterministic pipeline:

```text
FigureRecord
  -> deterministic UTF-8 JSON
  -> SHA-256 payload hash
  -> carrier-appropriate compression or text escaping
  -> native metadata, attachment, package part, dataset, or archive entry
```

Binary attachment formats store `record.json` directly when their container
already compresses it. Metadata-only formats may use deterministic gzip
(`mtime=0`) followed by Base64 when their native field requires XML-safe or
text-safe data.

### Carrier manifest

Introduce `reprofig-carrier/1`, which describes transport without duplicating
scientific meaning:

```json
{
  "carrier_schema": "reprofig-carrier/1",
  "created_by": {"package": "reprofig", "version": "0.2.0"},
  "records": [
    {
      "figure_id": "fig-...",
      "record_path": "reprofig/fig-.../record.json",
      "record_sha256": "...",
      "profile": "master",
      "target": {"kind": "slide-shape", "slide": 2, "shape_id": 17}
    }
  ]
}
```

Single-record metadata carriers may store the record inline and retain the
same manifest fields as a small locator. Multi-record carriers store a manifest
plus one record namespace per figure.

### Format capabilities

Each adapter reports a `CarrierCapabilities` object:

- supported suffixes and media types
- single-record or multi-record support
- inline payload, attachment, or native-dataset storage
- whether embedding preserves encoded image/page bytes
- practical size class: `metadata`, `attachment`, or `scientific_container`
- supported profiles
- available optional dependency
- known editor and upload survival results

`reprofig formats` prints this information without importing every optional
dependency.

## Per-format design

| Carrier | ReproFig storage | Preferred implementation | Main survival risk |
|---|---|---|---|
| SVG | Existing gzip/Base64 XML metadata payload | Standard library XML | SVG optimizers or editors that delete unknown metadata |
| PDF | XMP summary plus associated `record.json`, CSV, statistics, and producer attachments | `pikepdf` optional extra | Publisher optimization, print-to-PDF, or flattening |
| PNG | Compressed `iTXt` entry with keyword `ReproFig`; insert before `IEND` without changing image chunks | Dependency-free chunk parser | Image export and web re-encoding |
| TIFF | XMP in standard TIFF tag 700, containing a payload locator and Base64 record; BigTIFF when required | Evaluate `tifffile` and `tifftools` in a spike | Editors rewriting or omitting unknown metadata tags |
| JPEG | Primary XMP locator plus Extended XMP application segments for the full record; insert without recompressing scan data | Dependency-free segment parser, with Pillow for decoded-pixel tests | Metadata stripping is common; ordinary XMP segments are small |
| WebP | Standard RIFF `XMP ` chunk with the carrier manifest and record | Dependency-free RIFF parser or Pillow adapter | Encoders may rebuild the RIFF file without XMP |
| AVIF/HEIF | XMP metadata item associated with the primary image | `pillow-heif` optional extra | Tool support and metadata preservation vary; avoid pixel re-encoding where possible |
| PowerPoint/Word/Excel | Open Packaging Conventions parts under `/reprofig/`, registered content types, and explicit relationships | Standard library ZIP/XML first | Office Document Inspector, alternative editors, and save-as operations |
| HTML | Non-executable `<script type="application/vnd.reprofig+json">` data blocks plus a document manifest | Standard library HTML-safe serializer/parser | Content management systems often sanitize unknown script blocks |
| HDF5 | `/reprofig/<figure_id>/record_json` byte dataset plus attributes and optional native table views | `h5py` optional extra | Downstream programs copying selected datasets only |
| netCDF-4 | `/reprofig/<figure_id>` group with a byte/string record variable and summary attributes | `netCDF4` optional extra | Classic netCDF formats do not support groups |
| FITS | `REPROFIG` binary table Header/Data Unit with one byte-array row per record and summary header keywords | `astropy` optional extra | Programs that copy only the primary Header/Data Unit |
| ZIP/RO-Crate | Explicit files, hashes, manifest, figure carriers, data, statistics, sources, and producer | Standard library ZIP plus current RO-Crate exporter | Unsafe extraction or incomplete manual copying |

### PDF details

- Add a document-level XMP summary containing schema, figure identifiers,
  profiles, producer versions, and carrier-manifest hash.
- Store each figure under `reprofig/<figure_id>/` as associated files:
  `record.json`, exact data CSV files, `statistics.csv`, and producer text when
  present.
- Mark attachments with appropriate association relationships and media types;
  do not add executable actions or JavaScript.
- Preserve existing pages, fonts, annotations, bookmarks, accessibility tags,
  and pre-existing attachments.
- Reject encrypted PDFs unless an explicit password-capable API is later
  designed; never prompt for or log a password in the core API.

### PNG details

- Parse and validate the PNG signature, chunk lengths, ordering, and cyclic
  redundancy checks.
- Remove only older ReproFig `iTXt` entries before inserting the replacement.
- Store UTF-8 JSON using the standard `iTXt` compression flag rather than a
  private critical chunk.
- Preserve every non-ReproFig chunk byte-for-byte.
- Enforce decompression and declared-length limits before allocating memory.

### JPEG details

- Parse marker segments up to Start of Scan, preserving entropy-coded scan
  bytes exactly.
- Use Adobe XMP primary and Extended XMP conventions. The primary packet holds
  the locator and extended-packet identifier; ordered extended segments hold
  the full payload with total length and offset fields.
- Preserve Exchangeable Image File Format (Exif), International Color
  Consortium profiles, comments, thumbnails, and unrelated application
  segments.
- Test records below and above the ordinary application-segment size limit.
- Report `metadata_survival="fragile"` even when ReproFig validation passes.

### TIFF details

- Use standard XMP tag 700 rather than inventing a private TIFF tag.
- Preserve byte order, image directories, pages, tiles, strips, compression,
  and BigTIFF status.
- Select the implementation library only after proving that adding tag 700
  leaves decoded pixels and all non-ReproFig tag values unchanged.
- One record applies to the carrier by default; multi-page targeting uses the
  carrier manifest rather than duplicating payloads in every image directory.

### WebP and AVIF/HEIF details

- Use their standard XMP metadata locations; do not misuse comments or Exif
  user fields.
- Preserve animation, frame timing, alpha, color profiles, orientation, and
  primary-image selection.
- If the available AVIF/HEIF library can only preserve metadata by recompressing
  pixels, require an explicit `allow_reencode=True` and record that transform.
  Metadata-only embedding remains the default contract.

### Office details

- Support `.pptx`, `.docx`, and `.xlsx`; never modify macro-enabled packages in
  the first release.
- Add `/reprofig/manifest.json` and `/reprofig/<figure_id>/record.json` as
  package parts with registered content types.
- Add package or document relationships so parts are reachable according to
  Open Packaging Conventions rather than relying on hidden ZIP members.
- PowerPoint targets use slide relationships and stable shape identifiers.
- Word targets use drawing relationships, bookmarks, or document-level scope.
- Excel targets use sheet name plus drawing relationship and shape identifier.
- Preserve unknown existing parts, digital-signature state warnings, and ZIP
  compression choices. Any modification invalidating an existing Office
  signature must fail unless explicitly approved.

### HTML details

- Use a non-JavaScript media type so browsers treat the element as a data block.
- Escape `<` as `\u003c` inside JSON so embedded producer text cannot terminate
  the script element with `</script>`.
- Use element IDs or stable selectors only as hints; record the figure's own
  stable identifier in the figure element and manifest.
- Provide a browser-independent extractor based on HTML parsing, not regular
  expressions.
- State clearly that sanitized content-management-system HTML should instead
  link to or download a ReproFig ZIP/RO-Crate.

### Scientific-container details

- HDF5 stores a dedicated group with exact record bytes in a dataset; small
  searchable summary values may also be attributes.
- netCDF support targets netCDF-4/HDF5 only. Do not silently rewrite classic
  netCDF-3 files into netCDF-4.
- FITS uses an extension Header/Data Unit named `REPROFIG`; do not overload
  structural header keywords or split long JSON across arbitrary cards.
- Native table mirrors are optional conveniences. Validation compares any
  native mirror with the canonical CSV hash and reports divergence.

### ZIP and RO-Crate details

Use this deterministic layout:

```text
reprofig-bundle/
  manifest.json
  checksums.sha256
  ro-crate-metadata.json
  figures/
    <figure files>
  records/
    <figure-id>/record.json
  data/
    <figure-id>/*.csv
  statistics/
    <figure-id>.csv
  code/
    <producer files>
  sources/
    <approved copied sources>
```

- Sort members and use fixed ZIP timestamps for reproducible builds.
- Store SHA-256 hashes for every member other than the checksum file itself.
- Reject absolute paths, parent traversal, drive-qualified paths, links, device
  files, duplicate normalized paths, and decompression bombs on extraction.
- Expand the existing RO-Crate exporter to describe every included file,
  profile, hash, figure relationship, producer, and public source.
- A bundle may contain private masters and public derivatives, but the root
  manifest must label each profile unambiguously.

## Public Python API

Add preferred format-neutral APIs while retaining current SVG entry points:

```python
from reprofig import (
    embed_file,
    extract_artifact,
    extract_records,
    formats,
    publish_artifacts,
    save_figure,
    validate_artifact,
)

save_figure(
    figure,
    "Figure 1.pdf",
    plotted_data=data,
    statistics=statistics,
    figure_profile="master",
)

publish_artifacts(
    ["Figure 1.pdf", "Figure 2.jpg", "Slides.pptx"],
    output_dir="Submission",
    figure_profile="minimal_public",
)
```

Behavior:

- `save_figure` renders Matplotlib-compatible formats and then embeds the final
  record atomically.
- `embed_file` adds one or more existing `FigureRecord` objects to an existing
  carrier without changing its visual content.
- `extract_records` always returns a list.
- Existing `extract_record` returns the sole record, accepts `figure_id=`, and
  raises a clear ambiguity error when a carrier holds several records.
- `extract_artifact` regenerates records, CSV files, statistics, captions, and
  producer text for one or all figure identifiers.
- `validate_artifact` dispatches by detected format and applies common record,
  privacy, integrity, and carrier checks.
- `publish_artifacts` is the format-neutral implementation;
  `publish_figures` remains a compatible wrapper.
- `formats` reports installed and unavailable adapters without importing heavy
  scientific packages.

## Command-line interface

Generalize existing commands and add only the missing operations:

```text
reprofig formats
reprofig inspect <artifact> [--figure-id ID]
reprofig validate <artifact> [--figure-id ID] [--public-safety]
reprofig embed <artifact> --record record.json
reprofig extract <artifact> --output DIR [--figure-id ID]
reprofig publish <artifacts...> --output-dir DIR --profile public|minimal-public
reprofig scan <path> --csv catalogue.csv
reprofig bundle <artifacts...> --output result.reprofig.zip [--ro-crate]
```

All commands must use atomic writes, retain the original file until validation
passes, and produce machine-readable errors when `--json` is requested.

## Package layout

```text
src/reprofig/
  carriers/
    __init__.py
    base.py
    manifest.py
    payload.py
    registry.py
    svg.py
    pdf.py
    png.py
    jpeg.py
    tiff.py
    webp.py
    heif.py
    office.py
    html.py
    hdf5.py
    netcdf.py
    fits.py
    bundle.py
  api.py
  publication.py
  validation.py
```

The existing `svg.py` remains as a compatibility facade or is moved behind one
with imports preserved. Optional dependencies are isolated inside adapters.

Suggested extras:

```toml
pdf = ["pikepdf"]
raster = ["Pillow", "tifffile"]
heif = ["pillow-heif"]
office = []
hdf5 = ["h5py"]
netcdf = ["netCDF4"]
fits = ["astropy"]
all-formats = ["pikepdf", "Pillow", "tifffile", "pillow-heif", "h5py", "netCDF4", "astropy"]
```

Pin minimum versions only after adapter tests identify the first version that
actually supports the required metadata behavior.

## Implementation stages

### Stage 0: freeze the SVG baseline

Changes:

- Record the current public API, command-line behavior, 22 package tests, and
  SVG fixtures as compatibility baselines.
- Add golden `master`, `public`, and `minimal_public` records used by every
  adapter test.
- Add a reusable assertion that extraction produces byte-identical record JSON,
  table CSV files, statistics CSV, and producer text.

Exit gate:

- All existing tests pass unchanged.
- The cross-format fixture and byte-equivalence assertion are stable.

### Stage 1: carrier core and dispatch

Changes:

- Implement `CarrierAdapter`, `CarrierCapabilities`, registry, payload codec,
  multi-record manifest, size guards, and atomic replacement helper.
- Add format detection by magic bytes first and suffix second.
- Add generic APIs and make SVG the first registered adapter.
- Keep all current SVG functions as compatible wrappers.

Exit gate:

- Old SVG calls and new generic calls produce equivalent SVG records.
- Unknown, mismatched, truncated, and unsupported carriers fail without writes.
- A mock multi-record adapter proves selection and ambiguity behavior.

### Stage 2: PDF

Changes:

- Implement XMP summary, associated attachments, multi-page targeting, and
  extraction with `pikepdf`.
- Add PDF optional dependency and capability reporting.
- Add `save_figure(...pdf)` and publication-profile conversion.

Exit gate:

- Single-record and multi-record PDF fixtures round-trip byte-identically.
- Page count, page render hashes, existing attachments, bookmarks, and document
  metadata remain intact.
- Encrypted, signed, malformed, and linearized PDF behavior is explicit and
  tested.

### Stage 3: PNG

Changes:

- Implement dependency-free chunk parsing, compressed `iTXt`, replacement,
  cyclic-redundancy validation, and size guards.
- Add pixel and chunk-preservation tests.

Exit gate:

- PNG pixels and all unrelated chunks are unchanged.
- Corrupt lengths, checksums, ordering, duplicate ReproFig chunks, and oversized
  decompression are handled safely.

### Stage 4: JPEG, TIFF, WebP, and AVIF/HEIF

Changes:

- Implement JPEG primary and Extended XMP segments without recompression.
- Select and implement TIFF tag-700 tooling after the preservation spike.
- Implement WebP XMP RIFF chunks and feature-flag updates.
- Implement AVIF/HEIF XMP metadata through `pillow-heif`, with an explicit
  re-encoding boundary.

Exit gate:

- Decoded pixel hashes match for all metadata-only operations.
- JPEG entropy-coded scan bytes match exactly.
- Multi-page TIFF, animated WebP, and multi-image AVIF/HEIF fixtures retain
  their structure, timing, primary-image status, color profile, and alpha.
- Large JPEG records exercise real Extended XMP chunking.

### Stage 5: Office Open XML and HTML

Changes:

- Implement package parts, content types, relationships, record targeting, and
  preservation for PowerPoint, Word, and Excel.
- Implement safe non-executable HTML data blocks and multiple-figure manifests.

Exit gate:

- Documents open without repair prompts in Microsoft Office and LibreOffice.
- Open/save round trips are classified in the survival matrix.
- Existing ZIP members, document relationships, images, and visible content are
  unchanged by embedding.
- HTML extraction resists `</script>`, Unicode, and malicious producer-text
  fixtures without executing content.

### Stage 6: HDF5, netCDF-4, and FITS

Changes:

- Add dedicated group or extension adapters and optional native table mirrors.
- Preserve native scientific structure and metadata.
- Add selection by figure identifier for multi-record containers.

Exit gate:

- Existing arrays, dimensions, groups, extensions, headers, compression, and
  attributes remain unchanged.
- Exact CSV and record bytes round-trip from each format.
- Native mirror divergence is detected.
- netCDF-3 is rejected without conversion.

### Stage 7: deterministic ZIP and RO-Crate

Changes:

- Implement the explicit bundle layout, deterministic ZIP writer, checksum
  verifier, secure extractor, and full RO-Crate metadata graph.
- Allow one bundle to contain several carriers and profiles.

Exit gate:

- Rebuilding the same bundle produces the same bytes.
- Every member hash verifies before extraction completes.
- Traversal, duplicate path, symbolic-link, device-file, and decompression-bomb
  fixtures are rejected.
- The RO-Crate validates and describes every included figure and data entity.

### Stage 8: publication, cataloguing, and command-line unification

Changes:

- Generalize `publish_figures`, extraction, scanning, captions, manifests, and
  validation reports to all adapters.
- Add format, carrier target, and survival information to catalogue rows.
- Produce public-safe companion CSV files regardless of the carrier.

Exit gate:

- A mixed batch containing SVG, PDF, PNG, JPEG, PowerPoint, and HDF5 produces
  validated public or minimal-public derivatives atomically.
- No output contains disallowed paths, credentials, private columns, or
  unapproved source locations.
- Existing SVG command lines remain unchanged.

### Stage 9: survival matrix and documentation

Test operations for every relevant carrier:

1. byte-for-byte copy and send
2. open and save without visible edits
3. metadata-only edit
4. crop or resize
5. recompress or optimize
6. export to the same format
7. export to another format
8. common publisher or web upload where an automated test endpoint is safe

Record each result as:

- `preserved`: record validates and exact data hashes match
- `stripped`: no record remains
- `corrupted`: a record remains but validation fails
- `not_tested`: software or operation was unavailable
- `not_applicable`: the operation has no meaning for that format

Exit gate:

- Documentation states the tested software name, version, operation, result,
  and recovery route.
- `reprofig formats` exposes the same measured support data.

### Stage 10: resolution, render policy, and final release

Resolution policy:

| Output | Default render target |
|---|---:|
| Screen preview | 150 dots per inch (DPI) |
| Continuous-tone or photographic raster | 300 DPI |
| Line art, plots, and text-heavy raster | 600 DPI |
| SVG or vector PDF | No intrinsic DPI; inspect embedded raster elements |

Publisher requirements always override these defaults. ReproFig does not infer
whether a figure is continuous-tone or line art from its appearance; callers
choose a preset or provide an explicit value.

Changes:

- Add `dpi`, `width`, `height`, `render_preset`, and format-specific compression
  options to `save_figure` and mixed-format publication calls.
- Use `dpi=300` as the default for newly rendered raster figures. Provide
  explicit `screen`, `continuous_tone`, and `line_art` presets, with a direct
  `dpi=` value taking precedence.
- Treat `dpi="preserve"` as the default when embedding into an existing raster
  file. `embed_file` must never resample pixels merely to add ReproFig data.
- Calculate raster pixel dimensions from the requested physical dimensions and
  DPI before rendering. Record the requested and resulting values separately.
- Do not silently upscale a low-resolution source. Fail or emit a validation
  warning unless the caller explicitly permits resampling.
- Keep compression separate from resolution: record JPEG/WebP/AVIF quality,
  PNG/TIFF compression, chroma subsampling, bit depth, and color space rather
  than treating DPI as an image-quality setting.
- For vector SVG and PDF, apply DPI only to rasterized artists and embedded
  images. Preserve vector geometry and editable text, and record the minimum
  and range of effective embedded-image DPI when they can be measured.
- Store actual carrier-specific rendering facts in the carrier manifest entry;
  store requested rendering settings with reproduction instructions.

Each carrier manifest record entry gains a `render` object containing, where
applicable:

```json
{
  "requested_dpi": 600,
  "actual_dpi_x": 600.0,
  "actual_dpi_y": 600.0,
  "width_px": 4252,
  "height_px": 2835,
  "physical_width_in": 7.0867,
  "physical_height_in": 4.725,
  "color_space": "sRGB",
  "bit_depth": 8,
  "codec": "tiff-deflate",
  "quality": null,
  "chroma_subsampling": null,
  "resampled": false,
  "source_width_px": 4252,
  "source_height_px": 2835,
  "embedded_raster_min_dpi": null
}
```

Validation requirements:

- Read actual pixel dimensions and density metadata back from the completed
  carrier instead of trusting requested settings.
- Report missing, conflicting, anisotropic, or implausible density metadata.
- Verify that `pixels = physical size in inches * DPI` within format rounding
  tolerance.
- Warn when a publication raster is below its selected preset.
- Confirm that metadata-only embedding leaves source pixels unchanged.
- Test non-square DPI, missing DPI, publisher-specific values, unit conversion,
  large dimensions, and low-resolution source handling.

Exit gate:

- Every raster adapter records requested and actual dimensions, density,
  compression, and resampling status accurately.
- SVG and PDF retain vector content while reporting embedded-raster resolution.
- The same requested physical size and DPI produce consistent pixel dimensions
  across PNG, TIFF, JPEG, WebP, and AVIF/HEIF within format constraints.
- Fresh installation tests cover Python 3.10 and newer on Windows and Linux.
- Built wheel and source distribution contain no fixtures with private data or
  local paths.
- The public release workflow publishes through the existing protected Python
  Package Index trusted publisher.

## Security and failure requirements

- Bound compressed and uncompressed record sizes before allocating memory.
- Stream large attachments and datasets where the underlying format permits it.
- Detect duplicate manifests, duplicate figure identifiers, conflicting
  records, and mismatched hashes.
- Reject path traversal and unsafe archive members before writing any file.
- Parse XML without external entities or network access.
- Never load embedded Python through pickle or import mechanisms.
- Never execute PDF actions, Office macros, HTML scripts, or producer code.
- Scrub private paths and credential-shaped values after profile conversion and
  before writing any public carrier or sidecar.
- Preserve the original file and use same-directory atomic replacement only
  after carrier and record validation succeed.
- Report when a pre-existing digital signature will be invalidated; do not
  silently claim the modified file remains signed.

## Definition of done

The expansion is complete only when:

- every requested suffix appears in `reprofig formats` with an installed or
  clearly unavailable adapter state;
- every installed adapter can embed, extract, inspect, validate, scan, and
  publish the three ReproFig profiles;
- extracted CSV and record bytes match their embedded hashes exactly;
- one mixed-format batch can generate public-safe carriers and companion CSVs;
- existing SVG, PyFLASH, PyMicroglia, and plot-that integrations still pass;
- no metadata-only embedding operation changes visible pixels or pages without
  explicit opt-in;
- every raster carrier reports requested and actual DPI, pixel dimensions,
  physical dimensions, compression settings, and resampling status;
- survival behavior is documented from executable tests; and
- ZIP/RO-Crate remains the recommended fallback whenever an editor or upload
  route is known to strip embedded metadata.

## Standards and implementation references

- [PNG Specification, Third Edition](https://www.w3.org/TR/png-3/)
- [Adobe XMP specifications and storage guidance](https://developer.adobe.com/xmp/docs/xmp-specifications/)
- [WebP RIFF container specification](https://developers.google.com/speed/webp/docs/riff_container)
- [pikepdf attachments and metadata documentation](https://pikepdf.readthedocs.io/en/latest/topics/metadata.html)
- [Microsoft Open Packaging Conventions](https://learn.microsoft.com/en-us/previous-versions/windows/desktop/opc/open-packaging-conventions-overview)
- [WHATWG HTML Standard](https://html.spec.whatwg.org/)
- [HDF5 data model](https://portal.hdfgroup.org/documentation/hdf5/latest/_h5_d_m__u_g.html)
- [netCDF data model](https://docs.unidata.ucar.edu/netcdf-c/current/netcdf_data_model.html)
- [Astropy FITS documentation](https://docs.astropy.org/en/stable/io/fits/index.html)
- [RO-Crate 1.2 specification](https://www.researchobject.org/ro-crate/specification/1.2/)
- [pillow-heif metadata API](https://pillow-heif.readthedocs.io/en/stable/reference/HeifImage.html)
