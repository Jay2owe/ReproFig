"""Non-executable HTML data-block carrier."""

from __future__ import annotations

import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Sequence

from ..schema import FigureRecord
from .base import CarrierCapabilities, CarrierError, CarrierFormatError, atomic_write_bytes
from .manifest import CarrierManifest

START = '<script type="application/vnd.reprofig+json" data-reprofig-schema="reprofig-carrier/1">'
BLOCK = re.compile(
    r"\s*<script\b[^>]*type=[\"']application/vnd\.reprofig\+json[\"'][^>]*>.*?</script\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)
CONTENT = re.compile(
    r"<script\b[^>]*type=[\"']application/vnd\.reprofig\+json[\"'][^>]*>(.*?)</script\s*>",
    flags=re.IGNORECASE | re.DOTALL,
)


class _ReproFigBlockParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=False)
        self._capturing = False
        self._parts: list[str] = []
        self.blocks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attributes = {name.lower(): value for name, value in attrs}
        if tag.lower() == "script" and attributes.get("type", "").lower() == "application/vnd.reprofig+json":
            if self._capturing:
                raise CarrierError("nested ReproFig HTML data blocks are invalid")
            self._capturing = True
            self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capturing:
            self._parts.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._capturing:
            self.blocks.append("".join(self._parts))
            self._capturing = False
            self._parts = []


def _safe_json(manifest: CarrierManifest) -> str:
    return manifest.to_json().replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


class HtmlAdapter:
    capabilities = CarrierCapabilities(
        format="html",
        extensions=(".html", ".htm"),
        mime_types=("text/html",),
    )

    @staticmethod
    def detect(prefix: bytes, path: Path) -> bool:
        cleaned = prefix.lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
        return cleaned.startswith(b"<!doctype html") or b"<html" in cleaned[:1024]

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
        raw = source.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise CarrierFormatError("HTML must be UTF-8 to embed ReproFig data safely") from exc
        text = BLOCK.sub("", text)
        block = "\n" + START + _safe_json(manifest) + "</script>\n"
        closing = re.search(r"</body\s*>", text, flags=re.IGNORECASE)
        if closing is None:
            closing = re.search(r"</html\s*>", text, flags=re.IGNORECASE)
        if closing:
            text = text[: closing.start()] + block + text[closing.start() :]
        else:
            text += block
        atomic_write_bytes(target, text.encode("utf-8"))
        return target

    def extract(
        self,
        source: Path,
        *,
        max_compressed: int,
        max_decompressed: int,
    ) -> tuple[list[FigureRecord], CarrierManifest]:
        text = source.read_text(encoding="utf-8-sig")
        parser = _ReproFigBlockParser()
        parser.feed(text)
        parser.close()
        matches = parser.blocks
        if not matches:
            raise CarrierError("HTML has no embedded ReproFig data block")
        if len(matches) > 1:
            raise CarrierError("HTML contains multiple ReproFig data blocks")
        value = matches[0]
        if len(value.encode("utf-8")) > max_decompressed:
            raise CarrierError("HTML ReproFig manifest exceeds size limit")
        manifest = CarrierManifest.from_json(value)
        return manifest.extract_records(
            max_compressed=max_compressed, max_decompressed=max_decompressed
        ), manifest
