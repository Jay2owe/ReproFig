"""Explicit opt-in proof policy application for already rendered artifacts."""

from __future__ import annotations

import os
import json
from pathlib import Path
from typing import Any, Mapping

from .artifacts import embed_file, extract_record
from .schema import FigureRecord
from .verification import ProofVerificationReport, verify_artifact


def apply_artifact_policy(
    path: str | os.PathLike[str],
    policy: Mapping[str, Any] | None,
    *,
    record: FigureRecord | None = None,
    reuse_encrypted_sections: bool = False,
) -> tuple[FigureRecord, ProofVerificationReport]:
    """Encrypt, sign and verify one artifact from non-secret policy references.

    Passwords are resolved only from explicitly named environment variables.
    An empty policy performs integrity verification and otherwise changes nothing.
    """

    target = Path(path)
    values = dict(policy or {})
    final = FigureRecord.from_dict((record or extract_record(target)).to_dict())
    section_ids = [
        str(value)
        for value in values.get("encrypt_sections", values.get("encrypted_sections", []))
    ]
    if section_ids:
        from .evidence import graph_from_record

        graph = graph_from_record(final)
        already_encrypted = {
            str(section.section_id) for section in graph.sections if section.encrypted
        }
        reused = sorted(set(section_ids) & already_encrypted)
        if reused and not reuse_encrypted_sections:
            raise ValueError(
                "evidence sections are already encrypted; explicit reuse is required: "
                + ", ".join(reused)
            )
        section_ids = [value for value in section_ids if value not in already_encrypted]
    if section_ids:
        environment_name = values.get("encryption_password_env")
        password = os.environ.get(str(environment_name or "")) if environment_name else None
        recipients = None
        recipient_file = values.get("recipient_file")
        if recipient_file:
            parsed = json.loads(Path(recipient_file).read_text(encoding="utf-8"))
            if not isinstance(parsed, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in parsed.items()
            ):
                raise ValueError("recipient_file must contain a JSON object of name to public key")
            recipients = parsed
        if not password and not recipients:
            raise ValueError(
                "selective encryption requires a named password environment variable or recipient_file"
            )
        from .crypto.encryption import encrypt_sections

        final = encrypt_sections(
            final, section_ids, password=password, recipients=recipients
        )

    signing_key = values.get("signing_key_path")
    if signing_key:
        environment_name = values.get("signing_password_env")
        password = os.environ.get(str(environment_name or ""))
        if not environment_name or not password:
            raise ValueError(
                "signing requires signing_password_env naming a non-empty environment variable"
            )
        from .crypto.signatures import sign_record

        final = sign_record(
            final,
            private_key_path=str(signing_key),
            password=password,
            policy_context={
                "profile": final.distribution_profile,
                "required_meanings": sorted(
                    str(value)
                    for value in values.get(
                        "required_meanings", values.get("required_grades", [])
                    )
                ),
            },
        )

    if section_ids or signing_key:
        embed_file(target, final, output_path=target)
    required = [
        str(value)
        for value in values.get("required_meanings", values.get("required_grades", []))
    ]
    report = verify_artifact(
        target,
        required=required,
        trust_store=values.get("trust_store", values.get("trust_policy_path")),
    )
    if required and not report.valid:
        failed = [
            f"{meaning}={report.meanings[meaning]}"
            for meaning in required
            if report.meanings.get(meaning) != "pass"
        ]
        raise RuntimeError("artifact failed required ReproFig proof policy: " + ", ".join(failed))
    return final, report


__all__ = ["apply_artifact_policy"]
