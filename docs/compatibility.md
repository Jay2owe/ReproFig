# Compatibility decisions

## Figure-Statistics Bundle

Figure-Statistics Bundle version 0.1.1 is a close conceptual match: canonical
CSV data, structured statistics, encodings, themes, and derived SVG exports. It
uses a directory as the canonical artifact and is licensed under the GNU Affero
General Public License version 3.

ReproFig therefore does not depend on Figure-Statistics Bundle. It
provides import and export functions that map the overlapping fields while
retaining embedded-SVG records and distribution profiles as explicit
extensions.

## Research Object Crate

Research Object Crate is used as an optional outer publication bundle. The SVG
record remains canonical when it travels alone.

## Frictionless tabular descriptors

Data-table metadata includes names, types, semantic roles, public states,
dimensions, and SHA-256 fingerprints. A future optional exporter can translate
these descriptors to Frictionless Data without changing the core schema.
