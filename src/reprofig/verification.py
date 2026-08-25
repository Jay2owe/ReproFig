"""Deterministic proof checks and honest, separate verification meanings."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence

from .artifacts import extract_records, validate_artifact
from .evidence import graph_from_record
from .schema import FigureRecord, deterministic_json

CHECK_STATUSES = frozenset({"pass", "fail", "unavailable", "inaccessible", "unsupported", "not_requested"})
VERIFICATION_MEANINGS = (
    "display_verified",
    "internally_consistent",
    "reproduced",
    "independently_verified",
    "source_linked",
    "signature_valid",
    "signer_trusted",
    "attested",
)


@dataclass
class ProofCheck:
    check_id: str
    meaning: str
    status: str
    subject_id: str | None = None
    message: str = ""
    expected: Any = None
    actual: Any = None
    tolerance: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.status not in CHECK_STATUSES:
            raise ValueError(f"unknown proof-check status {self.status!r}")
        if self.meaning not in VERIFICATION_MEANINGS:
            raise ValueError(f"unknown verification meaning {self.meaning!r}")

    def to_dict(self) -> dict[str, Any]:
        value = {
            "check_id": self.check_id,
            "meaning": self.meaning,
            "status": self.status,
            "message": self.message,
        }
        for name in ("subject_id", "expected", "actual"):
            item = getattr(self, name)
            if item is not None:
                value[name] = item
        if self.tolerance:
            value["tolerance"] = dict(self.tolerance)
        return value


@dataclass
class ProofVerificationReport:
    path: str | None = None
    checks: list[ProofCheck] = field(default_factory=list)
    required: list[str] = field(default_factory=list)
    integrity: dict[str, Any] | None = None

    def status_for(self, meaning: str) -> str:
        statuses = [check.status for check in self.checks if check.meaning == meaning]
        if not statuses:
            return "not_requested"
        if meaning in {"signer_trusted", "attested"} and "pass" in statuses:
            return "pass"
        for status in ("fail", "inaccessible", "unsupported", "unavailable", "not_requested"):
            if status in statuses:
                return status
        return "pass"

    @property
    def meanings(self) -> dict[str, str]:
        return {meaning: self.status_for(meaning) for meaning in VERIFICATION_MEANINGS}

    @property
    def valid(self) -> bool:
        if self.integrity is not None and not self.integrity.get("valid", False):
            return False
        return all(self.status_for(meaning) == "pass" for meaning in self.required)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "valid": self.valid,
            "required": sorted(self.required),
            "meanings": self.meanings,
            "checks": [check.to_dict() for check in sorted(self.checks, key=lambda value: value.check_id)],
            "integrity": self.integrity,
        }

    def to_json(self, *, indent: int | None = None) -> str:
        return deterministic_json(self.to_dict(), indent=indent)


def verify_record_proof(
    record: FigureRecord,
    *,
    requested: Sequence[str] = (),
    source_tables: Mapping[str, Any] | None = None,
    decryption: Mapping[str, Any] | None = None,
    trust_store: str | os.PathLike[str] | None = None,
) -> list[ProofCheck]:
    requested_set = set(requested)
    checks: list[ProofCheck] = []
    working_record = record
    if decryption:
        try:
            from .crypto.encryption import decrypt_record

            working_record = decrypt_record(record, **dict(decryption))
        except PermissionError as exc:
            checks.append(ProofCheck(
                "decryption", "internally_consistent", "inaccessible",
                record.figure_id, str(exc),
            ))
        except ImportError:
            checks.append(ProofCheck(
                "decryption", "internally_consistent", "unsupported",
                record.figure_id, "Cryptographic decryption support is unavailable.",
            ))
        except Exception as exc:
            checks.append(ProofCheck(
                "decryption", "internally_consistent", "inaccessible",
                record.figure_id, f"Protected evidence could not be decrypted: {type(exc).__name__}.",
            ))
    try:
        graph = graph_from_record(record)
        checks.append(ProofCheck(
            "evidence-root", "internally_consistent", "pass", record.figure_id,
            "Canonical evidence graph and root agree.", actual=graph.root_sha256,
        ))
    except Exception as exc:
        checks.append(ProofCheck(
            "evidence-root", "internally_consistent", "fail", record.figure_id, str(exc)
        ))
        return checks

    proof = record.extensions.get("proof")
    has_proof = isinstance(proof, Mapping) and bool(proof.get("sections"))
    if "source_linked" in requested_set:
        try:
            from .transformations import verify_record_transformations
            encrypted_transformations = any(
                section.encrypted and section.kind == "transformation_specification"
                for section in graph.sections
            )
            if encrypted_transformations and not decryption:
                checks.append(ProofCheck(
                    "source-reconstruction", "source_linked", "inaccessible",
                    record.figure_id, "Transformation specification is encrypted.",
                ))
            else:
                checks.extend(verify_record_transformations(
                    working_record, supplied_tables=source_tables or {}
                ))
        except ImportError:
            checks.append(ProofCheck("source-reconstruction", "source_linked", "unsupported", message="Transformation verifier is unavailable."))
    elif not has_proof:
        checks.append(ProofCheck("source-reconstruction", "source_linked", "unavailable", message="Legacy record has no declared source transformation graph."))

    if "independently_verified" in requested_set or "reproduced" in requested_set:
        try:
            from .stats.engine import verify_record_statistics
            encrypted_statistics = any(
                section.encrypted and section.kind == "statistical_specification"
                for section in graph.sections
            )
            if encrypted_statistics and not decryption:
                for meaning in requested_set & {"reproduced", "independently_verified"}:
                    checks.append(ProofCheck(
                        "statistics", meaning, "inaccessible", record.figure_id,
                        "Statistical specification is encrypted.",
                    ))
            else:
                checks.extend(verify_record_statistics(working_record))
        except ImportError:
            checks.append(ProofCheck("statistics", "independently_verified", "unsupported", message="Independent statistics extra is unavailable."))

    if "display_verified" in requested_set:
        checks.append(ProofCheck(
            "display-route", "display_verified", "unavailable",
            message="Display verification requires the carrier path and is run by verify_artifact.",
        ))

    signatures = proof.get("signatures", []) if isinstance(proof, Mapping) else []
    if "signature_valid" in requested_set or "signer_trusted" in requested_set:
        if not signatures:
            checks.append(ProofCheck("signature", "signature_valid", "unavailable", message="No signature envelope is present."))
        else:
            try:
                from .crypto.signatures import verify_record_signatures
                checks.extend(verify_record_signatures(record))
            except ImportError:
                checks.append(ProofCheck("signature", "signature_valid", "unsupported", message="Cryptography extra is unavailable."))
        if "signer_trusted" in requested_set:
            if trust_store is None:
                checks.append(ProofCheck("trust", "signer_trusted", "unavailable", message="No trust store was supplied."))
            else:
                try:
                    from .crypto.trust import evaluate_record_trust
                    checks.extend(evaluate_record_trust(record, trust_store))
                except ImportError:
                    checks.append(ProofCheck("trust", "signer_trusted", "unsupported", message="Trust support is unavailable."))
    if "attested" in requested_set:
        if not signatures:
            checks.append(ProofCheck(
                "attestation", "attested", "unavailable", record.figure_id,
                "No signed verification attestation is present.",
            ))
        else:
            try:
                from .crypto.signatures import verify_record_signatures

                valid = {
                    check.subject_id
                    for check in verify_record_signatures(record)
                    if check.status == "pass" and check.subject_id
                }
                found = False
                for signature in signatures:
                    context = signature.get("policy_context") or {}
                    if context.get("type") != "verification_attestation":
                        continue
                    found = True
                    fingerprint = str(signature.get("key_fingerprint", ""))
                    report_hash = str(context.get("verification_report_sha256", ""))
                    status = (
                        "pass"
                        if fingerprint in valid
                        and len(report_hash) == 64
                        and all(character in "0123456789abcdef" for character in report_hash)
                        else "fail"
                    )
                    checks.append(ProofCheck(
                        f"attestation:{fingerprint}", "attested", status,
                        fingerprint,
                        "A valid signature binds the declared verification-report hash."
                        if status == "pass"
                        else "Verification attestation signature or report hash is invalid.",
                        actual=report_hash,
                    ))
                if not found:
                    checks.append(ProofCheck(
                        "attestation", "attested", "unavailable", record.figure_id,
                        "Signatures are present but none is a verification attestation.",
                    ))
            except ImportError:
                checks.append(ProofCheck(
                    "attestation", "attested", "unsupported", record.figure_id,
                    "Cryptographic attestation support is unavailable.",
                ))
    return checks


def verify_artifact(
    path: str | os.PathLike[str],
    *,
    required: Sequence[str] = (),
    source_tables: Mapping[str, Any] | None = None,
    decryption: Mapping[str, Any] | None = None,
    trust_store: str | os.PathLike[str] | None = None,
) -> ProofVerificationReport:
    required_values = [str(value) for value in required]
    unknown = sorted(set(required_values) - set(VERIFICATION_MEANINGS))
    if unknown:
        raise ValueError("unknown required verification meanings: " + ", ".join(unknown))
    integrity = validate_artifact(path)
    report = ProofVerificationReport(
        path=str(Path(path)), required=required_values, integrity=integrity.to_dict()
    )
    if not integrity.valid:
        report.checks.append(ProofCheck("carrier-integrity", "internally_consistent", "fail", message="Carrier integrity validation failed."))
        return report
    records = extract_records(path)
    for record in records:
        report.checks.extend(
            verify_record_proof(
                record,
                requested=required_values,
                source_tables=source_tables,
                decryption=decryption,
                trust_store=trust_store,
            )
        )
    if "display_verified" in required_values:
        report.checks = [check for check in report.checks if check.check_id != "display-route"]
        try:
            suffix = Path(path).suffix.lower()
            display_records = records
            if decryption:
                from .crypto.encryption import decrypt_record

                display_records = [
                    decrypt_record(record, **dict(decryption)) for record in records
                ]
            if suffix == ".svg":
                from .render.svg_verify import verify_svg
                for record in display_records:
                    report.checks.extend(verify_svg(path, record))
            else:
                from .render.raster_verify import verify_raster_carrier
                for record in display_records:
                    report.checks.extend(verify_raster_carrier(path, record))
        except ImportError:
            report.checks.append(ProofCheck("display", "display_verified", "unsupported", message="Visual-verification dependencies are unavailable."))
    return report


__all__ = [
    "CHECK_STATUSES",
    "VERIFICATION_MEANINGS",
    "ProofCheck",
    "ProofVerificationReport",
    "verify_artifact",
    "verify_record_proof",
]
