"""Atomic high-level publication-workbook interface."""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from ..validation import ValidationReport
from .collect import collect_publication
from .evidence import embed_publication_record, publication_record
from .profiles import prepare_record_for_workbook, public_statistic_record
from .statistics import import_statistics_ledger, reconcile_statistics
from .validation import validate_publication_workbook
from .writer import render_workbook
from .writer import data_sheet_map


@dataclass(frozen=True)
class PublicationWorkbookResult:
    path: Path
    publication_id: str
    evidence_sha256: str
    figure_count: int
    unique_table_count: int
    statistic_count: int
    statistics_coverage: str
    validation: ValidationReport
    proof: Mapping[str, Any] | None = None

    @property
    def valid(self) -> bool:
        return self.validation.valid

    def to_dict(self) -> dict[str, Any]:
        value = {
            "path": str(self.path),
            "publication_id": self.publication_id,
            "evidence_sha256": self.evidence_sha256,
            "figure_count": self.figure_count,
            "unique_table_count": self.unique_table_count,
            "statistic_count": self.statistic_count,
            "statistics_coverage": self.statistics_coverage,
            "valid": self.valid,
            "validation": self.validation.to_dict(),
        }
        if self.proof is not None:
            value["proof"] = dict(self.proof)
        return value


def build_publication_workbook(
    artifacts: str | os.PathLike[str] | Sequence[str | os.PathLike[str]],
    output_path: str | os.PathLike[str],
    *,
    profile: str = "master",
    publication_id: str | None = None,
    experiment_statistics: str | os.PathLike[str] | Sequence[Mapping[str, Any]] | None = None,
    declare_ledger_complete: bool = False,
    safe_columns: Mapping[str, Sequence[str]] | Sequence[str] | None = None,
    public_sources: Mapping[str, str] | None = None,
    protected_sections: Sequence[str] = (),
    encryption_password: str | bytes | None = None,
    encryption_recipients: Mapping[str, str] | None = None,
    signing_key_path: str | os.PathLike[str] | None = None,
    signing_password: str | bytes | None = None,
    signature_policy_context: Mapping[str, Any] | None = None,
    required_meanings: Sequence[str] = (),
    trust_store: str | os.PathLike[str] | None = None,
    overwrite: bool = False,
) -> PublicationWorkbookResult:
    """Build one validated workbook or leave no destination at all."""

    profile = profile.replace("-", "_")
    if profile not in {"master", "public", "minimal_public"}:
        raise ValueError("profile must be master, public, or minimal_public")
    target = Path(output_path)
    if target.suffix.lower() != ".xlsx":
        raise ValueError("publication workbook output must use .xlsx")
    if target.exists() and not overwrite:
        raise FileExistsError(target)
    target.parent.mkdir(parents=True, exist_ok=True)

    collected = collect_publication(
        artifacts,
        publication_id=publication_id,
        require_complete=(profile == "master"),
        transform=lambda record: prepare_record_for_workbook(
            record,
            profile=profile,
            safe_columns=safe_columns,
            public_sources=public_sources,
        ),
    )
    dataset = collected.dataset
    dataset.profile = profile
    ledger = import_statistics_ledger(
        experiment_statistics,
        declare_complete=declare_ledger_complete,
    )
    if profile != "master":
        ledger.statistics = [public_statistic_record(row) for row in ledger.statistics]
    reconcile_statistics(dataset, ledger)

    visible_dataset = dataset
    sheet_map = data_sheet_map(dataset)
    aggregate = publication_record(dataset, sheet_map=sheet_map)
    protected = {str(value) for value in protected_sections}
    if protected:
        if "publication:aggregate" in protected:
            raise ValueError(
                "publication:aggregate cannot be encrypted because workbook validation "
                "requires its public worksheet mapping and visible fingerprint"
            )
        from ..crypto.encryption import encrypt_sections
        from .models import PublicationDataset

        aggregate = encrypt_sections(
            aggregate,
            sorted(protected),
            password=encryption_password,
            recipients=encryption_recipients,
        )
        visible_dataset = PublicationDataset.from_dict(dataset.to_dict())
        for table in visible_dataset.tables:
            if str(table.table_id) in protected:
                table.contents = None
                table.metadata["protected"] = True
        if "statistics:reported" in protected:
            for statistic in visible_dataset.statistics:
                statistic.raw_record = {}
                statistic.normalized["raw_record_json"] = None
                statistic.metadata["protected_raw_record"] = True
        for table in aggregate.data_tables:
            table_id = str(table.metadata.get("publication_table_id", ""))
            if table_id in protected:
                table.contents = None
        if "statistics:reported" in protected:
            for statistic in aggregate.statistics:
                statistic["raw_record_json"] = None
            from ..schema import sha256_bytes
            from ..tables import statistics_csv_bytes

            aggregate.statistics_csv_sha256 = sha256_bytes(
                statistics_csv_bytes(aggregate.statistics)
            )
        extension = aggregate.extensions["publication_workbook"]
        extension["dataset"] = visible_dataset.evidence_dict()
        extension["visible_logical_fingerprint"] = visible_dataset.fingerprint()
        extension["protected_section_ids"] = sorted(protected)
        aggregate.data_status = (
            "protected"
            if any(table.metadata.get("protected") for table in aggregate.data_tables)
            else (
                "complete"
                if all(table.contents is not None for table in aggregate.data_tables)
                else "incomplete"
            )
        )
        from ..evidence import refresh_evidence_graph

        aggregate = refresh_evidence_graph(aggregate)
    if signing_key_path is not None:
        if signing_password is None:
            raise ValueError("signing_password is required when signing_key_path is supplied")
        from ..crypto.signatures import sign_record

        aggregate = sign_record(
            aggregate,
            private_key_path=str(signing_key_path),
            password=signing_password,
            policy_context=signature_policy_context,
        )

    with tempfile.TemporaryDirectory(prefix=".reprofig-workbook-", dir=target.parent) as temporary:
        workspace = Path(temporary)
        rendered = workspace / "rendered.xlsx"
        embedded = workspace / "validated.xlsx"
        render_result = render_workbook(visible_dataset, rendered)
        embed_publication_record(
            rendered,
            embedded,
            aggregate,
        )
        report = validate_publication_workbook(
            embedded,
            require_complete=(profile == "master"),
            public_safety=(profile != "master"),
        )
        if not report.valid:
            messages = "; ".join(issue.message for issue in report.issues)
            raise ValueError(f"publication workbook failed validation: {messages}")
        proof_report = None
        if required_meanings:
            from ..verification import verify_artifact

            proof_report = verify_artifact(
                embedded,
                required=required_meanings,
                trust_store=trust_store,
            )
            if not proof_report.valid:
                failed = ", ".join(
                    f"{meaning}={proof_report.meanings.get(meaning)}"
                    for meaning in required_meanings
                    if proof_report.meanings.get(meaning) != "pass"
                )
                raise ValueError(
                    "publication workbook failed required proof policy: " + failed
                )
        os.replace(embedded, target)

    return PublicationWorkbookResult(
        path=target,
        publication_id=str(dataset.publication_id),
        evidence_sha256=dataset.fingerprint(),
        figure_count=len(dataset.figures),
        unique_table_count=len(dataset.tables),
        statistic_count=len(dataset.statistics),
        statistics_coverage=dataset.statistics_coverage,
        validation=report,
        proof=proof_report.to_dict() if proof_report is not None else None,
    )


__all__ = ["PublicationWorkbookResult", "build_publication_workbook"]
