from __future__ import annotations

from PIL import Image
import pytest

from reprofig import attach_evidence_graph, build_record, derive_profile
from reprofig.artifacts import embed_file, extract_record
from reprofig.crypto.keys import generate_signing_key
from reprofig.crypto.trust import TrustEntry, TrustStore
from reprofig.evidence import graph_from_record
from reprofig.guard.broker import OutputBroker
from reprofig.guard.policy import OutputPolicy
from reprofig.guard.workspace import GuardWorkspace
from reprofig.guard.python import guarded_python
from reprofig.recovery import recover_companion
from reprofig.registry import (
    LocalRegistry,
    registry_entry_for_artifact,
    sign_registry_entry,
)


def _record():
    return attach_evidence_graph(
        build_record(
            plotted_data=[{"group": "A", "value": 1.0}],
            column_classification={"group": "safe", "value": "safe"},
        )
    )


def test_broker_promotes_only_valid_contained_candidates(tmp_path):
    workspace = GuardWorkspace.create(tmp_path / "workspace")
    destination = tmp_path / "published"
    policy = OutputPolicy(
        permitted_formats=["svg"],
        required_meanings=["internally_consistent"],
        destination=str(destination),
    )
    broker = OutputBroker(workspace, destination, policy)
    source = workspace.scratch / "source.svg"
    source.write_text('<svg xmlns="http://www.w3.org/2000/svg"><path d="M0 0"/></svg>')
    candidate = workspace.candidates / "figure.svg"
    embed_file(source, _record(), output_path=candidate)

    receipt = broker.promote(candidate)
    assert receipt.final_sha256 == receipt.candidate_sha256
    assert (destination / "figure.svg").is_file()

    outside = tmp_path / "outside.svg"
    outside.write_text(source.read_text())
    with pytest.raises(ValueError, match="outside the controlled"):
        broker.promote(outside)
    with pytest.raises(ValueError, match="plain filename"):
        broker.promote(candidate, name="../escape.svg")


def test_language_neutral_broker_prepares_record_before_promotion(tmp_path):
    workspace = GuardWorkspace.create(tmp_path / "workspace")
    destination = tmp_path / "published"
    policy = OutputPolicy(
        permitted_formats=["svg"],
        required_meanings=["internally_consistent"],
        destination=str(destination),
    )
    candidate = workspace.candidates / "adapter-output.svg"
    candidate.write_text('<svg xmlns="http://www.w3.org/2000/svg"><circle r="2"/></svg>')
    source_record = _record()
    record_path = workspace.scratch / "figure-record.json"
    record_path.write_text(source_record.to_json(indent=2), encoding="utf-8")

    OutputBroker(workspace, destination, policy).prepare_and_promote(
        candidate, record_path=record_path
    )
    recovered = extract_record(destination / candidate.name)
    assert recovered.figure_id == source_record.figure_id
    assert graph_from_record(recovered).root_sha256


def test_broker_failure_leaves_destination_unchanged(tmp_path):
    workspace = GuardWorkspace.create(tmp_path / "workspace")
    destination = tmp_path / "published"
    broker = OutputBroker(
        workspace,
        destination,
        OutputPolicy(
            permitted_formats=["svg"],
            required_meanings=["internally_consistent"],
            destination=str(destination),
        ),
    )
    invalid = workspace.candidates / "invalid.svg"
    invalid.write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
    with pytest.raises(RuntimeError, match="carrier/profile"):
        broker.promote(invalid)
    assert list(destination.iterdir()) == []


def test_trusted_registry_recovers_stripped_public_artifact(tmp_path):
    stripped = tmp_path / "stripped.png"
    Image.new("RGB", (16, 16), "navy").save(stripped)
    public = derive_profile(
        _record(), "public", safe_columns=["group", "value"]
    )
    companion = tmp_path / "companion.png"
    embed_file(stripped, public, output_path=companion)

    key = tmp_path / "registry.pem"
    generate_signing_key(key, password="registry password")
    entry = registry_entry_for_artifact(
        stripped,
        figure_id=public.figure_id,
        evidence_root=graph_from_record(public).root_sha256,
        profile="public",
        recovery_locations=[companion.name],
    )
    sign_registry_entry(
        entry, private_key_path=str(key), password="registry password"
    )
    registry_path = tmp_path / "registry.json"
    registry = LocalRegistry()
    registry.add(entry)
    registry.save(registry_path)
    trust = TrustStore(
        [TrustEntry(entry.signer_fingerprint or "", "registry", scopes=["registry"])]
    )

    output = tmp_path / "recovered.png"
    result = recover_companion(
        stripped, registry, output, trust_store=trust
    )
    assert result.confidence == "exact_carrier_hash"
    assert extract_record(output).figure_id == public.figure_id

    changed = entry.to_dict()
    changed["recovery_locations"] = ["attacker.png"]
    with pytest.raises(ValueError, match="signature"):
        LocalRegistry().add(type(entry).from_dict(changed))

    registry.entries[0].revoked = True
    assert registry.resolve(stripped, trust_store=trust) is None


def test_registry_rejects_private_and_traversing_locations(tmp_path):
    artifact = tmp_path / "figure.png"
    Image.new("RGB", (2, 2), "white").save(artifact)
    with pytest.raises(ValueError, match="public profiles"):
        registry_entry_for_artifact(
            artifact,
            figure_id="figure",
            evidence_root="0" * 64,
            profile="master",
            recovery_locations=["companion.png"],
        )
    with pytest.raises(ValueError, match="stay below"):
        registry_entry_for_artifact(
            artifact,
            figure_id="figure",
            evidence_root="0" * 64,
            profile="public",
            recovery_locations=["../private/companion.png"],
        )


def test_scoped_python_guard_intercepts_and_restores_matplotlib(tmp_path):
    import matplotlib.figure
    import matplotlib.pyplot as plt

    destination = tmp_path / "guarded"
    destination.mkdir()
    policy = OutputPolicy(
        permitted_formats=["png"],
        required_meanings=["internally_consistent"],
        destination=str(destination),
    )
    original = matplotlib.figure.Figure.savefig
    log = []
    figure, axes = plt.subplots()
    axes.plot([0, 1], [1, 2])
    with guarded_python(policy, audit_log=log):
        figure.savefig(destination / "figure.png")
        with pytest.raises(PermissionError, match="forbidden"):
            figure.savefig(destination / "figure.pdf")
    plt.close(figure)
    assert matplotlib.figure.Figure.savefig is original
    assert log[0]["valid"] is True
    recovered = extract_record(destination / "figure.png")
    assert recovered.extensions["proof"]["root_sha256"]


def test_strict_python_guard_removes_output_that_misses_required_meaning(tmp_path):
    import matplotlib.pyplot as plt

    destination = tmp_path / "guarded"
    destination.mkdir()
    policy = OutputPolicy(
        permitted_formats=["png"],
        required_meanings=["independently_verified"],
        destination=str(destination),
    )
    figure, axes = plt.subplots()
    axes.plot([0, 1], [1, 2])
    target = destination / "rejected.png"
    with guarded_python(policy):
        with pytest.raises(RuntimeError, match="failed required"):
            figure.savefig(target)
    plt.close(figure)
    assert not target.exists()
