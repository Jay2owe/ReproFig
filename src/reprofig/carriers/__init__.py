"""Format adapters for embedding ReproFig records in scientific artifacts."""

from .base import (
    CarrierCapabilities,
    CarrierError,
    CarrierFormatError,
    CarrierLimitError,
    MissingDependencyError,
)
from .manifest import CARRIER_SCHEMA, CarrierManifest, CarrierRecordEntry
from .registry import formats, get_adapter, identify_format

__all__ = [
    "CARRIER_SCHEMA",
    "CarrierCapabilities",
    "CarrierError",
    "CarrierFormatError",
    "CarrierLimitError",
    "CarrierManifest",
    "CarrierRecordEntry",
    "MissingDependencyError",
    "formats",
    "get_adapter",
    "identify_format",
]
