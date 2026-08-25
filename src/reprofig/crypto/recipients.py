"""Password and named-recipient content-key envelopes."""

from __future__ import annotations

import base64
import os
from typing import Any, Mapping

from ..schema import deterministic_json, sha256_bytes
from .keys import public_key_fingerprint, recipient_public_bytes

MAX_RECIPIENTS = 100
MAX_ARGON2_MEMORY_KIB = 262_144


def _b64(value: bytes) -> str:
    return base64.b64encode(value).decode("ascii")


def _decode(value: str) -> bytes:
    return base64.b64decode(value, validate=True)


def wrap_with_password(
    content_key: bytes,
    password: str | bytes,
    *,
    aad: bytes,
    memory_cost_kib: int = 65_536,
    time_cost: int = 3,
    parallelism: int = 1,
) -> dict[str, Any]:
    if not (8_192 <= memory_cost_kib <= MAX_ARGON2_MEMORY_KIB and 1 <= time_cost <= 10 and 1 <= parallelism <= 16):
        raise ValueError("Argon2id parameters exceed ReproFig limits")
    from argon2.low_level import Type, hash_secret_raw
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    secret = password.encode("utf-8") if isinstance(password, str) else password
    if not secret:
        raise ValueError("password must not be empty")
    salt = os.urandom(16)
    wrapping_key = hash_secret_raw(secret, salt, time_cost, memory_cost_kib, parallelism, 32, Type.ID)
    nonce = os.urandom(12)
    wrapped = AESGCM(wrapping_key).encrypt(nonce, content_key, aad)
    return {
        "type": "password-argon2id-aes256gcm/v1", "salt": _b64(salt), "nonce": _b64(nonce),
        "wrapped_key": _b64(wrapped), "memory_cost_kib": memory_cost_kib,
        "time_cost": time_cost, "parallelism": parallelism,
    }


def unwrap_with_password(envelope: Mapping[str, Any], password: str | bytes, *, aad: bytes) -> bytes:
    from argon2.low_level import Type, hash_secret_raw
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    if envelope.get("type") != "password-argon2id-aes256gcm/v1":
        raise ValueError("unsupported password envelope")
    memory = int(envelope["memory_cost_kib"])
    time = int(envelope["time_cost"])
    parallel = int(envelope["parallelism"])
    if not (8_192 <= memory <= MAX_ARGON2_MEMORY_KIB and 1 <= time <= 10 and 1 <= parallel <= 16):
        raise ValueError("Argon2id envelope parameters exceed ReproFig limits")
    salt = _decode(str(envelope["salt"]))
    nonce = _decode(str(envelope["nonce"]))
    wrapped_key = _decode(str(envelope["wrapped_key"]))
    if len(salt) != 16 or len(nonce) != 12 or len(wrapped_key) != 48:
        raise ValueError("password envelope has invalid field lengths")
    secret = password.encode("utf-8") if isinstance(password, str) else password
    key = hash_secret_raw(secret, salt, time, memory, parallel, 32, Type.ID)
    return AESGCM(key).decrypt(nonce, wrapped_key, aad)


def wrap_for_recipients(content_key: bytes, recipients: Mapping[str, str], *, aad: bytes) -> list[dict[str, Any]]:
    if len(recipients) > MAX_RECIPIENTS:
        raise ValueError("recipient count exceeds ReproFig limit")
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    values = []
    for label, encoded_public in sorted(recipients.items()):
        public_bytes = _decode(encoded_public)
        public = X25519PublicKey.from_public_bytes(public_bytes)
        ephemeral = X25519PrivateKey.generate()
        shared = ephemeral.exchange(public)
        wrapping_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"ReproFig recipient wrap v1").derive(shared)
        nonce = os.urandom(12)
        values.append({
            "type": "x25519-hkdf-aes256gcm/v1", "label": str(label),
            "recipient_fingerprint": public_key_fingerprint(public_bytes),
            "ephemeral_public_key": _b64(recipient_public_bytes(ephemeral)),
            "nonce": _b64(nonce), "wrapped_key": _b64(AESGCM(wrapping_key).encrypt(nonce, content_key, aad)),
        })
    return values


def unwrap_for_recipient(envelopes: list[Mapping[str, Any]], private_key: Any, *, aad: bytes) -> bytes:
    from cryptography.hazmat.primitives import hashes
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PublicKey
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    from cryptography.hazmat.primitives.kdf.hkdf import HKDF
    if len(envelopes) > MAX_RECIPIENTS:
        raise ValueError("recipient count exceeds ReproFig limit")
    fingerprint = public_key_fingerprint(recipient_public_bytes(private_key))
    for envelope in envelopes:
        if envelope.get("recipient_fingerprint") != fingerprint:
            continue
        if envelope.get("type") != "x25519-hkdf-aes256gcm/v1":
            raise ValueError("unsupported recipient envelope")
        ephemeral_bytes = _decode(str(envelope["ephemeral_public_key"]))
        nonce = _decode(str(envelope["nonce"]))
        wrapped_key = _decode(str(envelope["wrapped_key"]))
        if len(ephemeral_bytes) != 32 or len(nonce) != 12 or len(wrapped_key) != 48:
            raise ValueError("recipient envelope has invalid field lengths")
        ephemeral = X25519PublicKey.from_public_bytes(ephemeral_bytes)
        shared = private_key.exchange(ephemeral)
        wrapping_key = HKDF(algorithm=hashes.SHA256(), length=32, salt=None, info=b"ReproFig recipient wrap v1").derive(shared)
        return AESGCM(wrapping_key).decrypt(nonce, wrapped_key, aad)
    raise ValueError("no recipient envelope matches the supplied private key")


__all__ = ["unwrap_for_recipient", "unwrap_with_password", "wrap_for_recipients", "wrap_with_password"]
