"""Canonical proof evidence graph and tamper-evident roots."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping, Sequence

from .schema import (
    EvidenceSection,
    FigureRecord,
    ScientificClaim,
    deterministic_json,
    sha256_bytes,
)

EVIDENCE_GRAPH_SCHEMA = "reprofig-evidence-graph/1"
EVIDENCE_ROOT_DOMAIN = b"ReproFig evidence root v1\x00"
SIGNATURE_DOMAIN = b"ReproFig signature v1\x00"


@dataclass(frozen=True)
class EvidenceGraph:
    figure_id: str
    record_schema: str
    sections: tuple[EvidenceSection, ...]
    claims: tuple[ScientificClaim, ...]
    root_sha256: str
    schema: str = EVIDENCE_GRAPH_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "figure_id": self.figure_id,
            "record_schema": self.record_schema,
            "sections": [value.to_dict() for value in self.sections],
            "claims": [value.to_dict() for value in self.claims],
            "root_sha256": self.root_sha256,
        }


def canonical_section_bytes(section: EvidenceSection) -> bytes:
    return deterministic_json(section.content_dict()).encode("utf-8")


def section_digest(section: EvidenceSection) -> str:
    return sha256_bytes(canonical_section_bytes(section))


def _validate_graph(sections: Sequence[EvidenceSection], claims: Sequence[ScientificClaim]) -> None:
    by_id: dict[str, EvidenceSection] = {}
    for section in sections:
        identity = str(section.section_id)
        if identity in by_id:
            raise ValueError(f"duplicate evidence section identity: {identity}")
        by_id[identity] = section
        if section.sha256 and section.sha256 != section_digest(section):
            raise ValueError(f"evidence section digest mismatch: {identity}")
    for section in sections:
        missing = sorted(set(section.dependencies) - set(by_id))
        if missing:
            raise ValueError(
                f"evidence section {section.section_id} has missing dependencies: {', '.join(missing)}"
            )
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(identity: str) -> None:
        if identity in visiting:
            raise ValueError(f"evidence dependency cycle includes {identity}")
        if identity in visited:
            return
        visiting.add(identity)
        for dependency in by_id[identity].dependencies:
            visit(dependency)
        visiting.remove(identity)
        visited.add(identity)

    for identity in sorted(by_id):
        visit(identity)
    claim_ids: set[str] = set()
    for claim in claims:
        identity = str(claim.claim_id)
        if identity in claim_ids:
            raise ValueError(f"duplicate claim identity: {identity}")
        claim_ids.add(identity)
        missing = sorted(set(claim.evidence_ids) - set(by_id))
        if missing:
            raise ValueError(f"claim {identity} has missing evidence: {', '.join(missing)}")


def evidence_root_input(
    figure_id: str,
    record_schema: str,
    sections: Sequence[EvidenceSection],
    claims: Sequence[ScientificClaim] = (),
) -> bytes:
    _validate_graph(sections, claims)
    descriptors = [
        {
            "section_id": section.section_id,
            "kind": section.kind,
            "sha256": section_digest(section),
            "dependencies": list(section.dependencies),
            "encrypted": section.encrypted,
        }
        for section in sorted(sections, key=lambda value: str(value.section_id))
    ]
    claim_descriptors = [
        claim.to_dict() for claim in sorted(claims, key=lambda value: str(value.claim_id))
    ]
    payload = deterministic_json({
        "domain": "reprofig-evidence-root-v1",
        "figure_id": str(figure_id),
        "record_schema": str(record_schema),
        "sections": descriptors,
        "claims": claim_descriptors,
    }).encode("utf-8")
    return EVIDENCE_ROOT_DOMAIN + payload


def calculate_evidence_root(
    figure_id: str,
    record_schema: str,
    sections: Sequence[EvidenceSection],
    claims: Sequence[ScientificClaim] = (),
) -> str:
    return sha256_bytes(evidence_root_input(figure_id, record_schema, sections, claims))


def default_evidence_sections(record: FigureRecord) -> list[EvidenceSection]:
    sections: list[EvidenceSection] = []
    table_ids: list[str] = []
    for index, table in enumerate(record.data_tables):
        section = EvidenceSection(
            section_id=f"table:{table.sha256}",
            kind="table",
            payload={"index": index, "table": table.to_dict()},
        )
        sections.append(section)
        table_ids.append(str(section.section_id))
    if record.statistics:
        sections.append(
            EvidenceSection(
                section_id="statistics:reported",
                kind="statistics",
                payload={"status": record.statistics_status, "records": record.statistics},
                dependencies=table_ids,
            )
        )
    provenance = {
        "producer": record.producer,
        "analysis": record.analysis,
        "sources": [source.to_dict() for source in record.sources],
        "reproduction": record.reproduction,
    }
    sections.append(EvidenceSection(section_id="provenance:record", kind="provenance", payload=provenance))
    render = record.extensions.get("render_manifest")
    if isinstance(render, Mapping):
        sections.append(
            EvidenceSection(
                section_id="render:manifest",
                kind="render_manifest",
                payload=dict(render),
                dependencies=table_ids + (["statistics:reported"] if record.statistics else []),
            )
        )
    existing_proof = record.extensions.get("proof")
    if isinstance(existing_proof, Mapping):
        for specification in existing_proof.get("statistical_specifications", []) or []:
            identity = specification.get("statistic_id") or specification.get("test_id")
            sections.append(
                EvidenceSection(
                    section_id=f"statistical-specification:{identity}",
                    kind="statistical_specification",
                    payload=dict(specification),
                    dependencies=table_ids,
                )
            )
        for transformation in existing_proof.get("transformations", []) or []:
            identity = transformation.get("transform_id")
            sections.append(
                EvidenceSection(
                    section_id=f"transformation-specification:{identity}",
                    kind="transformation_specification",
                    payload=dict(transformation),
                    dependencies=[],
                )
            )
    publication = record.extensions.get("publication_workbook")
    if isinstance(publication, Mapping):
        visible_fingerprint = publication.get(
            "visible_logical_fingerprint", publication.get("logical_fingerprint")
        )
        sections.append(
            EvidenceSection(
                section_id="publication:aggregate",
                kind="publication_workbook",
                payload={
                    "publication_id": publication.get("publication_id"),
                    "logical_fingerprint": publication.get("logical_fingerprint"),
                    "visible_logical_fingerprint": visible_fingerprint,
                    "sheet_map": publication.get("sheet_map"),
                },
                dependencies=table_ids + (["statistics:reported"] if record.statistics else []),
            )
        )
    return sections


def graph_from_record(record: FigureRecord) -> EvidenceGraph:
    proof = record.extensions.get("proof") or {}
    section_values = proof.get("sections") if isinstance(proof, Mapping) else None
    claim_values = proof.get("claims") if isinstance(proof, Mapping) else None
    sections = (
        [EvidenceSection.from_dict(item) for item in section_values]
        if isinstance(section_values, list)
        else default_evidence_sections(record)
    )
    claims = (
        [ScientificClaim.from_dict(item) for item in claim_values]
        if isinstance(claim_values, list)
        else []
    )
    root = calculate_evidence_root(record.figure_id, record.schema, sections, claims)
    if isinstance(section_values, list):
        stored_by_id = {str(section.section_id): section for section in sections}
        for expected_section in default_evidence_sections(record):
            stored = stored_by_id.get(str(expected_section.section_id))
            if stored is None:
                raise ValueError(
                    f"proof graph omits current record evidence {expected_section.section_id}"
                )
            if not stored.encrypted and section_digest(stored) != section_digest(expected_section):
                raise ValueError(
                    f"proof section {expected_section.section_id} disagrees with current record"
                )
    stored = proof.get("root_sha256") if isinstance(proof, Mapping) else None
    if stored and stored != root:
        raise ValueError(f"stored evidence root does not match reconstructed root: {stored} != {root}")
    return EvidenceGraph(record.figure_id, record.schema, tuple(sections), tuple(claims), root)


def attach_evidence_graph(
    record: FigureRecord,
    *,
    sections: Sequence[EvidenceSection] | None = None,
    claims: Sequence[ScientificClaim] | None = None,
) -> FigureRecord:
    result = FigureRecord.from_dict(record.to_dict())
    values = list(sections) if sections is not None else default_evidence_sections(result)
    previous = result.extensions.get("proof")
    if claims is None:
        claims = (
            [ScientificClaim.from_dict(value) for value in previous.get("claims", [])]
            if isinstance(previous, Mapping)
            else []
        )
    root = calculate_evidence_root(result.figure_id, result.schema, values, claims)
    preserved = (
        {
            key: value
            for key, value in previous.items()
            if key not in {"schema", "sections", "claims", "root_sha256", "signatures"}
        }
        if isinstance(previous, Mapping)
        else {}
    )
    signatures = previous.get("signatures", []) if isinstance(previous, Mapping) else []
    result.extensions["proof"] = {
        **preserved,
        "schema": EVIDENCE_GRAPH_SCHEMA,
        "sections": [section.to_dict() for section in values],
        "claims": [claim.to_dict() for claim in claims],
        "root_sha256": root,
        "signatures": signatures,
    }
    return result


def refresh_evidence_graph(record: FigureRecord) -> FigureRecord:
    """Refresh current evidence while safely retaining protected sections.

    Unencrypted default sections are rebuilt from the current record. Encrypted
    sections are reused only when their public plaintext digest proves that the
    current payload is identical. This lets one encrypted record be carried
    across SVG/raster variants without silently blessing a changed figure.
    """

    result = FigureRecord.from_dict(record.to_dict())
    previous = result.extensions.get("proof")
    if not isinstance(previous, Mapping) or not isinstance(previous.get("sections"), list):
        return attach_evidence_graph(result)

    defaults = {
        str(section.section_id): section for section in default_evidence_sections(result)
    }
    refreshed: list[EvidenceSection] = []
    seen: set[str] = set()

    def can_compare_encrypted_source(identity: str) -> bool:
        if identity.startswith("table:"):
            return result.data_status != "protected"
        if identity == "statistics:reported":
            return result.statistics_status != "protected"
        if identity == "provenance:record":
            return result.producer.get("protected") is not True
        if identity == "publication:aggregate":
            return "publication_workbook" in result.extensions
        if identity.startswith("statistical-specification:"):
            return bool((result.extensions.get("proof") or {}).get("statistical_specifications"))
        if identity.startswith("transformation-specification:"):
            return bool((result.extensions.get("proof") or {}).get("transformations"))
        return True

    for raw in previous["sections"]:
        section = EvidenceSection.from_dict(raw)
        identity = str(section.section_id)
        current = defaults.get(identity)
        if section.encrypted:
            if current is not None and can_compare_encrypted_source(identity):
                declared = (
                    section.payload.get("plaintext_sha256")
                    if isinstance(section.payload, Mapping)
                    else None
                )
                actual = sha256_bytes(deterministic_json(current.payload).encode("utf-8"))
                if declared != actual:
                    raise ValueError(
                        f"encrypted evidence {identity} cannot be reused after its source changed"
                    )
            refreshed.append(section)
        elif current is not None:
            refreshed.append(current)
        else:
            # Keep explicit non-default evidence, such as a protected or custom
            # statistical specification, that has no top-level representation.
            refreshed.append(section)
        seen.add(identity)
    refreshed.extend(
        section for identity, section in defaults.items() if identity not in seen
    )
    claims = [
        ScientificClaim.from_dict(value) for value in previous.get("claims", [])
    ]
    return attach_evidence_graph(result, sections=refreshed, claims=claims)


def signature_input(
    *,
    figure_id: str,
    record_schema: str,
    root_sha256: str,
    policy_context: Mapping[str, Any] | None = None,
    artifact_binding_sha256: str | None = None,
) -> bytes:
    payload = {
        "figure_id": figure_id,
        "record_schema": record_schema,
        "evidence_root": root_sha256,
        "policy_context": dict(policy_context or {}),
    }
    if artifact_binding_sha256 is not None:
        payload["artifact_binding_sha256"] = artifact_binding_sha256
    return SIGNATURE_DOMAIN + deterministic_json(payload).encode("utf-8")


__all__ = [
    "EVIDENCE_GRAPH_SCHEMA",
    "EvidenceGraph",
    "attach_evidence_graph",
    "calculate_evidence_root",
    "canonical_section_bytes",
    "default_evidence_sections",
    "evidence_root_input",
    "graph_from_record",
    "refresh_evidence_graph",
    "section_digest",
    "signature_input",
]
