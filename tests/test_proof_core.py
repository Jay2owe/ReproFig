from __future__ import annotations

import copy

import matplotlib.pyplot as plt

from reprofig import (
    StatisticalSpecification,
    attach_evidence_graph,
    bind_artist,
    build_record,
    save_figure,
    verify_proof,
)
from reprofig.crypto.encryption import decrypt_sections, encrypt_sections
from reprofig.crypto.keys import generate_signing_key
from reprofig.crypto.signatures import sign_record, verify_record_signatures
from reprofig.evidence import graph_from_record
from reprofig.stats.engine import verify_record_statistics


def test_evidence_root_detects_current_record_tampering():
    record = build_record(plotted_data=[{"value": 1}, {"value": 2}])
    proof = attach_evidence_graph(record)
    assert graph_from_record(proof).root_sha256 == proof.extensions["proof"]["root_sha256"]
    changed = copy.deepcopy(proof)
    changed.data_tables[0].contents = "value\n9\n"
    changed.data_tables[0].sha256 = "0" * 64
    try:
        graph_from_record(changed)
    except ValueError as exc:
        assert "current record evidence" in str(exc) or "disagrees with current record" in str(exc)
    else:
        raise AssertionError("tampered current record was accepted")


def test_independent_welch_t_specification():
    record = build_record(statistics_status="complete", statistics=[{"test_id": "t1", "p": 0.021311641128756727}])
    specification = StatisticalSpecification(
        statistic_id="t1",
        algorithm_id="welch-t/v1",
        inputs={"values_a": [1, 2, 3, 4], "values_b": [3, 4, 5, 8]},
        parameters={
            "alternative": "two_sided",
            "missing_policy": "omit",
            "confidence_level": 0.95,
        },
        expected={"statistic": -1.9867985355975655, "p_value": 0.10483311735559388},
        tolerances={"*": {"absolute": 1e-12, "relative": 1e-10}},
    )
    record.extensions["proof"] = {"statistical_specifications": [specification.to_dict()]}
    record = attach_evidence_graph(record)
    checks = verify_record_statistics(record)
    assert checks[0].status == "pass"
    assert checks[0].meaning == "independently_verified"


def test_signature_and_selective_encryption(tmp_path):
    record = attach_evidence_graph(build_record(plotted_data=[{"subject": "A", "value": 1}]))
    encrypted = encrypt_sections(record, [record.extensions["proof"]["sections"][0]["section_id"]], password="secret")
    assert b"subject" not in str(encrypted.extensions["proof"]["sections"][0]["payload"]).encode()
    decrypted = decrypt_sections(encrypted, password="secret")
    assert any("subject" in str(value) for value in decrypted.values())

    key = tmp_path / "signing.pem"
    generate_signing_key(key, password="key password")
    signed = sign_record(encrypted, private_key_path=str(key), password="key password")
    assert all(check.status == "pass" for check in verify_record_signatures(signed))
    tampered = copy.deepcopy(signed)
    tampered.extensions["proof"]["sections"][0]["payload"]["ciphertext"] = "AAAA"
    assert any(check.status == "fail" for check in verify_record_signatures(tampered))


def test_semantic_svg_visual_verification(tmp_path):
    figure, axes = plt.subplots()
    line, = axes.plot([0, 1, 2], [1, 3, 2])
    bind_artist(line, semantic_id="series-a", table_id=None, columns=["x", "y"])
    text = axes.text(1, 3.2, "p = 0.01")
    bind_artist(text, semantic_id="p-label", statistic_id=None, formatter_id="exact/v1")
    output = tmp_path / "proof.svg"
    save_figure(
        figure,
        output,
        plotted_data=[{"x": 0, "y": 1}, {"x": 1, "y": 3}, {"x": 2, "y": 2}],
        statistics=[{"p": "0.01"}],
        proof=True,
    )
    plt.close(figure)
    report = verify_proof(output, required=["display_verified"])
    assert report.valid, report.to_dict()
