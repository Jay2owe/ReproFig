"""Offline trust stores and signer lifecycle policy evaluation."""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..schema import FigureRecord, deterministic_json
from ..verification import ProofCheck

TRUST_SCHEMA = "reprofig-trust-store/1"


def _time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


@dataclass
class TrustEntry:
    fingerprint: str
    label: str
    scopes: list[str] = field(default_factory=lambda: ["*"])
    activated_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    replacement_fingerprint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {key: value for key, value in vars(self).items() if value not in (None, {}, [])}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "TrustEntry":
        return cls(
            fingerprint=str(value.get("fingerprint", "")), label=str(value.get("label", "")),
            scopes=[str(item) for item in value.get("scopes", ["*"])],
            activated_at=value.get("activated_at"), expires_at=value.get("expires_at"),
            revoked_at=value.get("revoked_at"), replacement_fingerprint=value.get("replacement_fingerprint"),
            metadata=dict(value.get("metadata") or {}),
        )

    def active(self, *, scope: str, at: datetime | None = None) -> bool:
        at = at or datetime.now(timezone.utc)
        activated = _time(self.activated_at)
        expires = _time(self.expires_at)
        revoked = _time(self.revoked_at)
        return (
            ("*" in self.scopes or scope in self.scopes)
            and (activated is None or at >= activated)
            and (expires is None or at < expires)
            and (revoked is None or at < revoked)
        )


@dataclass
class TrustPolicy:
    required_scopes: list[str] = field(default_factory=list)
    minimum_trusted_signatures: int = 1
    required_fingerprints: list[str] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.required_scopes = sorted({str(value) for value in self.required_scopes})
        self.required_fingerprints = sorted(
            {str(value) for value in self.required_fingerprints}
        )
        if self.minimum_trusted_signatures < 1:
            raise ValueError("minimum_trusted_signatures must be at least one")

    def to_dict(self) -> dict[str, Any]:
        return {
            "required_scopes": self.required_scopes,
            "minimum_trusted_signatures": self.minimum_trusted_signatures,
            "required_fingerprints": self.required_fingerprints,
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any] | None) -> "TrustPolicy":
        value = value or {}
        return cls(
            required_scopes=[str(item) for item in value.get("required_scopes", [])],
            minimum_trusted_signatures=int(
                value.get("minimum_trusted_signatures", 1)
            ),
            required_fingerprints=[
                str(item) for item in value.get("required_fingerprints", [])
            ],
        )


@dataclass
class TrustStore:
    entries: list[TrustEntry] = field(default_factory=list)
    policy: TrustPolicy = field(default_factory=TrustPolicy)
    schema: str = TRUST_SCHEMA

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "policy": self.policy.to_dict(),
            "entries": [
                item.to_dict()
                for item in sorted(self.entries, key=lambda value: value.fingerprint)
            ],
        }

    def save(self, path: str | os.PathLike[str], *, overwrite: bool = True) -> Path:
        target = Path(path)
        if target.exists() and not overwrite:
            raise FileExistsError(target)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        os.close(handle)
        candidate = Path(name)
        try:
            candidate.write_text(deterministic_json(self.to_dict(), indent=2) + "\n", encoding="utf-8")
            os.replace(candidate, target)
        finally:
            try:
                candidate.unlink()
            except OSError:
                pass
        return target

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "TrustStore":
        parsed = json.loads(Path(path).read_text(encoding="utf-8"))
        if parsed.get("schema") != TRUST_SCHEMA:
            raise ValueError("unsupported ReproFig trust-store schema")
        return cls(
            [TrustEntry.from_dict(item) for item in parsed.get("entries", [])],
            TrustPolicy.from_dict(parsed.get("policy")),
        )

    def add(self, entry: TrustEntry) -> None:
        self.entries = [item for item in self.entries if item.fingerprint != entry.fingerprint]
        self.entries.append(entry)

    def revoke(self, fingerprint: str, *, revoked_at: str, replacement_fingerprint: str | None = None) -> None:
        for entry in self.entries:
            if entry.fingerprint == fingerprint:
                entry.revoked_at = revoked_at
                entry.replacement_fingerprint = replacement_fingerprint
                return
        raise KeyError(fingerprint)

    def remove(self, fingerprint: str) -> None:
        retained = [item for item in self.entries if item.fingerprint != fingerprint]
        if len(retained) == len(self.entries):
            raise KeyError(fingerprint)
        self.entries = retained


def evaluate_record_trust(
    record: FigureRecord,
    store: str | os.PathLike[str] | TrustStore,
    *,
    scope: str = "figure",
) -> list[ProofCheck]:
    trust = store if isinstance(store, TrustStore) else TrustStore.load(store)
    from .signatures import verify_record_signatures

    proof = record.extensions.get("proof") or {}
    signatures = proof.get("signatures", []) if isinstance(proof, Mapping) else []
    if not signatures:
        return [ProofCheck("trust", "signer_trusted", "unavailable", record.figure_id, "No signer is present.")]
    signature_checks = verify_record_signatures(record)
    valid_fingerprints = {
        check.subject_id
        for check in signature_checks
        if check.status == "pass" and check.subject_id
    }
    checks: list[ProofCheck] = []
    by_fingerprint = {entry.fingerprint: entry for entry in trust.entries}
    required_scopes = trust.policy.required_scopes or [scope]
    trusted_fingerprints: set[str] = set()
    for signature in signatures:
        fingerprint = str(signature.get("key_fingerprint", ""))
        entry = by_fingerprint.get(fingerprint)
        scopes_ok = bool(entry) and all(
            entry.active(scope=required_scope) for required_scope in required_scopes
        )
        required_key_ok = (
            not trust.policy.required_fingerprints
            or fingerprint in trust.policy.required_fingerprints
        )
        status = (
            "pass"
            if fingerprint in valid_fingerprints and scopes_ok and required_key_ok
            else "fail"
        )
        if status == "pass":
            trusted_fingerprints.add(fingerprint)
        message = (
            f"Signer is trusted as {entry.label!r} for scopes {required_scopes!r}."
            if status == "pass"
            else "Signer is invalid, unknown, expired, revoked, out of scope or not required by policy."
        )
        checks.append(ProofCheck(f"trust:{fingerprint}", "signer_trusted", status, fingerprint, message))
    missing = sorted(set(trust.policy.required_fingerprints) - trusted_fingerprints)
    if missing or len(trusted_fingerprints) < trust.policy.minimum_trusted_signatures:
        checks.append(ProofCheck(
            "trust:policy",
            "signer_trusted",
            "fail",
            record.figure_id,
            "Trust policy minimum or required signer set was not satisfied.",
            expected={
                "minimum": trust.policy.minimum_trusted_signatures,
                "required_fingerprints": trust.policy.required_fingerprints,
            },
            actual={"trusted_fingerprints": sorted(trusted_fingerprints)},
        ))
    elif trusted_fingerprints:
        checks.append(ProofCheck(
            "trust:policy", "signer_trusted", "pass", record.figure_id,
            "Trust policy signer requirements are satisfied.",
        ))
    return checks


__all__ = [
    "TRUST_SCHEMA", "TrustEntry", "TrustPolicy", "TrustStore",
    "evaluate_record_trust",
]
