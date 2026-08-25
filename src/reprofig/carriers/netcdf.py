"""netCDF-4 native-group carrier."""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord
from .base import (
    CarrierCapabilities,
    CarrierError,
    CarrierFormatError,
    MissingDependencyError,
    record_path_tokens,
)
from .manifest import CarrierManifest


def _netcdf():
    try:
        import netCDF4
        import numpy as np
    except ImportError as exc:
        raise MissingDependencyError("netCDF support requires 'pip install reprofig[netcdf]'") from exc
    return netCDF4, np


def _write_bytes(group: Any, name: str, value: bytes, np: Any) -> None:
    dimension = f"{name}_length"
    group.createDimension(dimension, len(value))
    variable = group.createVariable(name, "u1", (dimension,), zlib=True)
    variable[:] = np.frombuffer(value, dtype="u1")


class NetcdfAdapter:
    capabilities = CarrierCapabilities(
        format="netcdf",
        extensions=(".nc", ".nc4", ".cdf"),
        mime_types=("application/x-netcdf",),
        optional_dependency="netCDF4",
        notes="Only netCDF-4/HDF5 files support embedded groups.",
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        if prefix.startswith(b"CDF"):
            return True
        if not prefix.startswith(b"\x89HDF\r\n\x1a\n"):
            return False
        try:
            import h5py

            with h5py.File(path, "r") as file:
                return "_NCProperties" in file.attrs
        except Exception:
            return False

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
        netCDF4, np = _netcdf()
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.", suffix=".nc"
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            shutil.copy2(source, temporary)
            try:
                with netCDF4.Dataset(temporary, "r+") as dataset:
                    if dataset.data_model not in {"NETCDF4", "NETCDF4_CLASSIC"}:
                        raise CarrierFormatError("classic netCDF cannot contain ReproFig groups")
                    index = 1
                    name = "reprofig"
                    while name in dataset.groups:
                        index += 1
                        name = f"reprofig_{index}"
                    group = dataset.createGroup(name)
                    tokens = record_path_tokens(records)
                    for entry in manifest.records:
                        entry.record_path = (
                            f"/{name}/{tokens[entry.figure_id]}/record_json"
                        )
                    group.setncattr("schema", manifest.schema)
                    _write_bytes(group, "manifest_json", manifest.to_json().encode("utf-8"), np)
                    for record in records:
                        record_group = group.createGroup(tokens[record.figure_id])
                        _write_bytes(
                            record_group,
                            "record_json",
                            record.to_json().encode("utf-8"),
                            np,
                        )
                    dataset.setncattr("reprofig_group", name)
                os.replace(temporary, target)
            except (OSError, RuntimeError) as exc:
                raise CarrierFormatError("file is not writable netCDF-4") from exc
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
        netCDF4, _np = _netcdf()
        try:
            with netCDF4.Dataset(source) as dataset:
                name = dataset.getncattr("reprofig_group") if "reprofig_group" in dataset.ncattrs() else "reprofig"
                if name not in dataset.groups or "manifest_json" not in dataset.groups[name].variables:
                    raise CarrierError("netCDF has no embedded ReproFig group")
                variable = dataset.groups[name].variables["manifest_json"]
                if variable.size > max_decompressed:
                    raise CarrierError("netCDF ReproFig manifest exceeds size limit")
                raw = bytes(variable[:].filled(0) if hasattr(variable[:], "filled") else variable[:])
        except OSError as exc:
            raise CarrierFormatError("file is not valid netCDF") from exc
        manifest = CarrierManifest.from_json(raw)
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest
