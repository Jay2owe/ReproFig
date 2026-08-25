import shutil
import subprocess
from pathlib import Path

import pandas as pd
import pytest

from reprofig import build_record, embed_record, extract_record


def _inkscape_executable():
    discovered = shutil.which("inkscape")
    if discovered:
        return discovered
    for candidate in (
        Path("C:/Program Files/Inkscape/bin/inkscape.exe"),
        Path("C:/Program Files/Inkscape/inkscape.exe"),
        Path("C:/Program Files (x86)/Inkscape/bin/inkscape.exe"),
    ):
        if candidate.is_file():
            return str(candidate)
    return None


INKSCAPE = _inkscape_executable()


@pytest.mark.skipif(INKSCAPE is None, reason="Inkscape is not installed")
def test_ordinary_inkscape_edit_and_save_retains_record(tmp_path):
    source = tmp_path / "inkscape.svg"
    resaved = tmp_path / "inkscape-resaved.svg"
    source.write_text(
        '<svg xmlns="http://www.w3.org/2000/svg" width="10" height="10">'
        '<rect id="mark" width="5" height="5"/></svg>',
        encoding="utf-8",
    )
    record = build_record(
        plotted_data=pd.DataFrame({"x": [1.25], "y": [2.5]}),
        statistics_status="not_applicable",
        producer={"package": "inkscape-roundtrip"},
    )
    embed_record(source, record)
    subprocess.run(
        [
            INKSCAPE,
            str(source),
            "--batch-process",
            "--actions=select-by-id:mark;transform-rotate:1",
            f"--export-filename={resaved}",
            "--export-type=svg",
        ],
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert resaved.is_file()
    assert "rotate(1)" in resaved.read_text(encoding="utf-8")
    loaded = extract_record(resaved)
    assert loaded.figure_id == record.figure_id
    assert loaded.data_tables[0].contents == record.data_tables[0].contents
    assert loaded.statistics == record.statistics
    assert loaded.sources == record.sources
