"""Command-line interface for portable figure artifacts."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Sequence

from .api import (
    bundle_artifacts,
    build_publication_workbook,
    embed_file,
    extract_artifact,
    extract_record,
    formats as carrier_formats,
    inspect_artifact,
    publish_artifacts,
    scan_artifacts,
    validate_artifact,
)
from .compat import export_fsb
from .publication import caption_for
from .schema import FigureRecord, deterministic_json


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


def _decryption_arguments(
    args: argparse.Namespace, *, password_attribute: str = "password_env"
) -> dict[str, object] | None:
    environment_name = getattr(args, password_attribute, None)
    password = os.environ.get(environment_name) if environment_name else None
    if environment_name and not password:
        raise ValueError(
            f"password environment variable {environment_name!r} is missing or empty"
        )
    recipient_key = getattr(args, "recipient_key", None)
    private_key = None
    if recipient_key:
        recipient_password_env = getattr(args, "recipient_password_env", None)
        if not recipient_password_env:
            raise ValueError(
                "--recipient-password-env is required with --recipient-key"
            )
        recipient_password = os.environ.get(recipient_password_env)
        if not recipient_password:
            raise ValueError(
                f"password environment variable {recipient_password_env!r} is missing or empty"
            )
        from .crypto.keys import load_recipient_private_key

        private_key = load_recipient_private_key(
            recipient_key, password=recipient_password
        )
    if password is None and private_key is None:
        return None
    return {"password": password, "recipient_private_key": private_key}


def _source_table_arguments(values: Sequence[str]) -> dict[str, object]:
    mapped = _key_value_pairs(values, option="--source-table") or {}
    from .tables import table_from_data

    result: dict[str, object] = {}
    for identity, filename in mapped.items():
        path = Path(filename)
        result[identity] = table_from_data(
            path.read_bytes(), name=path.stem, purpose="verification_source"
        )
    return result


def _parser(*, prog: str = "reprofig") -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=prog)
    parser.add_argument("--json", action="store_true", help="emit machine-readable errors")
    commands = parser.add_subparsers(dest="command", required=True)

    inspect_parser = commands.add_parser("inspect", help="print embedded figure details")
    inspect_parser.add_argument("figure")
    inspect_parser.add_argument("--figure-id")

    commands.add_parser("formats", help="list supported carrier formats")

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
    extract_parser.add_argument("--figure-id")
    extract_parser.add_argument("--name", help="human-readable export name")
    extract_parser.add_argument(
        "--naming", choices=["readable", "legacy"], default="readable"
    )

    embed_parser = commands.add_parser("embed", help="embed a record in an existing artifact")
    embed_parser.add_argument("artifact")
    embed_parser.add_argument("--record", required=True)
    embed_parser.add_argument("--output")
    embed_parser.add_argument("--allow-reencode", action="store_true")

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
    publish_parser.add_argument("--allow-reencode", action="store_true")
    publish_parser.add_argument(
        "--name", help="human-readable export name for a single input"
    )
    publish_parser.add_argument(
        "--naming", choices=["readable", "legacy"], default="readable"
    )
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

    bundle_parser = commands.add_parser("bundle", help="build a deterministic ReproFig ZIP")
    bundle_parser.add_argument("artifacts", nargs="+")
    bundle_parser.add_argument("--output", required=True)

    workbook_parser = commands.add_parser(
        "publication-workbook", help="combine figure data and statistics into verified Excel"
    )
    workbook_parser.add_argument("artifacts", nargs="+")
    workbook_parser.add_argument("--output", required=True)
    workbook_parser.add_argument(
        "--profile",
        choices=["master", "public", "minimal_public", "minimal-public"],
        default="master",
    )
    workbook_parser.add_argument("--publication-id")
    workbook_parser.add_argument("--statistics-ledger")
    workbook_parser.add_argument("--declare-ledger-complete", action="store_true")
    workbook_parser.add_argument("--safe-columns-json")
    workbook_parser.add_argument(
        "--public-source", action="append", metavar="KEY=URI"
    )
    workbook_parser.add_argument("--overwrite", action="store_true")
    workbook_parser.add_argument("--protect-section", action="append", default=[])
    workbook_parser.add_argument("--encryption-password-env")
    workbook_parser.add_argument("--recipient-file")
    workbook_parser.add_argument("--signing-key")
    workbook_parser.add_argument("--signing-password-env")
    workbook_parser.add_argument("--require", action="append", default=[])
    workbook_parser.add_argument("--trust-store")

    verify_parser = commands.add_parser("verify", help="verify proof meanings independently")
    verify_parser.add_argument("artifact")
    verify_parser.add_argument("--require", action="append", default=[])
    verify_parser.add_argument("--reproduction-report")
    verify_parser.add_argument("--trust-store")
    verify_parser.add_argument("--password-env")
    verify_parser.add_argument("--recipient-key")
    verify_parser.add_argument("--recipient-password-env")
    verify_parser.add_argument(
        "--source-table", action="append", default=[], metavar="ID=CSV"
    )

    reproduce_parser = commands.add_parser(
        "reproduce",
        help="explicitly run a trusted embedded producer and save its figure",
    )
    reproduce_parser.add_argument("artifact")
    reproduce_parser.add_argument("--bundle-root")
    reproduce_parser.add_argument("--output-dir", required=True)
    reproduce_parser.add_argument("--report")
    reproduce_parser.add_argument("--timeout-seconds", type=float, default=120.0)
    reproduce_parser.add_argument("--max-input-bytes", type=int, default=250_000_000)
    reproduce_parser.add_argument("--max-output-bytes", type=int, default=100_000_000)
    reproduce_parser.add_argument("--max-log-bytes", type=int, default=1_000_000)
    reproduce_parser.add_argument("--execute-trusted-producer", action="store_true")
    reproduce_parser.add_argument("--overwrite", action="store_true")
    reproduce_parser.add_argument("--name", help="human-readable export name")
    reproduce_parser.add_argument(
        "--naming", choices=["readable", "legacy"], default="readable"
    )

    key_parser = commands.add_parser("key", help="create protected signing or recipient keys")
    key_commands = key_parser.add_subparsers(dest="key_command", required=True)
    key_generate = key_commands.add_parser("generate")
    key_generate.add_argument("--output", required=True)
    key_generate.add_argument("--password-env", required=True)
    key_generate.add_argument("--kind", choices=["signing", "recipient"], default="signing")
    key_generate.add_argument("--overwrite", action="store_true")
    key_public = key_commands.add_parser("public")
    key_public.add_argument("--key", required=True)
    key_public.add_argument("--password-env", required=True)
    key_public.add_argument("--kind", choices=["signing", "recipient"], default="signing")

    sign_parser = commands.add_parser("sign", help="sign an artifact evidence root")
    sign_parser.add_argument("artifact")
    sign_parser.add_argument("--key", required=True)
    sign_parser.add_argument("--password-env", required=True)
    sign_parser.add_argument("--output")

    attest_parser = commands.add_parser(
        "attest", help="sign the deterministic hash of a verification report"
    )
    attest_parser.add_argument("artifact")
    attest_parser.add_argument("--key", required=True)
    attest_parser.add_argument("--password-env", required=True)
    attest_parser.add_argument("--require", action="append", default=[])
    attest_parser.add_argument("--reproduction-report")
    attest_parser.add_argument("--trust-store")
    attest_parser.add_argument("--evidence-password-env")
    attest_parser.add_argument("--recipient-key")
    attest_parser.add_argument("--recipient-password-env")
    attest_parser.add_argument(
        "--source-table", action="append", default=[], metavar="ID=CSV"
    )
    attest_parser.add_argument("--output")

    encrypt_parser = commands.add_parser("encrypt", help="encrypt selected evidence sections")
    encrypt_parser.add_argument("artifact")
    encrypt_parser.add_argument("--section", action="append", required=True)
    encrypt_parser.add_argument("--password-env")
    encrypt_parser.add_argument("--recipient-file")
    encrypt_parser.add_argument("--output")

    decrypt_parser = commands.add_parser("decrypt", help="decrypt accessible evidence to a new JSON file")
    decrypt_parser.add_argument("artifact")
    decrypt_parser.add_argument("--password-env")
    decrypt_parser.add_argument("--recipient-key")
    decrypt_parser.add_argument("--recipient-password-env")
    decrypt_parser.add_argument("--output", required=True)
    decrypt_parser.add_argument("--overwrite", action="store_true")

    trust_parser = commands.add_parser("trust", help="manage an offline signer trust store")
    trust_commands = trust_parser.add_subparsers(dest="trust_command", required=True)
    trust_list = trust_commands.add_parser("list")
    trust_list.add_argument("--store", required=True)
    trust_add = trust_commands.add_parser("add")
    trust_add.add_argument("--store", required=True)
    trust_add.add_argument("--fingerprint", required=True)
    trust_add.add_argument("--label", required=True)
    trust_add.add_argument("--scope", action="append", default=[])
    trust_revoke = trust_commands.add_parser("revoke")
    trust_revoke.add_argument("--store", required=True)
    trust_revoke.add_argument("--fingerprint", required=True)
    trust_revoke.add_argument("--at", required=True)
    trust_revoke.add_argument("--replacement")
    trust_remove = trust_commands.add_parser("remove")
    trust_remove.add_argument("--store", required=True)
    trust_remove.add_argument("--fingerprint", required=True)
    trust_policy = trust_commands.add_parser("set-policy")
    trust_policy.add_argument("--store", required=True)
    trust_policy.add_argument("--scope", action="append", default=[])
    trust_policy.add_argument("--minimum", type=int, default=1)
    trust_policy.add_argument("--fingerprint", action="append", default=[])

    guard_parser = commands.add_parser("guard", help="run plotting code under an explicit output policy")
    guard_commands = guard_parser.add_subparsers(dest="guard_command", required=True)
    guard_python = guard_commands.add_parser("python")
    guard_python.add_argument("--policy", required=True)
    guard_python.add_argument("script")
    guard_python.add_argument("arguments", nargs=argparse.REMAINDER)

    broker_parser = commands.add_parser("broker", help="verify and promote controlled candidate outputs")
    broker_commands = broker_parser.add_subparsers(dest="broker_command", required=True)
    broker_promote = broker_commands.add_parser("promote")
    broker_promote.add_argument("candidate")
    broker_promote.add_argument("--workspace", required=True)
    broker_promote.add_argument("--destination", required=True)
    broker_promote.add_argument("--policy", required=True)
    broker_promote.add_argument("--name")
    broker_promote.add_argument("--record")
    broker_promote.add_argument("--semantic-bindings")

    registry_parser = commands.add_parser("registry", help="publish or resolve stripped-figure identities")
    registry_commands = registry_parser.add_subparsers(dest="registry_command", required=True)
    registry_entry = registry_commands.add_parser("entry")
    registry_entry.add_argument("artifact")
    registry_entry.add_argument("--registry", required=True)
    registry_entry.add_argument("--recovery", action="append", required=True)
    registry_entry.add_argument("--key", required=True)
    registry_entry.add_argument("--password-env", required=True)
    registry_resolve = registry_commands.add_parser("resolve")
    registry_resolve.add_argument("artifact")
    registry_resolve.add_argument("--registry", required=True)
    registry_resolve.add_argument("--trust-store", required=True)
    registry_recover = registry_commands.add_parser("recover")
    registry_recover.add_argument("artifact")
    registry_recover.add_argument("--registry", required=True)
    registry_recover.add_argument("--trust-store", required=True)
    registry_recover.add_argument("--output", required=True)
    registry_recover.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: Sequence[str] | None = None, *, prog: str = "reprofig") -> int:
    raw = list(argv) if argv is not None else sys.argv[1:]
    json_requested = "--json" in raw
    if json_requested:
        raw = [value for value in raw if value != "--json"]
    args = _parser(prog=prog).parse_args(raw)
    args.json = bool(args.json or json_requested)
    try:
        return _dispatch(args)
    except Exception as exc:
        if args.json:
            print(
                deterministic_json(
                    {"error": type(exc).__name__, "message": str(exc)}, indent=2
                ),
                file=sys.stderr,
            )
            return 2
        raise


def _dispatch(args: argparse.Namespace) -> int:
    if args.command == "inspect":
        print(
            deterministic_json(
                inspect_artifact(args.figure, figure_id=args.figure_id), indent=2
            )
        )
        return 0
    if args.command == "formats":
        print(deterministic_json(carrier_formats(), indent=2))
        return 0
    if args.command == "validate":
        report = validate_artifact(
            args.figure,
            expected_profile=_profile(args.profile),
            require_complete=args.complete,
            public_safety=args.public_safety or None,
        )
        print(deterministic_json(report.to_dict(), indent=2))
        return 0 if report.valid else 1
    if args.command == "extract":
        paths = extract_artifact(
            args.figure,
            args.output,
            overwrite=args.overwrite,
            figure_id=args.figure_id,
            export_name=args.name,
            naming=args.naming,
        )
        print("\n".join(str(path) for path in paths))
        return 0
    if args.command == "embed":
        record = FigureRecord.from_json(Path(args.record).read_bytes())
        output = embed_file(
            args.artifact,
            record,
            output_path=args.output,
            allow_reencode=args.allow_reencode,
        )
        print(output)
        return 0
    if args.command == "caption":
        print(caption_for(extract_record(args.figure)), end="")
        return 0
    if args.command == "publish":
        safe_columns = None
        if args.safe_columns:
            safe_columns = [value.strip() for value in args.safe_columns.split(",") if value.strip()]
        result = publish_artifacts(
            args.figures,
            output_dir=args.output_dir,
            figure_profile=_profile(args.profile),
            safe_columns=safe_columns,
            public_sources=_key_value_pairs(
                args.public_source, option="--public-source"
            ),
            write_csv=not args.no_csv,
            bundle=args.ro_crate,
            allow_reencode=args.allow_reencode,
            export_name=args.name,
            naming=args.naming,
        )
        print(deterministic_json({
            "valid": result.valid,
            "artifacts": [str(path) for path in result.artifact_paths],
            "csvs": [str(path) for path in result.csv_paths],
            "manifest": str(result.manifest_path) if result.manifest_path else None,
            "validation": str(result.validation_path) if result.validation_path else None,
        }, indent=2))
        return 0 if result.valid else 1
    if args.command == "scan":
        rows = scan_artifacts(args.path, output_csv=args.csv, output_jsonl=args.jsonl)
        print(deterministic_json({"figures": len(rows)}, indent=2))
        return 0
    if args.command == "fsb-export":
        output = export_fsb(args.figure, args.output, svg_path=args.figure)
        print(output)
        return 0
    if args.command == "bundle":
        output = bundle_artifacts(args.artifacts, args.output)
        print(output)
        return 0
    if args.command == "publication-workbook":
        safe_columns = None
        if args.safe_columns_json:
            safe_columns = json.loads(Path(args.safe_columns_json).read_text(encoding="utf-8"))
            if not isinstance(safe_columns, dict):
                raise ValueError("--safe-columns-json must contain a JSON object")
        encryption_password = None
        if args.encryption_password_env:
            encryption_password = os.environ.get(args.encryption_password_env)
            if not encryption_password:
                raise ValueError(
                    f"password environment variable {args.encryption_password_env!r} is missing or empty"
                )
        recipients = None
        if args.recipient_file:
            recipients = json.loads(Path(args.recipient_file).read_text(encoding="utf-8"))
            if not isinstance(recipients, dict) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in recipients.items()
            ):
                raise ValueError("--recipient-file must contain a JSON object of name to public key")
        signing_password = None
        if args.signing_key:
            if not args.signing_password_env:
                raise ValueError("--signing-password-env is required with --signing-key")
            signing_password = os.environ.get(args.signing_password_env)
            if not signing_password:
                raise ValueError(
                    f"password environment variable {args.signing_password_env!r} is missing or empty"
                )
        result = build_publication_workbook(
            args.artifacts,
            args.output,
            profile=_profile(args.profile) or "master",
            publication_id=args.publication_id,
            experiment_statistics=args.statistics_ledger,
            declare_ledger_complete=args.declare_ledger_complete,
            safe_columns=safe_columns,
            public_sources=_key_value_pairs(args.public_source, option="--public-source"),
            protected_sections=args.protect_section,
            encryption_password=encryption_password,
            encryption_recipients=recipients,
            signing_key_path=args.signing_key,
            signing_password=signing_password,
            signature_policy_context={
                "profile": _profile(args.profile) or "master",
                "required_meanings": sorted(args.require),
            },
            required_meanings=args.require,
            trust_store=args.trust_store,
            overwrite=args.overwrite,
        )
        print(deterministic_json(result.to_dict(), indent=2) if args.json else result.path)
        return 0 if result.valid else 1
    if args.command == "verify":
        from .verification import verify_artifact as verify_proof

        decryption = _decryption_arguments(args)
        report = verify_proof(
            args.artifact,
            required=args.require,
            source_tables=_source_table_arguments(args.source_table),
            decryption=decryption,
            trust_store=args.trust_store,
            reproduction_report=args.reproduction_report,
        )
        print(report.to_json(indent=2))
        return 0 if report.valid else 1
    if args.command == "reproduce":
        from .reproduction import ReproductionPolicy, reproduce_figure

        report = reproduce_figure(
            args.artifact,
            bundle_root=args.bundle_root,
            output_dir=args.output_dir,
            report_path=args.report,
            policy=ReproductionPolicy(
                timeout_seconds=args.timeout_seconds,
                max_input_bytes=args.max_input_bytes,
                max_output_bytes=args.max_output_bytes,
                max_log_bytes=args.max_log_bytes,
            ),
            execute_trusted_producer=args.execute_trusted_producer,
            overwrite=args.overwrite,
            export_name=args.name,
            naming=args.naming,
        )
        print(report.to_json(indent=2))
        return 0 if report.valid else 1
    if args.command == "key":
        from .crypto.keys import (
            generate_recipient_key,
            generate_signing_key,
            load_recipient_private_key,
            load_signing_private_key,
            public_key_fingerprint,
            recipient_public_bytes,
            signing_public_bytes,
        )

        password = os.environ.get(args.password_env)
        if not password:
            raise ValueError(f"password environment variable {args.password_env!r} is missing or empty")
        if args.key_command == "generate":
            generator = generate_signing_key if args.kind == "signing" else generate_recipient_key
            print(generator(args.output, password=password, overwrite=args.overwrite))
            return 0
        loader = (
            load_signing_private_key
            if args.kind == "signing"
            else load_recipient_private_key
        )
        public_bytes = (
            signing_public_bytes(loader(args.key, password=password))
            if args.kind == "signing"
            else recipient_public_bytes(loader(args.key, password=password))
        )
        import base64

        print(deterministic_json({
            "kind": args.kind,
            "public_key": base64.b64encode(public_bytes).decode("ascii"),
            "fingerprint": public_key_fingerprint(public_bytes),
        }, indent=2))
        return 0
    if args.command == "sign":
        from .crypto.signatures import sign_record

        password = os.environ.get(args.password_env)
        if not password:
            raise ValueError(f"password environment variable {args.password_env!r} is missing or empty")
        record = sign_record(
            extract_record(args.artifact), private_key_path=args.key, password=password
        )
        output = embed_file(args.artifact, record, output_path=args.output)
        print(output)
        return 0
    if args.command == "attest":
        from .crypto.attestations import attest_report
        from .verification import verify_artifact as verify_proof

        password = os.environ.get(args.password_env)
        if not password:
            raise ValueError(
                f"password environment variable {args.password_env!r} is missing or empty"
            )
        report = verify_proof(
            args.artifact,
            required=args.require,
            source_tables=_source_table_arguments(args.source_table),
            decryption=_decryption_arguments(
                args, password_attribute="evidence_password_env"
            ),
            trust_store=args.trust_store,
            reproduction_report=args.reproduction_report,
        )
        if args.require and not report.valid:
            raise ValueError("cannot attest a report that failed its required meanings")
        record = attest_report(
            extract_record(args.artifact),
            report,
            private_key_path=args.key,
            password=password,
        )
        output = embed_file(args.artifact, record, output_path=args.output)
        print(output)
        return 0
    if args.command == "encrypt":
        from .crypto.encryption import encrypt_sections

        password = os.environ.get(args.password_env) if args.password_env else None
        if args.password_env and not password:
            raise ValueError(f"password environment variable {args.password_env!r} is missing or empty")
        recipients = None
        if args.recipient_file:
            recipients = json.loads(Path(args.recipient_file).read_text(encoding="utf-8"))
            if not isinstance(recipients, dict):
                raise ValueError("--recipient-file must contain a JSON object")
        if not password and not recipients:
            raise ValueError("encrypt requires --password-env or --recipient-file")
        record = encrypt_sections(
            extract_record(args.artifact),
            args.section,
            password=password,
            recipients=recipients,
        )
        output = embed_file(args.artifact, record, output_path=args.output)
        print(output)
        return 0
    if args.command == "decrypt":
        from .crypto.encryption import decrypt_sections

        output = Path(args.output)
        if output.exists() and not args.overwrite:
            raise FileExistsError(output)
        password = os.environ.get(args.password_env) if args.password_env else None
        if args.password_env and not password:
            raise ValueError(f"password environment variable {args.password_env!r} is missing or empty")
        recipient_private_key = None
        if args.recipient_key:
            if not args.recipient_password_env:
                raise ValueError(
                    "--recipient-password-env is required with --recipient-key"
                )
            recipient_password = os.environ.get(args.recipient_password_env)
            if not recipient_password:
                raise ValueError(
                    f"password environment variable {args.recipient_password_env!r} is missing or empty"
                )
            from .crypto.keys import load_recipient_private_key

            recipient_private_key = load_recipient_private_key(
                args.recipient_key, password=recipient_password
            )
        if not password and recipient_private_key is None:
            raise ValueError(
                "decrypt requires --password-env or --recipient-key"
            )
        values = decrypt_sections(
            extract_record(args.artifact),
            password=password,
            recipient_private_key=recipient_private_key,
        )
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(deterministic_json(values, indent=2) + "\n", encoding="utf-8")
        print(output)
        return 0
    if args.command == "trust":
        from .crypto.trust import TrustEntry, TrustPolicy, TrustStore

        if args.trust_command == "list":
            store = TrustStore.load(args.store)
            print(deterministic_json(store.to_dict(), indent=2))
            return 0
        store = TrustStore.load(args.store) if Path(args.store).exists() else TrustStore()
        if args.trust_command == "add":
            store.add(TrustEntry(
                args.fingerprint, args.label, scopes=args.scope or ["*"]
            ))
        elif args.trust_command == "revoke":
            store.revoke(args.fingerprint, revoked_at=args.at, replacement_fingerprint=args.replacement)
        elif args.trust_command == "remove":
            store.remove(args.fingerprint)
        elif args.trust_command == "set-policy":
            store.policy = TrustPolicy(
                required_scopes=args.scope,
                minimum_trusted_signatures=args.minimum,
                required_fingerprints=args.fingerprint,
            )
        store.save(args.store)
        print(args.store)
        return 0
    if args.command == "guard" and args.guard_command == "python":
        from .guard.python import launch_guarded_python

        completed = launch_guarded_python(
            args.script, policy_path=args.policy, arguments=args.arguments
        )
        return int(completed.returncode)
    if args.command == "broker" and args.broker_command == "promote":
        from .guard.broker import promote_candidate
        from .guard.policy import OutputPolicy

        policy = OutputPolicy.from_json(args.policy)
        if args.record:
            from .guard.broker import OutputBroker
            from .guard.workspace import GuardWorkspace

            receipt = OutputBroker(
                GuardWorkspace.create(args.workspace),
                args.destination,
                policy,
            ).prepare_and_promote(
                args.candidate,
                record_path=args.record,
                semantic_bindings_path=args.semantic_bindings,
                name=args.name,
            )
        else:
            receipt = promote_candidate(
                args.candidate,
                workspace=args.workspace,
                destination=args.destination,
                policy=policy,
                name=args.name,
            )
        print(deterministic_json({**receipt.to_dict(), "receipt_sha256": receipt.fingerprint()}, indent=2))
        return 0
    if args.command == "registry":
        from .evidence import graph_from_record
        from .recovery import recover_companion
        from .registry import LocalRegistry, registry_entry_for_artifact, sign_registry_entry

        registry = LocalRegistry.load(args.registry)
        if args.registry_command == "entry":
            password = os.environ.get(args.password_env)
            if not password:
                raise ValueError(f"password environment variable {args.password_env!r} is missing or empty")
            record = extract_record(args.artifact)
            graph = graph_from_record(record)
            entry = registry_entry_for_artifact(
                args.artifact,
                figure_id=record.figure_id,
                evidence_root=graph.root_sha256,
                profile=record.distribution_profile,
                recovery_locations=args.recovery,
            )
            registry.add(sign_registry_entry(entry, private_key_path=args.key, password=password))
            registry.save(args.registry)
            print(deterministic_json(entry.to_dict(), indent=2))
            return 0
        if args.registry_command == "resolve":
            resolved = registry.resolve(args.artifact, trust_store=args.trust_store)
            print(deterministic_json(
                {"match": resolved[0].to_dict(), "confidence": resolved[1]} if resolved else {"match": None},
                indent=2,
            ))
            return 0 if resolved else 1
        if args.registry_command == "recover":
            result = recover_companion(
                args.artifact,
                registry,
                args.output,
                trust_store=args.trust_store,
                overwrite=args.overwrite,
            )
            print(deterministic_json({
                "recovered_path": str(result.recovered_path), "figure_id": result.figure_id,
                "evidence_root": result.evidence_root, "confidence": result.confidence,
            }, indent=2))
            return 0
    raise AssertionError(args.command)


if __name__ == "__main__":
    raise SystemExit(main())
