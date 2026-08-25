"""Signed attestations over deterministic verification-report hashes."""

from __future__ import annotations

from typing import Any, Mapping

from ..schema import FigureRecord, deterministic_json, sha256_bytes
from ..verification import ProofVerificationReport
from .signatures import sign_record


def attest_report(
    record: FigureRecord,
    report: ProofVerificationReport | Mapping[str, Any],
    *,
    private_key_path: str,
    password: str | bytes,
) -> FigureRecord:
    value = report.to_dict() if isinstance(report, ProofVerificationReport) else dict(report)
    report_sha256 = sha256_bytes(deterministic_json(value).encode("utf-8"))
    return sign_record(
        record,
        private_key_path=private_key_path,
        password=password,
        policy_context={
            "type": "verification_attestation",
            "verification_report_sha256": report_sha256,
            "meanings": value.get("meanings", {}),
        },
    )


__all__ = ["attest_report"]
