from __future__ import annotations

import copy
import base64

import pytest

from reprofig import (
    TrustEntry,
    TrustPolicy,
    TrustStore,
    attach_evidence_graph,
    build_record,
    derive_profile,
)
from reprofig.crypto.encryption import decrypt_sections, encrypt_sections
from reprofig.crypto.keys import generate_signing_key
from reprofig.crypto.keys import (
    generate_recipient_key,
    load_recipient_private_key,
    recipient_public_bytes,
)
from reprofig.crypto.attestations import attest_report
from reprofig.crypto.signatures import sign_record, verify_record_signatures
from reprofig.crypto.trust import evaluate_record_trust
from reprofig.evidence import attach_evidence_graph as attach_graph
from reprofig.evidence import graph_from_record
from reprofig.schema import EvidenceSection, ScientificClaim
from reprofig.evidence import calculate_evidence_root
from reprofig.verification import ProofVerificationReport, verify_record_proof


def _master():
    return attach_evidence_graph(
        build_record(
            plotted_data=[
                {"subject": "participant-001", "group": "control", "value": 1.0},
                {"subject": "participant-002", "group": "treated", "value": 2.0},
            ],
            statistics=[{"test_id": "t1", "p": "0.0123456789", "n": 2}],
            column_classification={
                "subject": "private",
                "group": "safe",
                "value": "safe",
            },
        )
    )


def test_trust_requires_valid_signature_and_enforces_lifecycle(tmp_path):
    key = tmp_path / "trusted.pem"
    attacker = tmp_path / "attacker.pem"
    generate_signing_key(key, password="trusted password")
    generate_signing_key(attacker, password="attacker password")
    signed = sign_record(
        _master(), private_key_path=str(key), password="trusted password"
    )
    fingerprint = signed.extensions["proof"]["signatures"][0]["key_fingerprint"]
    store = TrustStore(
        [TrustEntry(fingerprint, "publication signer", scopes=["figure"])],
        TrustPolicy(required_scopes=["figure"], required_fingerprints=[fingerprint]),
    )
    assert any(check.status == "pass" for check in evaluate_record_trust(signed, store))

    forged = copy.deepcopy(signed)
    forged.extensions["proof"]["signatures"] = []
    forged = sign_record(
        forged, private_key_path=str(attacker), password="attacker password"
    )
    assert all(check.status == "fail" for check in evaluate_record_trust(forged, store))

    store.revoke(fingerprint, revoked_at="2000-01-01T00:00:00+00:00")
    assert any(check.status == "fail" for check in evaluate_record_trust(signed, store))


def test_signature_detects_section_substitution_and_duplicate_signers(tmp_path):
    key = tmp_path / "signing.pem"
    generate_signing_key(key, password="key password")
    signed = sign_record(
        _master(), private_key_path=str(key), password="key password"
    )
    assert all(check.status == "pass" for check in verify_record_signatures(signed))

    substituted = copy.deepcopy(signed)
    substituted.extensions["proof"]["sections"][0]["payload"] = {"attacker": True}
    assert any(check.status == "fail" for check in verify_record_signatures(substituted))

    duplicate = copy.deepcopy(signed)
    duplicate.extensions["proof"]["signatures"].append(
        copy.deepcopy(duplicate.extensions["proof"]["signatures"][0])
    )
    assert any("duplicate" in check.message for check in verify_record_signatures(duplicate))


def test_encryption_wrong_password_corruption_and_resource_limits_fail():
    master = _master()
    table_id = str(graph_from_record(master).sections[0].section_id)
    protected = encrypt_sections(master, [table_id], password="correct horse")
    with pytest.raises(Exception):
        decrypt_sections(protected, password="wrong battery")

    graph = graph_from_record(protected)
    corrupted_sections = [copy.deepcopy(section) for section in graph.sections]
    encrypted = next(section for section in corrupted_sections if section.encrypted)
    encrypted.payload["ciphertext"] = "AAAA"
    encrypted.sha256 = None
    corrupted = attach_graph(protected, sections=corrupted_sections, claims=graph.claims)
    with pytest.raises(ValueError, match="ciphertext integrity"):
        decrypt_sections(corrupted, password="correct horse")

    expensive_sections = [copy.deepcopy(section) for section in graph.sections]
    encrypted = next(section for section in expensive_sections if section.encrypted)
    encrypted.payload["envelopes"]["password"]["memory_cost_kib"] = 999_999_999
    encrypted.sha256 = None
    expensive = attach_graph(protected, sections=expensive_sections, claims=graph.claims)
    with pytest.raises(ValueError, match="Argon2id envelope parameters"):
        decrypt_sections(expensive, password="correct horse")


def test_encrypted_public_profile_policies_are_one_way_and_private_safe():
    master = _master()
    table_id = str(graph_from_record(master).sections[0].section_id)
    protected = encrypt_sections(master, [table_id], password="master password")

    dropped = derive_profile(
        protected, "minimal_public", encrypted_section_policy="drop"
    )
    assert not any(section.encrypted for section in graph_from_record(dropped).sections)
    assert "participant-001" not in dropped.to_json()

    retained = derive_profile(
        protected, "minimal_public", encrypted_section_policy="retain_ciphertext"
    )
    assert any(section.encrypted for section in graph_from_record(retained).sections)
    plaintext = decrypt_sections(retained, password="master password")
    assert any("participant-001" in str(value) for value in plaintext.values())

    reencrypted = derive_profile(
        protected,
        "public",
        safe_columns=["group", "value"],
        encrypted_section_policy="decrypt_transform_reencrypt",
        decryption={"password": "master password"},
        reencrypt_password="public-review password",
    )
    serialized = reencrypted.to_json()
    assert "participant-001" not in serialized
    public_plaintext = decrypt_sections(
        reencrypted, password="public-review password"
    )
    assert "participant-001" not in str(public_plaintext)
    assert "control" in str(public_plaintext)


def test_named_recipient_can_decrypt_but_unrelated_key_cannot(tmp_path):
    recipient_path = tmp_path / "reviewer.pem"
    unrelated_path = tmp_path / "unrelated.pem"
    generate_recipient_key(recipient_path, password="recipient password")
    generate_recipient_key(unrelated_path, password="unrelated password")
    recipient = load_recipient_private_key(
        recipient_path, password="recipient password"
    )
    public = base64.b64encode(recipient_public_bytes(recipient)).decode("ascii")
    master = _master()
    table_id = str(graph_from_record(master).sections[0].section_id)
    protected = encrypt_sections(
        master, [table_id], recipients={"journal-reviewer": public}
    )
    plaintext = decrypt_sections(protected, recipient_private_key=recipient)
    assert "participant-001" in str(plaintext[table_id])
    unrelated = load_recipient_private_key(
        unrelated_path, password="unrelated password"
    )
    with pytest.raises(ValueError, match="no recipient envelope"):
        decrypt_sections(protected, recipient_private_key=unrelated)


def test_ciphertext_cannot_be_swapped_between_figure_identities():
    first = _master()
    second = _master()
    first_id = str(graph_from_record(first).sections[0].section_id)
    second_id = str(graph_from_record(second).sections[0].section_id)
    assert first_id == second_id
    envelope_password = f"test-only-{first_id[:8]}"
    protected_first = encrypt_sections(
        first, [first_id], password=envelope_password
    )
    protected_second = encrypt_sections(
        second, [second_id], password=envelope_password
    )
    first_graph = graph_from_record(protected_first)
    second_graph = graph_from_record(protected_second)
    donor = next(section for section in first_graph.sections if section.encrypted)
    sections = [copy.deepcopy(section) for section in second_graph.sections]
    target = next(section for section in sections if section.encrypted)
    target.payload = copy.deepcopy(donor.payload)
    target.sha256 = None
    swapped = attach_graph(
        protected_second, sections=sections, claims=second_graph.claims
    )
    with pytest.raises(Exception):
        decrypt_sections(swapped, password=envelope_password)


def test_attestation_binds_a_deterministic_report_hash(tmp_path):
    key = tmp_path / "attester.pem"
    generate_signing_key(key, password="attestation password")
    record = _master()
    report = ProofVerificationReport(
        checks=[], required=[], integrity={"valid": True}
    )
    attested = attest_report(
        record,
        report,
        private_key_path=str(key),
        password="attestation password",
    )
    checks = verify_record_proof(attested, requested=["attested"])
    assert any(check.meaning == "attested" and check.status == "pass" for check in checks)
    changed = copy.deepcopy(attested)
    changed.extensions["proof"]["signatures"][0]["policy_context"][
        "verification_report_sha256"
    ] = "0" * 64
    checks = verify_record_proof(changed, requested=["attested"])
    assert any(check.meaning == "attested" and check.status == "fail" for check in checks)


def test_evidence_graph_rejects_missing_dependencies_cycles_and_claims():
    first = EvidenceSection(section_id="first", kind="table", payload={"x": 1})
    missing = EvidenceSection(
        section_id="missing", kind="derived", payload={}, dependencies=["absent"]
    )
    with pytest.raises(ValueError, match="missing dependencies"):
        calculate_evidence_root("figure", "reprofig/1", [first, missing])

    left = EvidenceSection(
        section_id="left", kind="derived", payload={}, dependencies=["right"]
    )
    right = EvidenceSection(
        section_id="right", kind="derived", payload={}, dependencies=["left"]
    )
    with pytest.raises(ValueError, match="cycle"):
        calculate_evidence_root("figure", "reprofig/1", [left, right])

    claim = ScientificClaim(text="unsupported claim", evidence_ids=["absent"])
    with pytest.raises(ValueError, match="missing evidence"):
        calculate_evidence_root("figure", "reprofig/1", [first], [claim])
