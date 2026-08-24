"""Directory interoperability with Figure-Statistics Bundle."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

from .api import build_record
from .schema import DataTable, FigureRecord, deterministic_json
from .svg import extract_record
from .tables import safe_filename_token, statistics_csv_bytes, table_from_data


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(deterministic_json(value, indent=2) + "\n", encoding="utf-8")


def export_fsb(
    figure: FigureRecord | str | Path,
    output_dir: str | Path,
    *,
    svg_path: str | Path | None = None,
) -> Path:
    """Export overlapping fields to a Figure-Statistics Bundle-style directory."""

    if isinstance(figure, FigureRecord):
        record = figure
    else:
        svg_path = figure
        record = extract_record(figure)
    output = Path(output_dir)
    if output.exists() and any(output.iterdir()):
        raise FileExistsError(f"Figure-Statistics Bundle directory is not empty: {output}")
    (output / "data").mkdir(parents=True, exist_ok=True)
    (output / "stats").mkdir(parents=True, exist_ok=True)
    (output / "exports").mkdir(parents=True, exist_ok=True)
    data_refs: list[str] = []
    data_info: dict[str, Any] = {"tables": []}
    filenames: set[str] = set()
    for index, table in enumerate(record.data_tables):
        filename = "data.csv" if index == 0 else f"{safe_filename_token(table.name)}.csv"
        if filename in filenames:
            raise ValueError(f"Figure-Statistics Bundle table filenames collide at {filename}")
        filenames.add(filename)
        data_refs.append(f"data/{filename}")
        if table.contents is not None:
            (output / "data" / filename).write_bytes(table.contents.encode("utf-8"))
        data_info["tables"].append(
            {
                "name": table.name,
                "path": f"data/{filename}",
                "purpose": table.purpose,
                "sha256": table.sha256,
                "shape": [table.row_count, table.column_count],
                "columns": [column.to_dict() for column in table.columns],
            }
        )
    _write_json(output / "data" / "data_info.json", data_info)
    _write_json(output / "stats" / "stats.json", record.statistics)
    (output / "stats" / "stats.csv").write_bytes(statistics_csv_bytes(record.statistics))
    _write_json(
        output / "node.json",
        {
            "id": record.figure_id,
            "type": "figure",
            "name": record.title or record.original_stem or record.figure_id,
            "refs": {
                "data": data_refs,
                "data_info": "data/data_info.json",
                "stats": "stats/stats.json",
                "encoding": "encoding.json",
                "theme": "theme.json",
            },
            "reprofig": {
                "schema": record.schema,
                "profile": record.distribution_profile,
                "created_at": record.created_at,
                "producer": record.producer,
            },
        },
    )
    _write_json(output / "encoding.json", {"traces": [], "data_refs": data_refs})
    _write_json(output / "theme.json", {"source": "rendered SVG"})
    if svg_path is not None:
        shutil.copy2(svg_path, output / "exports" / Path(svg_path).name)
    return output


def import_fsb(bundle_dir: str | Path) -> FigureRecord:
    """Import the canonical data and statistics from an FSB-style directory."""

    bundle = Path(bundle_dir)
    node = json.loads((bundle / "node.json").read_text(encoding="utf-8"))
    info_path = bundle / "data" / "data_info.json"
    data_info = json.loads(info_path.read_text(encoding="utf-8")) if info_path.exists() else {}
    tables: list[DataTable] = []
    declared = data_info.get("tables") if isinstance(data_info, dict) else None
    if declared:
        for item in declared:
            path = bundle / item.get("path", "")
            if not path.is_file():
                continue
            table = table_from_data(
                path.read_bytes(),
                name=item.get("name", path.stem),
                purpose=item.get("purpose", "plot_and_statistics"),
                classification={
                    column.get("name"): column
                    for column in item.get("columns", [])
                    if isinstance(column, dict) and column.get("name")
                },
                roles={
                    column.get("name"): column.get("role")
                    for column in item.get("columns", [])
                    if isinstance(column, dict) and column.get("role")
                },
            )
            tables.append(table)
    else:
        for path in sorted((bundle / "data").glob("*.csv")):
            tables.append(table_from_data(path.read_bytes(), name=path.stem))
    stats_path = bundle / "stats" / "stats.json"
    statistics = json.loads(stats_path.read_text(encoding="utf-8")) if stats_path.exists() else []
    extension = (
        node.get("reprofig")
        or node.get("metafig")
        or node.get("figure_artifact")
        or {}
    )
    return build_record(
        title=node.get("name"),
        original_stem=bundle.name,
        producer=extension.get("producer") or {"package": "fsb-import"},
        data_tables=tables,
        statistics=statistics,
        data_status="complete" if tables else "incomplete",
        statistics_status="complete" if statistics else "not_applicable",
        extensions={"fsb_node": node},
    )
