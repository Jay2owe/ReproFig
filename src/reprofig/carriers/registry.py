"""Lazy carrier registry with content-first format detection."""

from __future__ import annotations

from pathlib import Path
from importlib.util import find_spec
from typing import Any

from .base import CarrierAdapter, CarrierCapabilities, CarrierFormatError

_ALIASES = {
    "jpg": "jpeg",
    "tif": "tiff",
    "h5": "hdf5",
    "hdf": "hdf5",
    "nc": "netcdf",
    "nc4": "netcdf",
    "fit": "fits",
    "fts": "fits",
    "htm": "html",
    "heic": "heif",
    "reprofig": "zip",
}


def _factories() -> list[tuple[str, Any]]:
    from .bundle import BundleAdapter
    from .fits import FitsAdapter
    from .hdf5 import Hdf5Adapter
    from .heif import AvifAdapter, HeifAdapter
    from .html import HtmlAdapter
    from .jpeg import JpegAdapter
    from .netcdf import NetcdfAdapter
    from .office import DocxAdapter, PptxAdapter, XlsxAdapter
    from .pdf import PdfAdapter
    from .png import PngAdapter
    from .svg import SvgAdapter
    from .tiff import TiffAdapter
    from .webp import WebpAdapter

    return [
        ("svg", SvgAdapter),
        ("pdf", PdfAdapter),
        ("png", PngAdapter),
        ("jpeg", JpegAdapter),
        ("tiff", TiffAdapter),
        ("webp", WebpAdapter),
        ("avif", AvifAdapter),
        ("heif", lambda: HeifAdapter("heif")),
        ("pptx", PptxAdapter),
        ("docx", DocxAdapter),
        ("xlsx", XlsxAdapter),
        ("html", HtmlAdapter),
        ("netcdf", NetcdfAdapter),
        ("hdf5", Hdf5Adapter),
        ("fits", FitsAdapter),
        ("zip", BundleAdapter),
    ]


def _normalise(value: str) -> str:
    value = value.lower().lstrip(".")
    return _ALIASES.get(value, value)


def get_adapter(format: str) -> CarrierAdapter:
    wanted = _normalise(format)
    for name, factory in _factories():
        if name == wanted:
            return factory()
    raise CarrierFormatError(f"unsupported ReproFig carrier format {format!r}")


def identify_format(path: str | Path, *, format: str | None = None) -> str:
    artifact = Path(path)
    if format:
        adapter = get_adapter(format)
        if artifact.exists():
            prefix = artifact.read_bytes()[:4096]
            if not adapter.detect(prefix, artifact):
                raise CarrierFormatError(
                    f"file contents do not match declared {adapter.capabilities.format!r} format"
                )
        return adapter.capabilities.format
    if not artifact.exists():
        suffix = _normalise(artifact.suffix)
        get_adapter(suffix)
        return suffix
    prefix = artifact.read_bytes()[:4096]
    for name, factory in _factories():
        adapter = factory()
        if adapter.detect(prefix, artifact):
            return name
    suffix = _normalise(artifact.suffix)
    try:
        adapter = get_adapter(suffix)
    except CarrierFormatError:
        pass
    else:
        if adapter.detect(prefix, artifact):
            return adapter.capabilities.format
    raise CarrierFormatError(f"cannot identify carrier format for {artifact}")


def formats() -> list[dict[str, Any]]:
    dependencies: dict[str, tuple[tuple[str, ...], str] | None] = {
        "pdf": (("pikepdf",), "pdf"),
        "tiff": (("tifftools",), "raster"),
        "webp": (("PIL",), "raster"),
        "avif": (("PIL",), "heif"),
        "heif": (("pillow_heif",), "heif"),
        "hdf5": (("h5py",), "hdf5"),
        "netcdf": (("netCDF4", "h5py"), "netcdf"),
        "fits": (("astropy",), "fits"),
    }
    storage = {
        "pdf": "attachment",
        "pptx": "package_part",
        "docx": "package_part",
        "xlsx": "package_part",
        "hdf5": "native_dataset",
        "netcdf": "native_dataset",
        "fits": "native_dataset",
        "zip": "archive_entry",
    }
    size_class = {
        "pdf": "attachment",
        "pptx": "attachment",
        "docx": "attachment",
        "xlsx": "attachment",
        "hdf5": "scientific_container",
        "netcdf": "scientific_container",
        "fits": "scientific_container",
        "zip": "scientific_container",
    }
    robust = {"hdf5", "netcdf", "fits", "zip"}
    result: list[dict[str, Any]] = []
    for name, factory in _factories():
        value = factory().capabilities.to_dict()
        dependency = dependencies.get(name)
        value["available"] = dependency is None or all(
            find_spec(module) is not None for module in dependency[0]
        )
        value["install_extra"] = dependency[1] if dependency else None
        value["storage"] = storage.get(name, value["storage"])
        value["size_class"] = size_class.get(name, value["size_class"])
        value["metadata_survival"] = "robust" if name in robust else value["metadata_survival"]
        result.append(value)
    return result
