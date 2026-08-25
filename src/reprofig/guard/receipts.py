"""Deterministic promotion receipts."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from ..schema import deterministic_json, json_safe, sha256_bytes


@dataclass(frozen=True)
class PromotionReceipt:
    candidate_sha256: str
    final_sha256: str
    policy_sha256: str
    verification_sha256: str
    destination_name: str
    schema: str = "reprofig-promotion-receipt/1"

    def to_dict(self) -> dict[str, Any]:
        return dict(vars(self))

    def fingerprint(self) -> str:
        return sha256_bytes(deterministic_json(self.to_dict()).encode("utf-8"))


__all__ = ["PromotionReceipt"]
