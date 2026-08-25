"""Separate verification and atomic promotion of candidate outputs."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any

from ..artifacts import validate_artifact
from ..carriers.registry import identify_format
from ..schema import deterministic_json, sha256_bytes
from ..schema import FigureRecord
from ..sources import file_sha256
from ..verification import verify_artifact
from .policy import OutputPolicy
from .receipts import PromotionReceipt
from .workspace import GuardWorkspace

MAX_CANDIDATE_BYTES = 2 * 1024 * 1024 * 1024


class OutputBroker:
    def __init__(
        self,
        workspace: GuardWorkspace,
        destination: str | os.PathLike[str],
        policy: OutputPolicy,
        *,
        mode: str = "advisory",
    ) -> None:
        if mode not in {"advisory", "hard"}:
            raise ValueError("broker mode must be advisory or hard")
        self.workspace = workspace
        self.destination = Path(destination).resolve()
        if policy.destination and Path(policy.destination).resolve() != self.destination:
            raise ValueError("broker destination disagrees with the output policy")
        self.destination.mkdir(parents=True, exist_ok=True)
        if self.destination.is_symlink():
            raise ValueError("controlled destination must not be a symlink")
        self.policy = policy
        self.mode = mode

    def promote(self, candidate: str | os.PathLike[str], *, name: str | None = None) -> PromotionReceipt:
        source = self.workspace.require_candidate(candidate)
        if source.stat().st_size > MAX_CANDIDATE_BYTES:
            raise ValueError("candidate exceeds broker byte limit")
        final_name = name or source.name
        if Path(final_name).name != final_name or final_name in {".", ".."}:
            raise ValueError("destination name must be one plain filename")
        target = (self.destination / final_name).resolve()
        if self.destination not in target.parents:
            raise ValueError("promotion target escapes controlled destination")
        before = file_sha256(source)
        carrier = identify_format(source)
        aliases = {"jpg": "jpeg", "tif": "tiff", "heic": "heif"}
        permitted = {aliases.get(value, value) for value in self.policy.permitted_formats}
        if aliases.get(carrier, carrier) not in permitted:
            raise RuntimeError(
                f"candidate format {carrier!r} is forbidden by ReproFig promotion policy"
            )
        integrity = validate_artifact(
            source,
            expected_profile=self.policy.profile,
            public_safety=self.policy.profile != "master",
        )
        if not integrity.valid:
            raise RuntimeError("candidate failed ReproFig carrier/profile policy")
        report = verify_artifact(source, required=self.policy.required_meanings, trust_store=self.policy.trust_store)
        if not report.valid:
            if self.policy.quarantine_failed:
                quarantine = self.workspace.quarantine / source.name
                os.replace(source, quarantine)
            raise RuntimeError("candidate failed ReproFig promotion policy")
        policy_sha = sha256_bytes(deterministic_json(self.policy.to_dict()).encode("utf-8"))
        report_sha = sha256_bytes(report.to_json().encode("utf-8"))
        handle, candidate_name = tempfile.mkstemp(prefix=f".{target.name}.", suffix=".candidate", dir=target.parent)
        os.close(handle)
        promotion = Path(candidate_name)
        try:
            shutil.copyfile(source, promotion, follow_symlinks=False)
            after = file_sha256(promotion)
            if before != after:
                raise RuntimeError("candidate changed during promotion")
            if self.destination.is_symlink() or self.destination.resolve() != self.destination:
                raise RuntimeError("controlled destination changed during promotion")
            os.replace(promotion, target)
        finally:
            try:
                promotion.unlink()
            except OSError:
                pass
        return PromotionReceipt(before, file_sha256(target), policy_sha, report_sha, final_name)

    def prepare_and_promote(
        self,
        candidate: str | os.PathLike[str],
        *,
        record_path: str | os.PathLike[str],
        semantic_bindings_path: str | os.PathLike[str] | None = None,
        name: str | None = None,
    ) -> PromotionReceipt:
        """Embed a language-neutral record, apply policy, then promote."""

        import json

        from ..artifacts import embed_file
        from ..evidence import refresh_evidence_graph
        from ..policy import apply_artifact_policy
        from ..render.reference import refresh_visual_reference
        from ..render.schema import RenderManifest

        source = self.workspace.require_candidate(candidate)
        record = FigureRecord.from_json(Path(record_path).read_text(encoding="utf-8"))
        if semantic_bindings_path:
            parsed = json.loads(
                Path(semantic_bindings_path).read_text(encoding="utf-8")
            )
            value = parsed.get("render_manifest", parsed) if isinstance(parsed, dict) else parsed
            manifest = RenderManifest.from_dict(value)
            record.extensions["render_manifest"] = manifest.to_dict()
            record = refresh_evidence_graph(record)
        embed_file(source, record, output_path=source)
        if "render_manifest" in record.extensions:
            record = refresh_visual_reference(source, record)
            embed_file(source, record, output_path=source)
        apply_artifact_policy(
            source,
            self.policy.to_artifact_policy(),
            record=record,
        )
        return self.promote(source, name=name)


def promote_candidate(
    candidate: str | os.PathLike[str],
    *,
    workspace: str | os.PathLike[str],
    destination: str | os.PathLike[str],
    policy: OutputPolicy,
    name: str | None = None,
) -> PromotionReceipt:
    return OutputBroker(GuardWorkspace.create(workspace), destination, policy).promote(candidate, name=name)


__all__ = ["OutputBroker", "promote_candidate"]
