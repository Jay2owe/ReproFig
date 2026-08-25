from pathlib import Path

from reprofig import FigureRecord, validate_record


def test_versioned_fixture_is_package_neutral_and_ignores_unknown_optional_fields():
    fixture = Path(__file__).parent / "fixtures" / "figure-record-v1.json"
    record = FigureRecord.from_json(fixture.read_bytes())
    assert record.schema == "reprofig/1"
    assert record.producer["package"] == "other-analysis-example"
    assert "pyflash" not in record.to_json().lower()
    assert validate_record(record).valid
