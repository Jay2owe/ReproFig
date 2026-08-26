"""Build one portable bundle for every ReproFig verification meaning."""

from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from reprofig import (
    TransformationSpec,
    attach_evidence_graph,
    attest_report,
    embed_file,
    extract_artifact,
    extract_record,
    reproduce_figure,
    table_from_data,
    verify_proof,
)
from reprofig.crypto.keys import (
    generate_signing_key,
    load_signing_private_key,
    public_key_fingerprint,
    signing_public_bytes,
)
from reprofig.crypto.signatures import sign_record
from reprofig.crypto.trust import TrustEntry, TrustPolicy, TrustStore


DEMO_ROOT = Path(__file__).resolve().parents[1]
INPUT = DEMO_ROOT / "input" / "raw-observations.csv"
PRODUCER = DEMO_ROOT / "code" / "plot.py"
FIGURE_NAME = "raw-user-input-comparison.svg"
CLAIM = "In a small synthetic dataset, treatment observations are higher than control observations."
GRAMMAR = "dot/interval plot"
SOURCE_ID = "source:raw-user-input"
OVERVIEW_ROOT = DEMO_ROOT / "verification-layers-overview"
OVERVIEW_SOURCE = DEMO_ROOT / "input" / "verification-layers.csv"
OVERVIEW_PRODUCER = DEMO_ROOT / "code" / "layers_overview.py"
OVERVIEW_FIGURE = "verification-layers.svg"
OVERVIEW_CLAIM = (
    "ReproFig separates traceability from nine verification meanings so each "
    "claim can be checked and reported explicitly."
)
LEVELS = {
    "00-traceable-carrier": [],
    "01-internally-consistent": ["internally_consistent"],
    "02-statistics-reproduced": [
        "internally_consistent",
        "statistics_reproduced",
    ],
    "03-statistics-independently-verified": [
        "internally_consistent",
        "statistics_independently_verified",
    ],
    "04-figure-reproduced": ["internally_consistent", "figure_reproduced"],
    "05-display-verified": ["internally_consistent", "display_verified"],
    "06-source-linked": ["internally_consistent", "source_linked"],
    "07-signature-valid": ["internally_consistent", "signature_valid"],
    "08-signer-trusted": [
        "internally_consistent",
        "signature_valid",
        "signer_trusted",
    ],
    "09-attested": [
        "internally_consistent",
        "statistics_independently_verified",
        "figure_reproduced",
        "display_verified",
        "source_linked",
        "signature_valid",
        "signer_trusted",
        "attested",
    ],
}

LAYER_DETAILS = {
    "00-traceable-carrier": (
        "Traceable carrier",
        "The figure carries its exact values, complete statistical record, copied-input hash and standalone producer.",
        "This baseline is inspectable but makes no formal proof claim.",
    ),
    "01-internally-consistent": (
        "Internally consistent",
        "The carrier, embedded record, evidence sections and evidence-root hash agree.",
        "This does not establish that the source or statistical choices are correct.",
    ),
    "02-statistics-reproduced": (
        "Statistics reproduced",
        "The declared numbers match a rerun through the recorded producer-equivalent calculation route.",
        "This is repeatability through the same route, not an independent implementation.",
    ),
    "03-statistics-independently-verified": (
        "Statistics independently verified",
        "ReproFig's reference Welch test matches a separately implemented Python-standard-library calculation.",
        "This verifies the declared calculation, not whether Welch's test was the right scientific choice.",
    ),
    "04-figure-reproduced": (
        "Figure reproduced",
        "The trusted producer reruns in a temporary workspace and saves a separate matching figure.",
        "Producer execution is explicit and does not prove the inputs were honestly collected.",
    ),
    "05-display-verified": (
        "Display verified",
        "The visible dots, means, comparison bracket and p-value text match their semantic bindings.",
        "Unbound decoration is outside this check.",
    ),
    "06-source-linked": (
        "Source linked",
        "An executable declared transformation reconstructs the exact plotted table from the copied raw CSV.",
        "This does not establish that the supplied observations were honestly collected.",
    ),
    "07-signature-valid": (
        "Signature valid",
        "An Ed25519 signature mathematically approves the exact evidence root and visible binding.",
        "A valid signature alone does not identify or trust its signer.",
    ),
    "08-signer-trusted": (
        "Signer trusted",
        "The valid signature's public-key fingerprint satisfies an explicit local trust-store policy.",
        "Trust is local to that policy, not a universal identity claim.",
    ),
    "09-attested": (
        "Attested full stack",
        "A trusted signer approves a deterministic report after internal, independent, display, source, signature and trust checks pass.",
        "The demonstration key is temporary and does not represent a real person or institution.",
    ),
}

OBSOLETE_LEVELS = (
    "01-traceable",
    "02-independently-verified",
    "03-source-linked-and-signed",
    "02-reproduced",
    "03-independently-verified",
    "04-display-verified",
    "05-source-linked",
    "06-signature-valid",
    "07-signer-trusted",
    "08-attested",
)


def _json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _plot_environment() -> dict[str, str]:
    environment = os.environ.copy()
    scripts = environment.get("PLOT_THAT_SCRIPTS")
    if scripts:
        environment["PYTHONPATH"] = os.pathsep.join(
            value
            for value in (scripts, environment.get("PYTHONPATH", ""))
            if value
        )
    return environment


def _write_sources(
    root: Path,
    copied: Path,
    *,
    original_path: str = "input/raw-observations.csv",
    description: str = "synthetic user-entered table",
) -> None:
    stat = copied.stat()
    with (root / "data" / "sources.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "original_path",
                "copied_path",
                "file_name",
                "modification_time",
                "byte_size",
                "sha256",
                "public_uri",
            ],
            lineterminator="\n",
        )
        writer.writeheader()
        writer.writerow(
            {
                "original_path": original_path,
                "copied_path": f"data/src/{copied.name}",
                "file_name": copied.name,
                "modification_time": datetime.fromtimestamp(
                    stat.st_mtime, tz=timezone.utc
                ).isoformat(timespec="seconds"),
                "byte_size": stat.st_size,
                "sha256": _sha256(copied),
                "public_uri": "",
            }
        )
    (root / "data" / "sources.md").write_text(
        "# Source index\n\n"
        f"`data/src/{copied.name}` is an exact copy of the {description} at "
        f"`{original_path}`. Its byte size and SHA-256 digest are recorded in "
        "`sources.csv`.\n",
        encoding="utf-8",
    )


def _prepare_level(name: str) -> Path:
    root = DEMO_ROOT / name
    if root.exists():
        for attempt in range(20):
            try:
                shutil.rmtree(root)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.5)
    for part in (
        "code",
        "data/der",
        "data/src",
        "fig",
        "preview",
        "unpacked",
        "verification",
    ):
        (root / part).mkdir(parents=True, exist_ok=True)
    copied = root / "data" / "src" / INPUT.name
    shutil.copy2(INPUT, copied)
    shutil.copy2(PRODUCER, root / "code" / "plot.py")
    _write_sources(root, copied)
    title, passing_claim, boundary = LAYER_DETAILS[name]
    number = int(name.split("-", 1)[0])
    requested = LEVELS[name]
    requested_text = ", ".join(f"`{meaning}`" for meaning in requested) or "none"
    (root / "README.md").write_text(
        f"# Layer {number} of 9 - {title}\n\n"
        f"{passing_claim}\n\n"
        f"Required verification meanings: {requested_text}.\n\n"
        f"Boundary: {boundary}\n\n"
        "Open `preview/raw-user-input-comparison.png` for the visible figure, "
        "`verification/meaning-summary.csv` for the compact result, and "
        "`unpacked/` for the evidence recovered from the Scalable Vector "
        "Graphics carrier.\n",
        encoding="utf-8",
    )
    return root


def _run_python_producer(root: Path) -> None:
    for attempt in range(12):
        result = subprocess.run(
            [sys.executable, "code/plot.py"],
            cwd=root,
            env=_plot_environment(),
            text=True,
            capture_output=True,
        )
        if result.returncode == 0:
            return
        output = f"{result.stdout}\n{result.stderr}"
        if "PermissionError" not in output or attempt == 11:
            raise RuntimeError(output.strip())
        time.sleep(0.75)
    raise AssertionError("producer retry loop exhausted")


def _run_producer(root: Path) -> None:
    _run_python_producer(root)


def _prepare_overview() -> Path:
    root = OVERVIEW_ROOT
    if root.exists():
        for attempt in range(20):
            try:
                shutil.rmtree(root)
                break
            except PermissionError:
                if attempt == 19:
                    raise
                time.sleep(0.5)
    for part in ("code", "data/der", "data/src", "fig", "preview", "unpacked"):
        (root / part).mkdir(parents=True, exist_ok=True)
    copied = root / "data" / "src" / OVERVIEW_SOURCE.name
    shutil.copy2(OVERVIEW_SOURCE, copied)
    shutil.copy2(OVERVIEW_PRODUCER, root / "code" / "plot.py")
    _write_sources(
        root,
        copied,
        original_path="input/verification-layers.csv",
        description="verification-layer definition table",
    )
    (root / "README.md").write_text(
        "# ReproFig verification layers overview\n\n"
        "This timeline shows the traceable baseline and all nine formal "
        "verification meanings. Each row states the narrow claim established "
        "by a pass and the boundary that remains.\n\n"
        "The exact displayed wording is in `data/der/figure_data.csv`; the "
        "standalone Matplotlib producer is `code/plot.py`.\n",
        encoding="utf-8",
    )
    return root


def _run_overview(root: Path) -> None:
    _run_python_producer(root)


def _source_table(root: Path):
    return table_from_data(
        (root / "data" / "src" / "raw-observations.csv").read_bytes(),
        name="raw-user-input",
        purpose="verification_source",
    )


def _portable_report(report):
    relative = f"fig/{FIGURE_NAME}"
    report.path = relative
    if isinstance(report.integrity, dict):
        report.integrity = {**report.integrity, "path": relative}
    return report


def _enhance_level(root: Path) -> None:
    figure = root / "fig" / FIGURE_NAME
    required = LEVELS[root.name]
    if "source_linked" in required:
        record = extract_record(figure)
        target = next(
            table for table in record.data_tables if table.name == "figure_data"
        )
        transformation = TransformationSpec(
            operation="select",
            input_table_ids=[SOURCE_ID],
            output_table_id=f"table:{target.sha256}",
            parameters={"columns": ["observation_id", "group", "response"]},
        )
        proof = dict(record.extensions.get("proof") or {})
        proof["transformations"] = [transformation.to_dict()]
        for volatile in ("schema", "sections", "root_sha256", "signatures"):
            proof.pop(volatile, None)
        record.extensions["proof"] = proof
        record = attach_evidence_graph(record)
        embed_file(figure, record, output_path=figure)

    if "signature_valid" not in required:
        if "figure_reproduced" in required:
            _reproduce_level(root)
        return

    with tempfile.TemporaryDirectory(prefix="reprofig-general-example-") as temporary:
        private_key = Path(temporary) / "demo-signing-key.pem"
        password = secrets.token_urlsafe(24)
        generate_signing_key(private_key, password=password, overwrite=True)
        private = load_signing_private_key(private_key, password=password)
        public_bytes = signing_public_bytes(private)
        fingerprint = public_key_fingerprint(public_bytes)
        _json(
            root / "verification" / "signer-public.json",
            {
                "algorithm": "Ed25519",
                "fingerprint": fingerprint,
                "public_key_base64": base64.b64encode(public_bytes).decode("ascii"),
                "private_key_included": False,
            },
        )
        signed = sign_record(
            extract_record(figure),
            private_key_path=str(private_key),
            password=password,
            policy_context={"purpose": "synthetic verification-level demonstration"},
        )
        embed_file(figure, signed, output_path=figure)

        trust_path = root / "verification" / "trust-store.json"
        if "signer_trusted" in required:
            trust_store = TrustStore(
                entries=[
                    TrustEntry(
                        fingerprint=fingerprint,
                        label="ReproFig synthetic-example signer",
                        scopes=["figure"],
                        metadata={"purpose": "local demonstration only"},
                    )
                ],
                policy=TrustPolicy(
                    required_scopes=["figure"],
                    minimum_trusted_signatures=1,
                    required_fingerprints=[fingerprint],
                ),
            )
            trust_store.save(trust_path)

        if "figure_reproduced" in required:
            _reproduce_level(root)

        if "attested" in required:
            required_before_attestation = [
                meaning for meaning in required if meaning != "attested"
            ]
            report = verify_proof(
                figure,
                required=required_before_attestation,
                source_tables={SOURCE_ID: _source_table(root)},
                trust_store=trust_path,
                reproduction_report=(
                    root / "verification" / "reproduction-report.json"
                ),
            )
            report = _portable_report(report)
            if not report.valid:
                raise RuntimeError(report.to_json(indent=2))
            attested = attest_report(
                extract_record(figure),
                report,
                private_key_path=str(private_key),
                password=password,
            )
            embed_file(figure, attested, output_path=figure)


def _reproduce_level(root: Path) -> None:
    report = reproduce_figure(
        root / "fig" / FIGURE_NAME,
        bundle_root=root,
        output_dir=root / "verification" / "reproduced",
        report_path=root / "verification" / "reproduction-report.json",
        execute_trusted_producer=True,
        overwrite=True,
    )
    if not report.valid:
        raise RuntimeError(report.to_json(indent=2))


def _register(root: Path) -> None:
    register_value = os.environ.get("PLOT_THAT_REGISTER")
    if not register_value:
        scripts = os.environ.get("PLOT_THAT_SCRIPTS")
        register_value = str(Path(scripts) / "register.py") if scripts else ""
    register = Path(register_value) if register_value else None
    if register is None or not register.is_file():
        raise FileNotFoundError(
            "--register needs PLOT_THAT_REGISTER or PLOT_THAT_SCRIPTS"
        )
    command = [
        sys.executable,
        str(register),
        "add",
        str(root),
        "--claim",
        CLAIM,
        "--grammar",
        GRAMMAR,
        "--producer",
        "code/plot.py",
        "--statistics-status",
        "complete",
        "--figure",
        f"fig/{FIGURE_NAME}",
    ]
    if LEVELS[root.name]:
        command.append("--proof")
    subprocess.run(command, check=True)


def _register_overview(root: Path) -> None:
    register_value = os.environ.get("PLOT_THAT_REGISTER")
    if not register_value:
        scripts = os.environ.get("PLOT_THAT_SCRIPTS")
        register_value = str(Path(scripts) / "register.py") if scripts else ""
    register = Path(register_value) if register_value else None
    if register is None or not register.is_file():
        raise FileNotFoundError(
            "--register needs PLOT_THAT_REGISTER or PLOT_THAT_SCRIPTS"
        )
    subprocess.run(
        [
            sys.executable,
            str(register),
            "add",
            str(root),
            "--claim",
            OVERVIEW_CLAIM,
            "--grammar",
            "timeline",
            "--producer",
            "code/plot.py",
            "--statistics-status",
            "not_applicable",
            "--figure",
            f"fig/{OVERVIEW_FIGURE}",
        ],
        check=True,
    )


def _verify_level(root: Path):
    kwargs = {}
    required = LEVELS[root.name]
    if "source_linked" in required:
        kwargs["source_tables"] = {SOURCE_ID: _source_table(root)}
    if "signer_trusted" in required:
        kwargs["trust_store"] = root / "verification" / "trust-store.json"
    if "figure_reproduced" in required:
        kwargs["reproduction_report"] = (
            root / "verification" / "reproduction-report.json"
        )
    report = verify_proof(
        root / "fig" / FIGURE_NAME,
        required=required,
        **kwargs,
    )
    report = _portable_report(report)
    if not report.valid:
        raise RuntimeError(report.to_json(indent=2))
    return report


def _write_report(root: Path, report) -> None:
    value = report.to_dict()
    _json(root / "verification" / "report.json", value)
    with (root / "verification" / "meaning-summary.csv").open(
        "w", newline="", encoding="utf-8"
    ) as handle:
        writer = csv.writer(handle, lineterminator="\n")
        writer.writerow(["meaning", "status"])
        writer.writerows(sorted(value["meanings"].items()))


def _unpack(root: Path) -> None:
    _extract_without_sync_race(root / "fig" / FIGURE_NAME, root / "unpacked")
    shutil.copy2(
        root / "fig" / "preview.png",
        root / "preview" / "raw-user-input-comparison.png",
    )


def _unpack_overview(root: Path) -> None:
    _extract_without_sync_race(root / "fig" / OVERVIEW_FIGURE, root / "unpacked")
    shutil.copy2(
        root / "fig" / "preview.png",
        root / "preview" / "verification-layers.png",
    )


def _extract_without_sync_race(figure: Path, destination: Path) -> None:
    """Avoid cloud-sync locks on ReproFig's short-lived extraction directory."""

    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="reprofig-demo-extract-") as temporary:
        outputs = extract_artifact(figure, temporary, overwrite=True)
        for source in outputs:
            target = destination / source.name
            for attempt in range(12):
                try:
                    shutil.copy2(source, target)
                    break
                except PermissionError:
                    if attempt == 11:
                        raise
                    time.sleep(0.75)


def _finalize(roots: list[Path], overview: Path) -> None:
    summary = {
        "claim": CLAIM,
        "grammar": GRAMMAR,
        "source_input": "input/raw-observations.csv",
        "producer": "code/plot.py",
        "dependencies": ["matplotlib", "reprofig[proof]"],
        "levels": {},
        "private_key": "generated in a temporary directory and deleted",
        "overview": {
            "folder": overview.name,
            "figure": f"{overview.name}/fig/{OVERVIEW_FIGURE}",
            "figure_id": extract_record(
                overview / "fig" / OVERVIEW_FIGURE
            ).figure_id,
        },
    }
    for root in roots:
        report = _verify_level(root)
        _write_report(root, report)
        _unpack(root)
        record = extract_record(root / "fig" / FIGURE_NAME)
        summary["levels"][root.name] = {
            "folder": root.name,
            "figure": f"{root.name}/fig/{FIGURE_NAME}",
            "figure_id": record.figure_id,
            "required": LEVELS[root.name],
            "valid": report.valid,
        }
    _unpack_overview(overview)
    _json(DEMO_ROOT / "build-summary.json", summary)


def build(*, register: bool = False) -> None:
    required_files = (INPUT, PRODUCER, OVERVIEW_SOURCE, OVERVIEW_PRODUCER)
    if not all(path.is_file() for path in required_files):
        raise FileNotFoundError("the demonstration inputs and producers must be present")
    for obsolete in OBSOLETE_LEVELS:
        path = DEMO_ROOT / obsolete
        if path.exists():
            for attempt in range(20):
                try:
                    shutil.rmtree(path)
                    break
                except PermissionError:
                    if attempt == 19:
                        raise
                    time.sleep(0.5)

    roots = []
    for name in LEVELS:
        root = _prepare_level(name)
        _run_producer(root)
        _enhance_level(root)
        roots.append(root)
    overview = _prepare_overview()
    _run_overview(overview)
    if register:
        for root in roots:
            _register(root)
        _register_overview(overview)

    _finalize(roots, overview)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--register",
        action="store_true",
        help="register every completed bundle with the plot-that artifact register",
    )
    parser.add_argument(
        "--finalize-only",
        action="store_true",
        help="verify and unpack existing bundles without regenerating or registering",
    )
    args = parser.parse_args()
    if args.finalize_only:
        _finalize([DEMO_ROOT / name for name in LEVELS], OVERVIEW_ROOT)
    else:
        build(register=args.register)


if __name__ == "__main__":
    main()
