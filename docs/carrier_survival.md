# Carrier survival and recovery

ReproFig metadata behaves like a luggage label: copying the whole bag keeps it,
but repacking the contents may discard it. Always retain the master artifact.

## Tested operations

The automated 0.3.0 tests embed a complete record, reopen the result through
the format's native Python library, verify the record hash, and confirm that
visible pixels/pages or scientific arrays remain unchanged where applicable.

| Carrier | Copy/send | Metadata-only embed | Native reopen | Save/export survival | Recovery route |
|---|---|---|---|---|---|
| SVG | preserved | preserved | preserved with XML readers and tested Inkscape round trip | unknown editors may strip unknown metadata | `.reprofig.zip` |
| PDF | preserved | preserved; signed files require explicit invalidation | preserved with pikepdf | print/flatten workflows commonly strip attachments | attached record or ZIP |
| PNG | preserved | preserved byte-for-byte for non-ReproFig chunks | preserved with Pillow | web re-encoding may strip iTXt | ZIP |
| JPEG | preserved | preserved without changing scan bytes | preserved with Pillow | metadata stripping is common | ZIP |
| TIFF | preserved | preserved strips/tiles; Extensible Metadata Platform tag 700 added | preserved with Pillow/tifftools | editor behavior varies | ZIP |
| WebP | preserved | preserved Resource Interchange File Format media chunks | preserved with Pillow | re-export may omit XMP | ZIP |
| AVIF/HEIF | preserved | requires explicit re-encode consent | preserved with pillow-heif | not tested across editors | ZIP |
| PPTX/DOCX/XLSX | preserved | package parts and relationships preserved | package structure validated | Document Inspector or save-as may remove parts | ZIP |
| HTML | preserved | preserved in a non-executable data block | standard-library parser | content-management sanitizers may remove the block | linked ZIP |
| HDF5 | preserved | native group; arrays preserved | preserved with h5py | subset copies can omit the group | copy `/reprofig` or ZIP |
| netCDF-4 | preserved | native group; variables preserved | preserved with netCDF4 | subset copies can omit the group | copy named group or ZIP |
| FITS | preserved | `REPROFIG` binary-table Header/Data Unit | preserved with Astropy | primary-only copies omit extensions | copy all Header/Data Units or ZIP |
| ZIP/RO-Crate | preserved | deterministic rebuild | checksums verified before record extraction | not applicable | canonical fallback |

`preserved` means the embedded record validates and exact CSV hashes match.
Operations not exercised against a named desktop editor or upload endpoint are
reported as unknown rather than assumed safe.

## Proof, signature and encryption survival

The 0.3.0 adversarial suite round-trips one signed record with an encrypted CSV
through all sixteen carriers listed above. Every recovered carrier retains the
same evidence root, passes its Ed25519 signature and decrypts to the exact CSV
with the authorized password. Carrier metadata stripping still removes the
embedded proof; cryptography cannot make an unknown metadata block survive an
editor that deletes it.

SVG verification detects missing or changed bound vector subtrees and
annotation text. PNG proof detects a one-channel mutation inside a declared
scientific-mark region. PDF and other raster formats use the same region-aware
reference when their renderer is available. Signatures include the carrier's
visual-reference hash, so substituting a visual binding invalidates the
signature even when the shared scientific root is unchanged.

Encrypted sections survive carrier changes as ciphertext. Wrong passwords,
unrelated recipients, corrupt authentication tags, cross-figure ciphertext
swaps and oversized Argon2id parameters fail before plaintext is returned.

Publication workbooks additionally compare visible cells with the embedded
canonical projection. Their visible redacted dataset fingerprint is in the
signed evidence graph. Editing worksheets, aggregate evidence or statistics
cannot retain a valid signature without the signing key.

When a platform strips metadata, a trusted signed identity registry can recover
a public companion by exact carrier hash or nominate a visual-fingerprint
candidate. Visual recovery is explicitly weaker and never fetches a private
master.

## Resolution policy

- Screen previews: 150 dots per inch (DPI).
- Continuous-tone raster figures: 300 DPI.
- Line art and text-heavy plots: 600 DPI.
- SVG and vector PDF: no intrinsic DPI; raster elements retain their own
  resolution.

`save_figure` records requested and completed pixel dimensions, density,
physical size, colour mode, bit depth, codec settings, and resampling state in
the carrier manifest. `embed_file` preserves the existing pixels and density.
