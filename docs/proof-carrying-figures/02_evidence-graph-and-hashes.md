# Stage 02 — Build the canonical evidence graph and tamper-evident root

## Why this stage exists

A signature or independent verifier needs one unambiguous answer to “what exactly is covered?” Existing table checksums protect individual payloads, but they do not bind claims, transformations, statistics and render semantics together. This stage creates a deterministic dependency graph and evidence root that later signatures and verification reports can trust.

## Prerequisites

- Stage 01 must be `_COMPLETED`.

## Read first

- `docs/proof-carrying-figures/00_overview.md:1-150`
- `docs/proof-carrying-figures/01_evidence-schema_COMPLETED.md` in its completed form
- `docs/publication-workbook/05_embedded-evidence-and-validation_COMPLETED.md:1-end`
- `src/reprofig/schema.py:1-353` plus the Stage 01 additions
- `src/reprofig/workbook/evidence.py:1-end`
- `src/reprofig/validation.py:1-246`
- `src/reprofig/carriers/manifest.py:1-191`
- `src/reprofig/carriers/payload.py:1-89`
- `tests/test_roundtrip.py:1-160`

## Scope

- Canonicalize every evidence section independently.
- Calculate a SHA-256 digest for each section.
- Record directed dependencies such as claim -> statistic -> transformed table -> source table.
- Reject missing references, duplicate identities and cycles.
- Build one domain-separated evidence-root input from the figure identity, schema and sorted section descriptors.
- Exclude signatures themselves from the signed root to avoid recursive self-hashing.
- Include ciphertext and encryption-envelope hashes once encrypted sections exist.
- Expose graph inspection and root calculation through the Python application programming interface.
- Validate stored roots against reconstructed roots.
- Give a publication workbook one evidence root derived from its aggregate record and canonical publication fingerprint, never from mutable Excel ZIP bytes.

## Out of scope

- Deciding whether a calculation is correct belongs to Stages 04–08.
- Verification-report presentation belongs to Stage 03.
- Digital signature creation belongs to Stage 13.
- Trust, encryption and public-profile behavior belong to Stages 14–16.

## Files touched

| path | change | reason |
|---|---|---|
| `src/reprofig/evidence.py` | NEW | Canonical section bytes, dependency graph and evidence-root calculation. |
| `src/reprofig/schema.py` | MODIFY | Store section digests, dependency references and evidence-root metadata. |
| `src/reprofig/validation.py` | MODIFY | Detect graph and root integrity failures. |
| `src/reprofig/api.py` | MODIFY | Export graph inspection and root calculation. |
| `src/reprofig/workbook/evidence.py` | MODIFY | Bind workbook aggregate evidence and the publication fingerprint into the graph. |
| `docs/schema.md` | MODIFY | Specify canonicalization and signed-root boundaries. |
| `tests/test_evidence_graph.py` | NEW | Cover determinism, cycles, missing references and tampering. |

## Implementation sketch

```python
@dataclass(frozen=True)
class SectionDigest:
    section_id: str
    kind: str
    schema: str
    sha256: str
    dependencies: tuple[str, ...] = ()

@dataclass
class EvidenceGraph:
    figure_id: str
    sections: list[SectionDigest]
    root_sha256: str

def canonical_section_bytes(section: Any) -> bytes: ...
def build_evidence_graph(record: FigureRecord) -> EvidenceGraph: ...
def verify_evidence_graph(record: FigureRecord) -> list[ValidationIssue]: ...
```

The root input is deterministic JSON and uses explicit domain separation:

```json
{
  "domain": "reprofig-evidence-root/v1",
  "figure_id": "fig-...",
  "record_schema": "reprofig/2",
  "sections": [
    {
      "section_id": "source-table",
      "kind": "data_table",
      "schema": "reprofig-table/1",
      "sha256": "...",
      "dependencies": []
    }
  ]
}
```

Sort sections by UTF-8 `section_id`; sort dependency identities; reject duplicate normalized identities. The root is the SHA-256 digest of the canonical root-input bytes. The whole carrier hash remains external because embedding it inside itself would be recursive.

Store enough information to distinguish:

```text
section hash mismatch
dependency graph mismatch
evidence root mismatch
carrier record hash mismatch
```

## Exit gate

1. Reordering dictionary keys, sections or dependency inputs does not change the evidence root.
2. Changing one table byte, test parameter, expected result, display binding or ciphertext byte changes the evidence root.
3. Adding an unreferenced section changes the root and is visible in graph inspection.
4. Duplicate section identities, missing dependencies and dependency cycles fail validation.
5. A stored evidence root validates after round trips through at least Scalable Vector Graphics and ZIP carriers.
6. Existing `reprofig/1` records remain valid but report that no proof graph is present.
7. `pytest tests/test_evidence_graph.py tests/test_roundtrip.py -q` passes.
8. A harmless Excel package rewrite that leaves embedded logical evidence unchanged leaves the publication evidence root unchanged.

## Known risks

- Hashing carrier bytes would create recursion and break after harmless metadata rewrites; sign canonical evidence sections instead.
- Normalizing numerical values too aggressively can make distinct calculations hash identically. Canonicalization must preserve declared type and exact representation.
- Dangling unreferenced evidence may conceal data. Include every section in the root even when no claim references it.
