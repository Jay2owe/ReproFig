"""Authenticated encryption of individual evidence sections."""

from __future__ import annotations

import base64
import json
import os
from typing import Any, Mapping, Sequence

from ..evidence import attach_evidence_graph, graph_from_record
from ..schema import EvidenceSection, FigureRecord, deterministic_json, sha256_bytes
from .recipients import unwrap_for_recipient, unwrap_with_password, wrap_for_recipients, wrap_with_password

ENCRYPTION_SCHEMA = "reprofig-encrypted-section/1"
MAX_CIPHERTEXT_BYTES = 250 * 1024 * 1024


def _aad(record: FigureRecord, section: EvidenceSection, public: Mapping[str, Any]) -> bytes:
    return deterministic_json({
        "domain": "ReproFig encrypted evidence v1",
        "figure_id": record.figure_id,
        "record_schema": record.schema,
        "section_id": section.section_id,
        "section_schema": section.schema,
        "public": dict(public),
    }).encode("utf-8")


def encrypt_sections(
    record: FigureRecord,
    section_ids: Sequence[str],
    *,
    password: str | bytes | None = None,
    recipients: Mapping[str, str] | None = None,
) -> FigureRecord:
    if password is None and not recipients:
        raise ValueError("section encryption requires a password or at least one named recipient")
    graph = graph_from_record(record)
    selected = set(map(str, section_ids))
    known = {str(section.section_id) for section in graph.sections}
    missing = sorted(selected - known)
    if missing:
        raise ValueError("unknown evidence sections: " + ", ".join(missing))
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    encrypted: list[EvidenceSection] = []
    for section in graph.sections:
        if str(section.section_id) not in selected:
            encrypted.append(section)
            continue
        if section.encrypted:
            raise ValueError(f"evidence section {section.section_id} is already encrypted")
        plaintext = deterministic_json(section.payload).encode("utf-8")
        if len(plaintext) > MAX_CIPHERTEXT_BYTES:
            raise ValueError(f"evidence section {section.section_id} exceeds encryption limit")
        content_key = os.urandom(32)
        nonce = os.urandom(12)
        public = {
            "schema": ENCRYPTION_SCHEMA,
            "algorithm": "AES-256-GCM",
            "plaintext_sha256": sha256_bytes(plaintext),
            "plaintext_size": len(plaintext),
        }
        aad = _aad(record, section, public)
        ciphertext = AESGCM(content_key).encrypt(nonce, plaintext, aad)
        envelopes: dict[str, Any] = {}
        if password is not None:
            envelopes["password"] = wrap_with_password(content_key, password, aad=aad)
        if recipients:
            envelopes["recipients"] = wrap_for_recipients(content_key, recipients, aad=aad)
        descriptor = {
            **public, "nonce": base64.b64encode(nonce).decode("ascii"),
            "ciphertext": base64.b64encode(ciphertext).decode("ascii"),
            "ciphertext_sha256": sha256_bytes(ciphertext), "envelopes": envelopes,
        }
        encrypted.append(EvidenceSection(
            section_id=section.section_id, kind=section.kind, schema=section.schema,
            payload=descriptor, dependencies=section.dependencies, encrypted=True,
            metadata={key: value for key, value in section.metadata.items() if key in {"label", "purpose"}},
        ))
    result = FigureRecord.from_dict(record.to_dict())
    proof = dict(result.extensions.get("proof") or {})
    proof["signatures"] = []
    for index, table in enumerate(result.data_tables):
        if f"table:{table.sha256}" in selected:
            table.name = f"protected_table_{index + 1}"
            table.purpose = "protected"
            table.row_count = 0
            table.column_count = 0
            table.columns = []
            table.contents = None
            table.metadata = {"protected": True}
    if any(f"table:{table.sha256}" in selected for table in result.data_tables):
        result.data_status = "protected"
    if "statistics:reported" in selected:
        result.statistics = []
        result.statistics_status = "protected"
        result.statistics_csv_sha256 = None
    if "provenance:record" in selected:
        result.producer = {"protected": True}
        result.analysis = {}
        result.sources = []
        result.reproduction = {}
    if "render:manifest" in selected:
        result.extensions.pop("render_manifest", None)
        result.extensions.pop("visual_reference", None)
    if "publication:aggregate" in selected:
        result.extensions.pop("publication_workbook", None)
    proof["statistical_specifications"] = [
        value
        for value in proof.get("statistical_specifications", [])
        if f"statistical-specification:{value.get('statistic_id') or value.get('test_id')}"
        not in selected
    ]
    proof["transformations"] = [
        value
        for value in proof.get("transformations", [])
        if f"transformation-specification:{value.get('transform_id')}" not in selected
    ]
    result.extensions["proof"] = proof
    return attach_evidence_graph(result, sections=encrypted, claims=graph.claims)


def decrypt_sections(
    record: FigureRecord,
    *,
    password: str | bytes | None = None,
    recipient_private_key: Any | None = None,
) -> dict[str, Any]:
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    graph = graph_from_record(record)
    result: dict[str, Any] = {}
    for section in graph.sections:
        if not section.encrypted:
            result[str(section.section_id)] = section.payload
            continue
        descriptor = section.payload
        if not isinstance(descriptor, Mapping) or descriptor.get("schema") != ENCRYPTION_SCHEMA:
            raise ValueError(f"invalid encrypted descriptor for {section.section_id}")
        ciphertext = base64.b64decode(str(descriptor["ciphertext"]), validate=True)
        if len(ciphertext) > MAX_CIPHERTEXT_BYTES or sha256_bytes(ciphertext) != descriptor.get("ciphertext_sha256"):
            raise ValueError(f"ciphertext integrity or size failure for {section.section_id}")
        public = {key: descriptor[key] for key in ("schema", "algorithm", "plaintext_sha256", "plaintext_size")}
        aad_section = section
        aad_identity = descriptor.get("aad_section_id")
        if aad_identity:
            aad_section = EvidenceSection.from_dict({
                **section.to_dict(), "section_id": str(aad_identity)
            })
        aad = _aad(record, aad_section, public)
        envelopes = descriptor.get("envelopes") or {}
        if password is not None and isinstance(envelopes.get("password"), Mapping):
            content_key = unwrap_with_password(envelopes["password"], password, aad=aad)
        elif recipient_private_key is not None and isinstance(envelopes.get("recipients"), list):
            content_key = unwrap_for_recipient(envelopes["recipients"], recipient_private_key, aad=aad)
        else:
            raise PermissionError(f"no usable key for encrypted section {section.section_id}")
        plaintext = AESGCM(content_key).decrypt(
            base64.b64decode(str(descriptor["nonce"]), validate=True), ciphertext, aad
        )
        if len(plaintext) != int(descriptor["plaintext_size"]) or sha256_bytes(plaintext) != descriptor["plaintext_sha256"]:
            raise ValueError(f"plaintext identity mismatch for {section.section_id}")
        result[str(section.section_id)] = json.loads(plaintext)
    return result


def decrypt_record(
    record: FigureRecord,
    *,
    password: str | bytes | None = None,
    recipient_private_key: Any | None = None,
) -> FigureRecord:
    """Materialize accessible plaintext in a verification-only record copy."""

    from ..schema import DataTable, SourceReference

    result = FigureRecord.from_dict(record.to_dict())
    graph = graph_from_record(record)
    sections = {str(value.section_id): value for value in graph.sections}
    values = decrypt_sections(
        record,
        password=password,
        recipient_private_key=recipient_private_key,
    )
    proof = dict(result.extensions.get("proof") or {})
    for identity, payload in values.items():
        section = sections[identity]
        if not section.encrypted:
            continue
        if section.kind == "table" and isinstance(payload, Mapping):
            table = DataTable.from_dict(payload.get("table") or {})
            index = int(payload.get("index", 0))
            while len(result.data_tables) <= index:
                result.data_tables.append(table)
            result.data_tables[index] = table
            result.data_status = "complete"
        elif section.kind == "statistics" and isinstance(payload, Mapping):
            result.statistics = list(payload.get("records") or [])
            result.statistics_status = str(payload.get("status", "complete"))
        elif section.kind == "provenance" and isinstance(payload, Mapping):
            result.producer = dict(payload.get("producer") or {})
            result.analysis = dict(payload.get("analysis") or {})
            result.sources = [
                value
                if isinstance(value, SourceReference)
                else SourceReference.from_dict(value)
                for value in payload.get("sources") or []
            ]
            result.reproduction = dict(payload.get("reproduction") or {})
        elif section.kind == "render_manifest" and isinstance(payload, Mapping):
            result.extensions["render_manifest"] = dict(payload)
        elif section.kind == "statistical_specification" and isinstance(payload, Mapping):
            proof.setdefault("statistical_specifications", []).append(dict(payload))
        elif section.kind == "transformation_specification" and isinstance(payload, Mapping):
            proof.setdefault("transformations", []).append(dict(payload))
    result.extensions["proof"] = proof
    return result


__all__ = [
    "ENCRYPTION_SCHEMA", "decrypt_record", "decrypt_sections", "encrypt_sections"
]
