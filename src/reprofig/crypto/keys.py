"""Ed25519 and X25519 key generation and protected serialization."""

from __future__ import annotations

import base64
import os
import tempfile
from pathlib import Path
from typing import Any

from ..schema import sha256_bytes


def public_key_fingerprint(public_bytes: bytes) -> str:
    return "sha256:" + sha256_bytes(public_bytes)


def _write_private_key(target: Path, data: bytes, *, overwrite: bool) -> Path:
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".key", dir=target.parent)
    candidate = Path(name)
    try:
        try:
            os.chmod(candidate, 0o600)
        except OSError:
            pass
        os.write(descriptor, data)
        os.close(descriptor)
        descriptor = -1
        os.replace(candidate, target)
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        try:
            candidate.unlink()
        except OSError:
            pass
    return target


def generate_signing_key(path: str | os.PathLike[str], *, password: str | bytes, overwrite: bool = False) -> Path:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    secret = password.encode("utf-8") if isinstance(password, str) else password
    if not secret:
        raise ValueError("private signing keys require a non-empty password")
    key = Ed25519PrivateKey.generate()
    data = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(secret),
    )
    return _write_private_key(target, data, overwrite=overwrite)


def load_signing_private_key(path: str | os.PathLike[str], *, password: str | bytes):
    from cryptography.hazmat.primitives import serialization
    secret = password.encode("utf-8") if isinstance(password, str) else password
    return serialization.load_pem_private_key(Path(path).read_bytes(), password=secret)


def signing_public_bytes(key: Any) -> bytes:
    from cryptography.hazmat.primitives import serialization
    public = key.public_key() if hasattr(key, "public_key") else key
    return public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


def encode_public_key(key: Any) -> str:
    return base64.b64encode(signing_public_bytes(key)).decode("ascii")


def generate_recipient_key(path: str | os.PathLike[str], *, password: str | bytes, overwrite: bool = False) -> Path:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey
    target = Path(path)
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    secret = password.encode("utf-8") if isinstance(password, str) else password
    if not secret:
        raise ValueError("private recipient keys require a non-empty password")
    key = X25519PrivateKey.generate()
    data = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
        serialization.BestAvailableEncryption(secret),
    )
    return _write_private_key(target, data, overwrite=overwrite)


def load_recipient_private_key(path: str | os.PathLike[str], *, password: str | bytes):
    from cryptography.hazmat.primitives import serialization
    secret = password.encode("utf-8") if isinstance(password, str) else password
    return serialization.load_pem_private_key(Path(path).read_bytes(), password=secret)


def recipient_public_bytes(key: Any) -> bytes:
    from cryptography.hazmat.primitives import serialization
    public = key.public_key() if hasattr(key, "public_key") else key
    return public.public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)


__all__ = [
    "encode_public_key", "generate_recipient_key", "generate_signing_key",
    "load_recipient_private_key", "load_signing_private_key", "public_key_fingerprint",
    "recipient_public_bytes", "signing_public_bytes",
]
