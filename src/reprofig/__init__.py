"""Portable, self-describing scientific figure artifacts."""

from .api import (
    attach,
    attachment_for,
    build_record,
    build_record_for_figure,
    detach,
    read_svg,
    save_svg,
    write_companion_tables,
)
from .compat import export_fsb, import_fsb
from .profiles import approved_public_tables, derive_profile
from .publication import (
    PublicationResult,
    caption_for,
    classify_figure,
    export_rocrate,
    extract_figure,
    inspect_figure,
    publish_figures,
    scan_figures,
)
from .schema import (
    LEGACY_SCHEMA_IDS,
    SCHEMA_ID,
    SUPPORTED_SCHEMA_IDS,
    ColumnSpec,
    DataTable,
    FigureRecord,
    SourceReference,
)
from .sources import file_sha256, source_reference, source_status
from .svg import FigureRecordError, embed_record, extract_record, try_extract_record
from .tables import statistics_csv_bytes, table_from_data
from .validation import ValidationIssue, ValidationReport, validate_record, validate_svg

__all__ = [
    "LEGACY_SCHEMA_IDS",
    "SCHEMA_ID",
    "SUPPORTED_SCHEMA_IDS",
    "ColumnSpec",
    "DataTable",
    "FigureRecord",
    "FigureRecordError",
    "PublicationResult",
    "SourceReference",
    "ValidationIssue",
    "ValidationReport",
    "approved_public_tables",
    "attach",
    "attachment_for",
    "build_record",
    "build_record_for_figure",
    "caption_for",
    "classify_figure",
    "derive_profile",
    "detach",
    "embed_record",
    "export_fsb",
    "export_rocrate",
    "extract_figure",
    "extract_record",
    "file_sha256",
    "import_fsb",
    "inspect_figure",
    "publish_figures",
    "read_svg",
    "save_svg",
    "scan_figures",
    "source_reference",
    "source_status",
    "statistics_csv_bytes",
    "table_from_data",
    "try_extract_record",
    "validate_record",
    "validate_svg",
    "write_companion_tables",
]

__version__ = "0.1.0"
