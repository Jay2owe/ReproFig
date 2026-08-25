"""HDF5 native-group carrier."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord
from ..tables import safe_filename_token
from .base import (
    CarrierCapabilities,
    CarrierError,
    CarrierFormatError,
    MissingDependencyError,
    record_path_tokens,
)
from .manifest import CarrierManifest


def _h5py():
    try:
        import h5py
        import numpy as np
    except ImportError as exc:
        raise MissingDependencyError("HDF5 support requires 'pip install reprofig[hdf5]'") from exc
    return h5py, np


def _bytes_dataset(group: Any, name: str, value: bytes, np: Any) -> None:
    group.create_dataset(name, data=np.frombuffer(value, dtype="u1"), compression="gzip")


class Hdf5Adapter:
    capabilities = CarrierCapabilities(
        format="hdf5",
        extensions=(".h5", ".hdf5", ".hdf"),
        mime_types=("application/x-hdf5",),
        optional_dependency="h5py",
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        return prefix.startswith(b"\x89HDF\r\n\x1a\n")

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
        h5py, np = _h5py()
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.", suffix=".h5"
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            shutil.copy2(source, temporary)
            try:
                with h5py.File(temporary, "r+") as file:
                    if "reprofig" in file:
                        del file["reprofig"]
                    group = file.create_group("reprofig")
                    tokens = record_path_tokens(records)
                    for entry in manifest.records:
                        entry.record_path = f"/reprofig/{tokens[entry.figure_id]}/record_json"
                    group.attrs["schema"] = manifest.schema
                    _bytes_dataset(group, "manifest_json", manifest.to_json().encode("utf-8"), np)
                    for record in records:
                        record_group = group.create_group(tokens[record.figure_id])
                        _bytes_dataset(
                            record_group, "record_json", record.to_json().encode("utf-8"), np
                        )
                        figure_data = record_group.create_group("data")
                        for index, table in enumerate(record.data_tables):
                            if table.contents is not None:
                                dataset = f"{index:03d}_{safe_filename_token(table.name)}_csv"
                                _bytes_dataset(
                                    figure_data, dataset, table.contents.encode("utf-8"), np
                                )
                os.replace(temporary, target)
            except OSError as exc:
                raise CarrierFormatError("file is not writable HDF5") from exc
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
        h5py, _np = _h5py()
        try:
            with h5py.File(source, "r") as file:
                if "reprofig/manifest_json" not in file:
                    raise CarrierError("HDF5 has no embedded ReproFig group")
                dataset = file["reprofig/manifest_json"]
                if dataset.size > max_decompressed:
                    raise CarrierError("HDF5 ReproFig manifest exceeds size limit")
                raw = bytes(dataset[...])
        except OSError as exc:
            raise CarrierFormatError("file is not valid HDF5") from exc
        manifest = CarrierManifest.from_json(raw)
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest
