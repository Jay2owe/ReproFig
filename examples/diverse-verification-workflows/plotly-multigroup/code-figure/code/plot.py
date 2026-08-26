"""Render the example's exact plotting script as a traceable code figure."""

from __future__ import annotations

import csv
import sys
from pathlib import Path

from reprofig import build_record, embed_file

BUNDLE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BUNDLE / "data" / "src"))
from code_figure import Panel, line_table, save  # noqa: E402

SOURCE = BUNDLE / "data" / "src" / "example-plot.py"
PANELS = [
    Panel(
        label='EXACT PLOTLY PRODUCER',
        code=SOURCE.read_text(encoding="utf-8"),
        accent="blue",
    )
]


def main() -> None:
    result = save(
        PANELS,
        BUNDLE / "fig" / 'condition-response-code.svg',
        png=str(BUNDLE / "fig" / 'condition-response-code.png'),
        png_scale=2.0,
    )
    rows = line_table(PANELS)
    table = BUNDLE / "data" / "der" / "figure_data.csv"
    with table.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    record = build_record(
        title='Multiple-group comparison producer code',
        original_stem='condition-response-code',
        producer={"package": "plot-that", "grammar": "code-panel"},
        plotted_data=table.read_bytes(),
        data_status="incomplete",
        statistics_status="complete",
        reproduction={
            "script": Path(__file__).read_text(encoding="utf-8"),
            "command": "python code/plot.py",
        },
    )
    record.figure_id = 'rf-16450315b13940c6be000aaf0c94b9d0'
    for target in (
        BUNDLE / "fig" / 'condition-response-code.svg',
        BUNDLE / "fig" / 'condition-response-code.png',
    ):
        embed_file(target, record, output_path=target)
    print(
        f"{result['width']:g} x {result['height']:g}, "
        f"{result['lines']} source lines; {result['rasteriser']}"
    )


if __name__ == "__main__":
    main()
