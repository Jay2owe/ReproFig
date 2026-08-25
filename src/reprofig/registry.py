"""Signed, privacy-safe local and explicit HTTP identity registries."""

from __future__ import annotations

import base64
import json
import os
import tempfile
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import urlparse

from .crypto.keys import load_signing_private_key, public_key_fingerprint, signing_public_bytes
from .render.fingerprint import visual_fingerprint
from .schema import deterministic_json, sha256_bytes
from .sources import file_sha256

REGISTRY_SCHEMA = "reprofig-identity-registry/1"
ENTRY_SCHEMA = "reprofig-identity-entry/1"
MAX_REGISTRY_BYTES = 20 * 1024 * 1024


@dataclass
class RegistryEntry:
    figure_id: str
    evidence_root: str
    profile: str
    carrier_hashes: dict[str, str]
    visual: dict[str, str]
    recovery_locations: list[str]
    signer_fingerprint: str | None = None
    public_key: str | None = None
    signature: str | None = None
    supersedes: str | None = None
    revoked: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)
    schema: str = ENTRY_SCHEMA

    def unsigned_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema, "figure_id": self.figure_id, "evidence_root": self.evidence_root,
            "profile": self.profile, "carrier_hashes": dict(sorted(self.carrier_hashes.items())),
            "visual": dict(sorted(self.visual.items())), "recovery_locations": sorted(self.recovery_locations),
            "supersedes": self.supersedes, "revoked": self.revoked, "metadata": self.metadata,
        }

    def to_dict(self) -> dict[str, Any]:
        return {**self.unsigned_dict(), "signer_fingerprint": self.signer_fingerprint, "public_key": self.public_key, "signature": self.signature}

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "RegistryEntry":
        if value.get("schema") != ENTRY_SCHEMA:
            raise ValueError("unsupported registry-entry schema")
        return cls(
            figure_id=str(value.get("figure_id", "")), evidence_root=str(value.get("evidence_root", "")),
            profile=str(value.get("profile", "public")), carrier_hashes=dict(value.get("carrier_hashes") or {}),
            visual=dict(value.get("visual") or {}), recovery_locations=[str(item) for item in value.get("recovery_locations", [])],
            signer_fingerprint=value.get("signer_fingerprint"), public_key=value.get("public_key"), signature=value.get("signature"),
            supersedes=value.get("supersedes"), revoked=bool(value.get("revoked", False)), metadata=dict(value.get("metadata") or {}),
        )

    def verify_signature(self) -> bool:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
        if not self.public_key or not self.signature or not self.signer_fingerprint:
            return False
        try:
            public = base64.b64decode(self.public_key, validate=True)
            if public_key_fingerprint(public) != self.signer_fingerprint:
                return False
            Ed25519PublicKey.from_public_bytes(public).verify(
                base64.b64decode(self.signature, validate=True),
                b"ReproFig registry entry v1\x00" + deterministic_json(self.unsigned_dict()).encode("utf-8"),
            )
        except (InvalidSignature, ValueError, TypeError):
            return False
        return True


def sign_registry_entry(entry: RegistryEntry, *, private_key_path: str, password: str | bytes) -> RegistryEntry:
    key = load_signing_private_key(private_key_path, password=password)
    public = signing_public_bytes(key)
    entry.signer_fingerprint = public_key_fingerprint(public)
    entry.public_key = base64.b64encode(public).decode("ascii")
    entry.signature = base64.b64encode(key.sign(b"ReproFig registry entry v1\x00" + deterministic_json(entry.unsigned_dict()).encode("utf-8"))).decode("ascii")
    return entry


def registry_entry_for_artifact(
    path: str | os.PathLike[str], *, figure_id: str, evidence_root: str,
    profile: str, recovery_locations: list[str], carrier_name: str | None = None,
) -> RegistryEntry:
    source = Path(path)
    if profile not in {"public", "minimal_public"}:
        raise ValueError("identity-registry entries may reference only public profiles")
    for location in recovery_locations:
        parsed = urlparse(location)
        if parsed.scheme not in {"", "https"}:
            raise ValueError("recovery locations must be HTTPS URIs or relative paths")
        if not parsed.scheme:
            relative = Path(location)
            if relative.is_absolute() or ".." in relative.parts:
                raise ValueError(
                    "registry relative recovery locations must stay below the registry folder"
                )
    return RegistryEntry(
        figure_id=figure_id, evidence_root=evidence_root, profile=profile,
        carrier_hashes={carrier_name or source.name: file_sha256(source)},
        visual=visual_fingerprint(source), recovery_locations=recovery_locations,
    )


@dataclass
class LocalRegistry:
    entries: list[RegistryEntry] = field(default_factory=list)
    source_path: Path | None = field(default=None, repr=False, compare=False)

    @classmethod
    def load(cls, path: str | os.PathLike[str]) -> "LocalRegistry":
        target = Path(path)
        if not target.exists():
            return cls(source_path=target)
        parsed = json.loads(target.read_text(encoding="utf-8"))
        if parsed.get("schema") != REGISTRY_SCHEMA:
            raise ValueError("unsupported identity-registry schema")
        return cls(
            [RegistryEntry.from_dict(item) for item in parsed.get("entries", [])],
            source_path=target,
        )

    def save(self, path: str | os.PathLike[str]) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".tmp", dir=target.parent)
        os.close(handle)
        candidate = Path(name)
        try:
            candidate.write_text(deterministic_json({"schema": REGISTRY_SCHEMA, "entries": [item.to_dict() for item in sorted(self.entries, key=lambda value: (value.figure_id, value.evidence_root))]}, indent=2) + "\n", encoding="utf-8")
            os.replace(candidate, target)
        finally:
            try:
                candidate.unlink()
            except OSError:
                pass
        self.source_path = target
        return target

    def add(self, entry: RegistryEntry) -> None:
        if not entry.verify_signature():
            raise ValueError("registry entry signature is not valid")
        self.entries = [value for value in self.entries if not (value.figure_id == entry.figure_id and value.evidence_root == entry.evidence_root)]
        self.entries.append(entry)

    def resolve(
        self,
        path: str | os.PathLike[str],
        *,
        trust_store: str | os.PathLike[str] | Any,
        scope: str = "registry",
    ) -> tuple[RegistryEntry, str] | None:
        from .crypto.trust import TrustStore

        trust = (
            trust_store
            if isinstance(trust_store, TrustStore)
            else TrustStore.load(trust_store)
        )
        trusted = {
            value.fingerprint
            for value in trust.entries
            if value.active(scope=scope)
        }

        def acceptable(entry: RegistryEntry) -> bool:
            return (
                not entry.revoked
                and entry.verify_signature()
                and entry.signer_fingerprint in trusted
            )

        exact = file_sha256(path)
        for entry in self.entries:
            if acceptable(entry) and exact in entry.carrier_hashes.values():
                return entry, "exact_carrier_hash"
        visual = visual_fingerprint(path)
        for entry in self.entries:
            if acceptable(entry) and entry.visual == visual:
                return entry, "visual_fingerprint_candidate"
        return None


def fetch_registry(url: str, *, timeout: float = 10.0) -> LocalRegistry:
    if urlparse(url).scheme != "https":
        raise ValueError("remote identity registries require HTTPS")
    with urllib.request.urlopen(url, timeout=timeout) as response:
        raw = response.read(MAX_REGISTRY_BYTES + 1)
    if len(raw) > MAX_REGISTRY_BYTES:
        raise ValueError("remote registry exceeds ReproFig size limit")
    parsed = json.loads(raw)
    if parsed.get("schema") != REGISTRY_SCHEMA:
        raise ValueError("unsupported remote registry schema")
    return LocalRegistry([RegistryEntry.from_dict(item) for item in parsed.get("entries", [])])


__all__ = [
    "ENTRY_SCHEMA", "REGISTRY_SCHEMA", "LocalRegistry", "RegistryEntry", "fetch_registry",
    "registry_entry_for_artifact", "sign_registry_entry",
]
