"""Ed25519 signature envelopes over canonical ReproFig evidence roots."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from typing import Any, Mapping

from ..evidence import attach_evidence_graph, graph_from_record, signature_input
from ..schema import FigureRecord, json_safe
from ..schema import deterministic_json, sha256_bytes
from ..verification import ProofCheck
from .keys import load_signing_private_key, public_key_fingerprint, signing_public_bytes

SIGNATURE_SCHEMA = "reprofig-signature/1"


@dataclass
class SignatureEnvelope:
    key_fingerprint: str
    public_key: str
    signature: str
    evidence_root: str
    artifact_binding_sha256: str | None = None
    policy_context: dict[str, Any] = field(default_factory=dict)
    algorithm: str = "Ed25519"
    schema: str = SIGNATURE_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        value = {
            "schema": self.schema, "algorithm": self.algorithm,
            "key_fingerprint": self.key_fingerprint, "public_key": self.public_key,
            "signature": self.signature, "evidence_root": self.evidence_root,
            "policy_context": json_safe(self.policy_context),
        }
        if self.artifact_binding_sha256 is not None:
            value["artifact_binding_sha256"] = self.artifact_binding_sha256
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "SignatureEnvelope":
        return cls(
            schema=str(value.get("schema", SIGNATURE_SCHEMA)),
            algorithm=str(value.get("algorithm", "")),
            key_fingerprint=str(value.get("key_fingerprint", "")),
            public_key=str(value.get("public_key", "")), signature=str(value.get("signature", "")),
            evidence_root=str(value.get("evidence_root", "")),
            artifact_binding_sha256=value.get("artifact_binding_sha256"),
            policy_context=dict(value.get("policy_context") or {}),
        )


def _artifact_binding(record: FigureRecord) -> str | None:
    value = record.extensions.get("visual_reference")
    if not isinstance(value, Mapping):
        return None
    return sha256_bytes(deterministic_json(value).encode("utf-8"))


def sign_record(
    record: FigureRecord,
    *,
    private_key_path: str,
    password: str | bytes,
    policy_context: Mapping[str, Any] | None = None,
) -> FigureRecord:
    result = FigureRecord.from_dict(record.to_dict())
    if not isinstance(result.extensions.get("proof"), Mapping) or not result.extensions["proof"].get("root_sha256"):
        result = attach_evidence_graph(result)
    graph = graph_from_record(result)
    private_key = load_signing_private_key(private_key_path, password=password)
    public_bytes = signing_public_bytes(private_key)
    context = dict(json_safe(policy_context or {}))
    artifact_binding = _artifact_binding(result)
    signed = signature_input(
        figure_id=result.figure_id, record_schema=result.schema,
        root_sha256=graph.root_sha256, policy_context=context,
        artifact_binding_sha256=artifact_binding,
    )
    envelope = SignatureEnvelope(
        key_fingerprint=public_key_fingerprint(public_bytes),
        public_key=base64.b64encode(public_bytes).decode("ascii"),
        signature=base64.b64encode(private_key.sign(signed)).decode("ascii"),
        evidence_root=graph.root_sha256,
        artifact_binding_sha256=artifact_binding,
        policy_context=context,
    )
    signatures = list(result.extensions["proof"].get("signatures", []))
    signatures = [value for value in signatures if value.get("key_fingerprint") != envelope.key_fingerprint]
    signatures.append(envelope.to_dict())
    result.extensions["proof"]["signatures"] = sorted(signatures, key=lambda value: value["key_fingerprint"])
    return result


def verify_record_signatures(record: FigureRecord) -> list[ProofCheck]:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    proof = record.extensions.get("proof") or {}
    values = proof.get("signatures", []) if isinstance(proof, Mapping) else []
    if not values:
        return [ProofCheck("signature", "signature_valid", "unavailable", record.figure_id, "No signatures are present.")]
    try:
        graph = graph_from_record(record)
    except Exception as exc:
        return [ProofCheck("signature-root", "signature_valid", "fail", record.figure_id, str(exc))]
    checks: list[ProofCheck] = []
    seen: set[str] = set()
    for index, value in enumerate(values):
        try:
            envelope = SignatureEnvelope.from_dict(value)
            if envelope.schema != SIGNATURE_SCHEMA or envelope.algorithm != "Ed25519":
                raise ValueError("unsupported signature envelope")
            public_bytes = base64.b64decode(envelope.public_key, validate=True)
            fingerprint = public_key_fingerprint(public_bytes)
            if fingerprint != envelope.key_fingerprint:
                raise ValueError("public key fingerprint does not match envelope")
            if fingerprint in seen:
                raise ValueError("duplicate signer envelope")
            seen.add(fingerprint)
            if envelope.evidence_root != graph.root_sha256:
                raise ValueError("signature references a different evidence root")
            if envelope.artifact_binding_sha256 != _artifact_binding(record):
                raise ValueError("signature references a different carrier visual binding")
            public_key = Ed25519PublicKey.from_public_bytes(public_bytes)
            public_key.verify(
                base64.b64decode(envelope.signature, validate=True),
                signature_input(
                    figure_id=record.figure_id, record_schema=record.schema,
                    root_sha256=graph.root_sha256, policy_context=envelope.policy_context,
                    artifact_binding_sha256=envelope.artifact_binding_sha256,
                ),
            )
            checks.append(ProofCheck(f"signature:{fingerprint}", "signature_valid", "pass", fingerprint, "Ed25519 signature is mathematically valid."))
        except (ValueError, InvalidSignature, TypeError) as exc:
            checks.append(ProofCheck(f"signature:{index}", "signature_valid", "fail", message=str(exc) or "invalid Ed25519 signature"))
    return checks


__all__ = ["SIGNATURE_SCHEMA", "SignatureEnvelope", "sign_record", "verify_record_signatures"]
