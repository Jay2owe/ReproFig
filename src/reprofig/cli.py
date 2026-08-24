"""Command-line interface for portable figure artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Sequence

from .compat import export_fsb
from .publication import (
    caption_for,
    extract_figure,
    inspect_figure,
    publish_figures,
    scan_figures,
)
from .schema import deterministic_json
from .svg import extract_record
from .validation import validate_svg


def _profile(value: str | None) -> str | None:
    return value.replace("-", "_") if value else value


def _key_value_pairs(values: Sequence[str] | None, *, option: str) -> dict[str, str] | None:
    if not values:
        return None
    result: dict[str, str] = {}
    for value in values:
        key, separator, mapped = value.partition("=")
        if not separator or not key.strip() or not mapped.strip():
            raise ValueError(f"{option} values must use KEY=VALUE")
        result[key.strip()] = mapped.strip()
    return result


def _parser(*, prog: str = "reprofig") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser("inspect", help="print embedded figure details")
    inspect_parser.add_argument("figure")

    validate_parser = commands.add_parser("validate", help="validate integrity and privacy")
    validate_parser.add_argument("figure")
    validate_parser.add_argument(
        "--profile", choices=["master", "public", "minimal_public", "minimal-public"]
    )
    validate_parser.add_argument("--complete", action="store_true")
    validate_parser.add_argument("--public-safety", action="store_true")

    extract_parser = commands.add_parser("extract", help="regenerate data and provenance files")
    extract_parser.add_argument("figure")
    extract_parser.add_argument("--output", required=True)
    extract_parser.add_argument("--overwrite", action="store_true")

    caption_parser = commands.add_parser("caption", help="write a deterministic caption draft")
    caption_parser.add_argument("figure")

    publish_parser = commands.add_parser("publish", help="make publication-safe derivatives")
    publish_parser.add_argument("figures", nargs="+")
    publish_parser.add_argument("--output-dir", required=True)
    publish_parser.add_argument(
        "--profile", choices=["public", "minimal_public", "minimal-public"], default="public"
    )
    publish_parser.add_argument(
        "--safe-columns",
        help="comma-separated allowlist applied to each single-table figure",
    )
    publish_parser.add_argument("--no-csv", action="store_true")
    publish_parser.add_argument("--ro-crate", action="store_true")
    publish_parser.add_argument(
        "--public-source",
        action="append",
        metavar="KEY=URI",
        help="replace one internal source with an approved public URI; repeatable",
    )

    scan_parser = commands.add_parser("scan", help="rebuild a searchable figure catalogue")
    scan_parser.add_argument("path")
    scan_parser.add_argument("--csv")
    scan_parser.add_argument("--jsonl")

    fsb_parser = commands.add_parser("fsb-export", help="export an FSB-compatible directory")
    fsb_parser.add_argument("figure")
    fsb_parser.add_argument("--output", required=True)
    return parser


def main(argv: Sequence[str] | None = None, *, prog: str = "reprofig") -> int:
    args = _parser(prog=prog).parse_args(argv)
    if args.command == "inspect":
        print(deterministic_json(inspect_figure(args.figure), indent=2))
        return 0
    if args.command == "validate":
        report = validate_svg(
            args.figure,
            expected_profile=_profile(args.profile),
            require_complete=args.complete,
            public_safety=args.public_safety or None,
        )
        print(deterministic_json(report.to_dict(), indent=2))
        return 0 if report.valid else 1
    if args.command == "extract":
        paths = extract_figure(args.figure, args.output, overwrite=args.overwrite)
        print("\n".join(str(path) for path in paths))
        return 0
    if args.command == "caption":
        print(caption_for(extract_record(args.figure)), end="")
        return 0
    if args.command == "publish":
        safe_columns = None
        if args.safe_columns:
            safe_columns = [value.strip() for value in args.safe_columns.split(",") if value.strip()]
        result = publish_figures(
            args.figures,
            output_dir=args.output_dir,
            figure_profile=_profile(args.profile),
            safe_columns=safe_columns,
            public_sources=_key_value_pairs(
                args.public_source, option="--public-source"
            ),
            write_csv=not args.no_csv,
            rocrate=args.ro_crate,
        )
        print(deterministic_json({
            "valid": result.valid,
            "svgs": [str(path) for path in result.svg_paths],
            "csvs": [str(path) for path in result.csv_paths],
            "manifest": str(result.manifest_path) if result.manifest_path else None,
            "validation": str(result.validation_path) if result.validation_path else None,
        }, indent=2))
        return 0 if result.valid else 1
    if args.command == "scan":
        rows = scan_figures(args.path, output_csv=args.csv, output_jsonl=args.jsonl)
        print(deterministic_json({"figures": len(rows)}, indent=2))
        return 0
    if args.command == "fsb-export":
        output = export_fsb(args.figure, args.output, svg_path=args.figure)
        print(output)
        return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
