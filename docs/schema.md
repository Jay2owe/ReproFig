# Figure record schema

`reprofig/1` is a package-neutral JSON record embedded through a carrier-
specific manifest. SVG uses a gzip-compressed Base64 metadata payload; other
carriers use attachments, metadata blocks, Office parts, native groups or a
deterministic archive entry. Unknown optional fields are ignored by version 1
readers. Required scientific meaning is supplied by the producing package; the
core never infers sample units or tests from rendered labels.

The top-level record contains stable figure identity, creation time, producer,
analysis context, one or more exact CSV tables, structured statistics, source
fingerprints, reproduction instructions, integrity metadata, and a distribution
profile (`master`, `public`, or `minimal_public`).

Each table records its exact UTF-8 CSV bytes, SHA-256 hash, shape, purpose, and
per-column semantic role plus `safe`, `private`, or `unclassified` publication
state. Statistics remain lossless JSON and also normalize deterministically to
a publisher-facing CSV whose hash is stored in the record.

Profile conversion is one-way:

```text
master -> public -> minimal_public
   |                       ^
   +-----------------------+
```

Public conversion requires an allowlist. A reduced record cannot recreate
private fields removed from its master.

## Optional publication aggregate

An Excel publication workbook embeds one aggregate `reprofig/1` record whose
`extensions.publication_workbook` contains
`reprofig-publication-workbook/1`. It binds publication identity, source figure
records, deduplicated tables, normalized statistics, test families, declared
coverage and exact worksheet mapping. Excel cells are projections; the
aggregate record is canonical.

## Optional proof graph

`extensions.proof` uses `reprofig-evidence-graph/1` and contains sorted evidence
sections, scientific claims, a SHA-256 Merkle-like root over canonical section
descriptors, optional statistical/transformation specifications and signature
envelopes. It is an additive version 1 extension; base readers need no proof
dependencies.

Default evidence section kinds are exact table, reported statistics,
provenance, render manifest, typed statistical specification, transformation
specification and publication aggregate. Each section declares a stable ID,
schema, dependencies, payload, encryption state and digest. Missing
dependencies, duplicate IDs, cycles, altered current-record evidence and root
mismatch are invalid.

Scientific claims identify their evidence and statistic IDs without affecting
the loose human-readable statistics records. Typed transformations use a closed
operation/version registry. Typed statistics use a separate closed
algorithm/version registry and keep exact expected results, tolerances and
display formatting distinct.

`extensions.render_manifest` uses `reprofig-render-manifest/1` for axes, marks
and annotations. `extensions.visual_reference` is carrier-specific and outside
the shared scientific root; signatures bind its deterministic hash separately.

Ed25519 signatures use `reprofig-signature/1`. Encrypted sections use
`reprofig-encrypted-section/1`. Public derivative lineage uses
`reprofig-proof-lineage/1`. Trust stores, output policies, promotion receipts
and identity registries are separate documents rather than trusted embedded
record fields.

## Compatibility

ReproFig 0.3 writes the same top-level `reprofig/1` schema as 0.2. Older readers
can inspect ordinary fields but cannot claim proof verification. Legacy
`figure-artifact/1` and `metafig/1` inputs remain readable. Unknown algorithms
or future component versions are `unsupported`, never silently coerced.
