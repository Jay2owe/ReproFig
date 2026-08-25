"""FITS dedicated HDU carrier."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord
from .base import CarrierCapabilities, CarrierError, CarrierFormatError, MissingDependencyError
from .manifest import CarrierManifest

HDU_NAME = "REPROFIG"


def _astropy():
    try:
        from astropy.io import fits
        import numpy as np
    except ImportError as exc:
        raise MissingDependencyError("FITS support requires 'pip install reprofig[fits]'") from exc
    return fits, np


class FitsAdapter:
    capabilities = CarrierCapabilities(
        format="fits",
        extensions=(".fits", ".fit", ".fts"),
        mime_types=("application/fits", "image/fits"),
        optional_dependency="astropy",
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        return prefix.startswith(b"SIMPLE  =")

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
        fits, np = _astropy()
        try:
            with fits.open(source, mode="readonly", memmap=False) as opened:
                hdus = [hdu.copy() for hdu in opened if hdu.name.upper() != HDU_NAME]
        except OSError as exc:
            raise CarrierFormatError("file is not valid FITS") from exc
        for entry in manifest.records:
            entry.record_path = f"REPROFIG:{entry.figure_id}:RECORD"
        record_arrays = [
            np.frombuffer(record.to_json().encode("utf-8"), dtype="u1") for record in records
        ]
        manifest_arrays = [
            np.frombuffer(manifest.to_json().encode("utf-8"), dtype="u1")
        ] + [np.array([], dtype="u1") for _record in records[1:]]
        metadata = fits.BinTableHDU.from_columns(
            [
                fits.Column(
                    name="FIGURE_ID",
                    format="64A",
                    array=np.asarray([record.figure_id for record in records]),
                ),
                fits.Column(
                    name="PROFILE",
                    format="16A",
                    array=np.asarray([record.distribution_profile for record in records]),
                ),
                fits.Column(name="RECORD", format="PB()", array=record_arrays),
                fits.Column(name="MANIFEST", format="PB()", array=manifest_arrays),
            ],
            name=HDU_NAME,
        )
        metadata.header["RFSCHEMA"] = (manifest.schema, "ReproFig carrier schema")
        metadata.header["RFCOUNT"] = (len(records), "Number of figure records")
        hdus.append(metadata)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.", suffix=".fits"
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            fits.HDUList(hdus).writeto(temporary, overwrite=True, checksum=True)
            os.replace(temporary, target)
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
        fits, _np = _astropy()
        try:
            with fits.open(source, mode="readonly", memmap=False) as opened:
                matches = [hdu for hdu in opened if hdu.name.upper() == HDU_NAME]
                if not matches:
                    raise CarrierError("FITS has no embedded REPROFIG HDU")
                table = matches[-1].data
                if table is None or len(table) == 0 or "MANIFEST" not in table.names:
                    raise CarrierError("FITS REPROFIG table is empty or invalid")
                raw = bytes(table["MANIFEST"][0])
        except OSError as exc:
            raise CarrierFormatError("file is not valid FITS") from exc
        if len(raw) > max_decompressed:
            raise CarrierError("FITS ReproFig manifest exceeds size limit")
        manifest = CarrierManifest.from_json(raw)
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest
