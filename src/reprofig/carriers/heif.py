"""AVIF/HEIF XMP carrier with explicit re-encoding consent."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord
from .base import CarrierCapabilities, CarrierError, CarrierFormatError, MissingDependencyError
from .manifest import CarrierManifest
from .payload import decode_bytes, encode_bytes

NS = b"https://reprofig.org/ns/carrier/1"
_PAYLOAD = re.compile(br"<reprofig:payload>([A-Za-z0-9+/=\s]+)</reprofig:payload>")


def _backend():
    try:
        import pillow_heif
    except ImportError as exc:
        raise MissingDependencyError("AVIF/HEIF support requires 'pip install reprofig[heif]'") from exc
    return pillow_heif


def _xmp(manifest: CarrierManifest) -> bytes:
    payload = encode_bytes(manifest.to_json().encode("utf-8")).encode("ascii")
    return (
        b'<x:xmpmeta xmlns:x="adobe:ns:meta/">'
        b'<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">'
        b'<rdf:Description rdf:about="" xmlns:reprofig="https://reprofig.org/ns/carrier/1">'
        b"<reprofig:payload>" + payload + b"</reprofig:payload>"
        b"</rdf:Description></rdf:RDF></x:xmpmeta>"
    )


class HeifAdapter:
    def __init__(self, format: str) -> None:
        self.format = format
        extensions = (".avif",) if format == "avif" else (".heic", ".heif")
        mime = ("image/avif",) if format == "avif" else ("image/heif", "image/heic")
        self.capabilities = CarrierCapabilities(
            format=format,
            extensions=extensions,
            mime_types=mime,
            metadata_only=False,
            preserves_encoded_media=False,
            optional_dependency="Pillow>=11.3" if format == "avif" else "pillow-heif",
            notes="Embedding re-encodes media and therefore requires allow_reencode=True.",
        )

    def detect(self, prefix: bytes, path: Path) -> bool:
        if len(prefix) < 12 or prefix[4:8] != b"ftyp":
            return False
        brands = prefix[8:64]
        if self.format == "avif":
            return any(brand in brands for brand in (b"avif", b"avis"))
        return any(brand in brands for brand in (b"heic", b"heix", b"heif", b"mif1", b"msf1"))

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
        if not allow_reencode:
            raise CarrierError(
                f"{self.format.upper()} metadata embedding requires re-encoding; pass allow_reencode=True"
            )
        if self.format == "avif":
            try:
                from PIL import Image
            except ImportError as exc:
                raise MissingDependencyError(
                    "AVIF support requires 'pip install reprofig[heif]'"
                ) from exc
            target.parent.mkdir(parents=True, exist_ok=True)
            descriptor, temporary_name = tempfile.mkstemp(
                dir=str(target.parent), prefix=f".{target.name}.", suffix=".avif"
            )
            os.close(descriptor)
            temporary = Path(temporary_name)
            try:
                with Image.open(source) as image:
                    save_options = dict(options or {})
                    for key in ("exif", "icc_profile"):
                        if key in image.info:
                            save_options.setdefault(key, image.info[key])
                    save_options["xmp"] = _xmp(manifest)
                    image.save(temporary, format="AVIF", **save_options)
                os.replace(temporary, target)
            except (OSError, KeyError) as exc:
                raise CarrierFormatError("file is not valid AVIF") from exc
            finally:
                try:
                    temporary.unlink()
                except OSError:
                    pass
            return target
        pillow_heif = _backend()
        try:
            heif = pillow_heif.open_heif(source)
        except Exception as exc:
            raise CarrierFormatError(f"file is not valid {self.format.upper()}") from exc
        heif.info["xmp"] = _xmp(manifest)
        target.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            dir=str(target.parent), prefix=f".{target.name}.", suffix=target.suffix
        )
        os.close(descriptor)
        temporary = Path(temporary_name)
        try:
            heif.save(temporary, **dict(options or {}))
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
        if self.format == "avif":
            try:
                from PIL import Image
                with Image.open(source) as image:
                    xmp = image.info.get("xmp")
            except (ImportError, OSError) as exc:
                raise CarrierFormatError("file is not valid AVIF") from exc
            if not xmp or NS not in xmp:
                raise CarrierError("AVIF has no embedded ReproFig XMP")
            match = _PAYLOAD.search(xmp)
            if not match:
                raise CarrierError("AVIF ReproFig XMP payload is missing")
            manifest = CarrierManifest.from_json(
                decode_bytes(
                    match.group(1).decode("ascii"),
                    max_compressed=max_compressed,
                    max_decompressed=max_decompressed,
                )
            )
            return manifest.extract_records(
                max_compressed=max_compressed, max_decompressed=max_decompressed
            ), manifest
        pillow_heif = _backend()
        try:
            heif = pillow_heif.open_heif(source)
        except Exception as exc:
            raise CarrierFormatError(f"file is not valid {self.format.upper()}") from exc
        xmp = heif.info.get("xmp")
        if not xmp or NS not in xmp:
            raise CarrierError(f"{self.format.upper()} has no embedded ReproFig XMP")
        match = _PAYLOAD.search(xmp)
        if not match:
            raise CarrierError(f"{self.format.upper()} ReproFig XMP payload is missing")
        manifest = CarrierManifest.from_json(
            decode_bytes(
                match.group(1).decode("ascii"),
                max_compressed=max_compressed,
                max_decompressed=max_decompressed,
            )
        )
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest


AvifAdapter = lambda: HeifAdapter("avif")
