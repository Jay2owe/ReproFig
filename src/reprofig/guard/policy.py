"""Typed, inert-until-invoked figure-output policy."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ..schema import json_safe
from ..verification import VERIFICATION_MEANINGS, normalize_verification_meaning


@dataclass
class OutputPolicy:
    permitted_formats: list[str] = field(default_factory=lambda: ["svg", "pdf", "png", "jpeg", "tiff", "webp"])
    profile: str = "master"
    required_meanings: list[str] = field(default_factory=list)
    destination: str | None = None
    signing_key_path: str | None = None
    signing_password_env: str | None = None
    encrypt_section_ids: list[str] = field(default_factory=list)
    encryption_password_env: str | None = None
    trust_store: str | None = None
    quarantine_failed: bool = False
    strict: bool = True
    schema: str = "reprofig-output-policy/1"

    def __post_init__(self) -> None:
        self.profile = self.profile.replace("-", "_")
        self.required_meanings = [
            normalize_verification_meaning(value) for value in self.required_meanings
        ]
        unknown = sorted(set(self.required_meanings) - set(VERIFICATION_MEANINGS))
        if unknown:
            raise ValueError("unknown required verification meanings: " + ", ".join(unknown))

    def to_dict(self) -> dict[str, Any]:
        return {key: json_safe(value) for key, value in vars(self).items() if value not in (None, [], False)}

    def to_artifact_policy(self) -> dict[str, Any]:
        """Translate guard field names to the shared atomic save contract."""

        value = self.to_dict()
        value["encrypt_sections"] = value.pop("encrypt_section_ids", [])
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "OutputPolicy":
        if value.get("schema") not in (None, "reprofig-output-policy/1"):
            raise ValueError("unsupported output-policy schema")
        return cls(**{key: item for key, item in value.items() if key in cls.__dataclass_fields__})

    @classmethod
    def from_json(cls, path: str | Path) -> "OutputPolicy":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


__all__ = ["OutputPolicy"]
