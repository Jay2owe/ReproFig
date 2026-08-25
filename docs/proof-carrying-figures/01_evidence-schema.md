# Stage 01 — Define the typed proof-carrying evidence schema

## Why this stage exists

ReproFig 0.2 stores exact tables, source fingerprints and statistics, but the statistics and reproduction fields are open-ended dictionaries. Every later verifier needs stable, typed identities for claims, transformations, statistical tests, render manifests and cryptographic envelopes. This stage creates that contract while keeping every existing `reprofig/1` artifact readable.

## Prerequisites

- All stages in `docs/publication-workbook/` must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- `docs/publication-workbook/00_overview.md:1-74`
- `docs/publication-workbook/01_publication-dataset-contract_COMPLETED.md:1-end`
- `docs/publication-workbook/03_statistics-ledger_COMPLETED.md:1-end`
- `docs/publication-workbook/05_embedded-evidence-and-validation_COMPLETED.md:1-end`
- `src/reprofig/schema.py:1-353`
- `src/reprofig/workbook/models.py:1-end`
- `src/reprofig/workbook/evidence.py:1-end`
- `src/reprofig/__init__.py:1-105`
- `docs/schema.md:1-27`
- `tests/test_schema_fixture.py:1-12`
- `tests/fixtures/figure-record-v1.json:1-15`

## Scope

- Record a short compatibility decision before changing serialization.
- Introduce typed records for evidence sections, claims, transformation specifications, statistical specifications, semantic render manifests and cryptographic-envelope descriptors.
- Give every typed object a stable local identity and explicit schema/version field.
- Preserve deterministic serialization and JSON-safe values.
- Add explicit references between claims and supporting evidence identities.
- Continue reading `reprofig/1` and all legacy aliases without inventing missing proof fields.
- Keep ordinary 0.2 callers writing `reprofig/1` unless they explicitly supply proof-carrying evidence.
- Extend publication datasets, aggregate workbook records, stable table identities and stable test identities instead of defining parallel workbook concepts.
- Add a versioned fixture demonstrating a complete proof-carrying record.
- Export the new public types without importing optional statistics, visual or cryptographic packages.
- Freeze the existing simple build, save, inspect and extraction call signatures and defaults as a compatibility contract before later stages extend them.

## Out of scope

- Canonical evidence-root hashing belongs to Stage 02.
- Verification grades and reports belong to Stage 03.
- Executing transformations or statistics belongs to Stages 04–08.
- Rendering, signing and encryption behavior belongs to Stages 09–16.
- Carrier-specific changes are not needed: carriers continue embedding canonical record bytes.

## Files touched

| path | change | reason |
|---|---|---|
| `docs/decisions/proof-schema-version.md` | NEW | Record the compatibility decision and migration contract. |
| `src/reprofig/schema.py` | MODIFY | Define and serialize the new typed evidence objects. |
| `src/reprofig/workbook/models.py` | MODIFY | Let publication tables and statistics refer to optional typed proof identities. |
| `src/reprofig/__init__.py` | MODIFY | Export the package-neutral public schema types. |
| `docs/schema.md` | MODIFY | Document required meaning, identities and compatibility. |
| `tests/fixtures/figure-record-v2.json` | NEW | Freeze a package-neutral proof-carrying fixture. |
| `tests/test_schema_fixture.py` | MODIFY | Exercise old and new records, unknown optional fields and deterministic round trips. |
| `tests/test_api_compat.py` | MODIFY | Freeze the base install, public signatures, defaults and simple save/extract behavior. |

## Implementation sketch

Use a new top-level schema identifier when proof fields are present; the recommended decision is `reprofig/2`. Keep the version-1 writer as the default compatibility route.

```python
@dataclass
class EvidenceSection:
    section_id: str
    kind: str
    schema: str
    media_type: str | None = None
    contents: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

@dataclass
class ClaimSpec:
    claim_id: str
    statement: str
    evidence_ids: list[str] = field(default_factory=list)
    display_ids: list[str] = field(default_factory=list)

@dataclass
class TransformationSpec:
    transform_id: str
    algorithm: str
    inputs: list[str]
    output: str
    parameters: dict[str, Any] = field(default_factory=dict)

@dataclass
class StatisticalSpec:
    statistic_id: str
    algorithm: str
    inputs: dict[str, Any]
    parameters: dict[str, Any]
    expected: dict[str, Any]
    display: dict[str, Any] = field(default_factory=dict)

@dataclass
class RenderManifest:
    schema: str
    coordinate_system: dict[str, Any]
    marks: list[dict[str, Any]]
    annotations: list[dict[str, Any]]

@dataclass
class CryptoEnvelope:
    envelope_id: str
    purpose: str
    algorithm: str
    section_ids: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
```

The proof-carrying `FigureRecord` should refer to these through explicit fields rather than hiding them in `extensions`. Every `from_dict` method accepts unknown optional fields without treating them as verified meaning. Required fields fail with precise validation messages.

Version-1 input maps only existing meaning:

```text
data_tables -> existing exact table evidence
statistics -> existing untyped result records
reproduction -> existing opaque reproduction context
new typed proof collections -> absent
verification status -> not evaluated
```

Do not claim that old statistics are declarative merely because they are dictionaries.

## Exit gate

1. The version decision document states the writer and reader behavior for `reprofig/1`, legacy aliases and the new schema.
2. `FigureRecord.from_json()` reads the existing version-1 fixture unchanged.
3. The new fixture round-trips to byte-identical deterministic JSON.
4. Removing a required typed identity produces a targeted schema error.
5. Unknown optional fields do not prevent reading the record and are not silently promoted to verified fields.
6. Importing `reprofig` still succeeds with no scientific or cryptographic optional dependencies installed.
7. `pytest tests/test_schema_fixture.py -q` passes.
8. `pytest tests/test_api_compat.py -q` proves current callers need no new argument, metadata field or optional dependency.

## Known risks

- Changing the default schema would break existing consumers; keep proof writing explicit until migrations are complete.
- Generic dictionaries are tempting for speed but would force every verifier to reinterpret meaning. Keep typed boundaries even if payload values remain JSON-compatible.
- A schema that includes cryptographic behavior too early may freeze unsafe details. This stage records envelope descriptors only; algorithms are implemented later.
