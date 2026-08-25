"""PDF associated-file and XMP summary carrier."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord, sha256_bytes
from ..tables import safe_filename_token, statistics_csv_bytes
from .base import (
    CarrierCapabilities,
    CarrierError,
    CarrierFormatError,
    MissingDependencyError,
    record_path_tokens,
)
from .manifest import CarrierManifest

MANIFEST_NAME = "reprofig/manifest.json"
PREFIX = "reprofig/"
NS = "https://reprofig.org/ns/carrier/1/"


def _pikepdf():
    try:
        import pikepdf
    except ImportError as exc:
        raise MissingDependencyError("PDF support requires 'pip install reprofig[pdf]'") from exc
    return pikepdf


class PdfAdapter:
    capabilities = CarrierCapabilities(
        format="pdf",
        extensions=(".pdf",),
        mime_types=("application/pdf",),
        optional_dependency="pikepdf",
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        return prefix.startswith(b"%PDF-")

    def embed(
        self,
        source: Path,
        target: Path,
        records: Sequence[FigureRecord],
        *,
        manifest: CarrierManifest,
        allow_reencode: bool = False,
        options: dict[str, Any] | None = None,
    ) -> Path:
        pikepdf = _pikepdf()
        if b"/ByteRange" in source.read_bytes() and not bool(
            (options or {}).get("allow_invalidate_signature")
        ):
            raise CarrierError(
                "PDF contains a digital signature; pass "
                "options={'allow_invalidate_signature': True} to invalidate it explicitly"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.", suffix=".pdf"
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            with pikepdf.Pdf.open(source) as pdf:
                for name in list(pdf.attachments):
                    if name == MANIFEST_NAME or name.startswith(PREFIX):
                        del pdf.attachments[name]
                tokens = record_path_tokens(records)
                for entry in manifest.records:
                    entry.record_path = f"{PREFIX}{tokens[entry.figure_id]}/record.json"
                manifest_bytes = manifest.to_json(indent=2).encode("utf-8")
                pdf.attachments[MANIFEST_NAME] = manifest_bytes
                pdf.attachments[MANIFEST_NAME].relationship = pikepdf.Name("/Data")
                for record in records:
                    token = tokens[record.figure_id]
                    pdf.attachments[f"{PREFIX}{token}/record.json"] = record.to_json(
                        indent=2
                    ).encode("utf-8")
                    pdf.attachments[f"{PREFIX}{token}/record.json"].relationship = pikepdf.Name("/Data")
                    for index, table in enumerate(record.data_tables):
                        if table.contents is not None:
                            pdf.attachments[
                                f"{PREFIX}{token}/data/{index:03d}-{safe_filename_token(table.name)}.csv"
                            ] = table.contents.encode("utf-8")
                            pdf.attachments[
                                f"{PREFIX}{token}/data/{index:03d}-{safe_filename_token(table.name)}.csv"
                            ].relationship = pikepdf.Name("/Data")
                    pdf.attachments[
                        f"{PREFIX}{token}/statistics.csv"
                    ] = statistics_csv_bytes(record.statistics)
                    pdf.attachments[
                        f"{PREFIX}{token}/statistics.csv"
                    ].relationship = pikepdf.Name("/Data")
                with pdf.open_metadata(set_pikepdf_as_editor=False) as metadata:
                    metadata.register_xml_namespace(NS, "reprofig")
                    metadata["reprofig:schema"] = manifest.schema
                    metadata["reprofig:manifestAttachment"] = MANIFEST_NAME
                    metadata["reprofig:manifestSha256"] = sha256_bytes(manifest_bytes)
                    metadata["reprofig:figureIds"] = ",".join(
                        record.figure_id for record in records
                    )
                    metadata["reprofig:profiles"] = ",".join(
                        record.distribution_profile for record in records
                    )
                pdf.save(temporary)
            os.replace(temporary, target)
        except pikepdf.PdfError as exc:
            raise CarrierFormatError("PDF is invalid or encrypted") from exc
        finally:
            try:
                temporary.unlink()
            except OSError:
                pass
        return target

    def extract(
        self,
        source: Path,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> tuple[list[FigureRecord], CarrierManifest]:
        pikepdf = _pikepdf()
        try:
            with pikepdf.Pdf.open(source) as pdf:
                if MANIFEST_NAME not in pdf.attachments:
                    raise CarrierError("PDF has no embedded ReproFig manifest attachment")
                raw = pdf.attachments[MANIFEST_NAME].get_file().read_bytes()
        except pikepdf.PdfError as exc:
            raise CarrierFormatError("PDF is invalid or encrypted") from exc
        if len(raw) > max_decompressed:
            raise CarrierError("PDF ReproFig manifest exceeds size limit")
        manifest = CarrierManifest.from_json(raw)
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest
