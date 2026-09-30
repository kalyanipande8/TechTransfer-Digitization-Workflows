"""
FAIR-principle-aligned data standardization utilities.

Findable   -> every record gets a globally unique, structured, resolvable ID
              (e.g. TTD-SITE02-000104) instead of an opaque autoincrement int.
Accessible -> records are exposed through documented REST endpoints (app.py).
Interoperable -> all process-parameter values are normalized to one canonical
              unit per parameter type (SI-leaning) regardless of which unit
              the originating manufacturing site recorded it in, and every
              record conforms to one fixed JSON schema.
Reusable   -> records carry provenance (source_site, recorded_unit,
              standardized_unit, schema_version) so a downstream consumer can
              trust and reuse them without guessing conventions.

This module contains real, deterministic conversion + validation logic that
is unit-tested in tests/test_api.py -- it is not a stub.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone

SCHEMA_VERSION = "1.0"

# Canonical (standardized) unit for each parameter type, and the accepted
# input units this API knows how to convert from.
CANONICAL_UNITS = {
    "temperature": "C",
    "pressure": "bar",
    "ph": "pH",
    "pressure_diff": "mbar",
    "conductivity": "mS/cm",
    "flow_rate": "L/min",
    "mixing_speed": "rpm",
    "mass": "kg",
    "volume": "L",
    "time": "min",
}

_TEMP_TO_C = {
    "C": lambda v: v,
    "F": lambda v: (v - 32) * 5.0 / 9.0,
    "K": lambda v: v - 273.15,
}

_PRESSURE_TO_BAR = {
    "bar": lambda v: v,
    "psi": lambda v: v * 0.0689476,
    "kPa": lambda v: v / 100.0,
    "atm": lambda v: v * 1.01325,
}

_MASS_TO_KG = {
    "kg": lambda v: v,
    "g": lambda v: v / 1000.0,
    "lb": lambda v: v * 0.453592,
}

_VOLUME_TO_L = {
    "L": lambda v: v,
    "mL": lambda v: v / 1000.0,
    "gal": lambda v: v * 3.78541,
}

_FLOW_TO_LPM = {
    "L/min": lambda v: v,
    "mL/min": lambda v: v / 1000.0,
    "gal/min": lambda v: v * 3.78541,
}

_CONVERTERS = {
    "temperature": _TEMP_TO_C,
    "pressure": _PRESSURE_TO_BAR,
    "mass": _MASS_TO_KG,
    "volume": _VOLUME_TO_L,
    "flow_rate": _FLOW_TO_LPM,
    # Parameters below have a single accepted unit -> identity conversion.
    "ph": {"pH": lambda v: v},
    "pressure_diff": {"mbar": lambda v: v},
    "conductivity": {"mS/cm": lambda v: v},
    "mixing_speed": {"rpm": lambda v: v},
    "time": {"min": lambda v: v, "s": lambda v: v / 60.0, "h": lambda v: v * 60.0},
}

VALID_PARAMETER_TYPES = set(CANONICAL_UNITS.keys())

VALID_DOC_TYPES = {
    "Batch Record",
    "SOP",
    "Process Validation Report",
    "Analytical Method Transfer",
    "Equipment Qualification",
    "Change Control",
    "Risk Assessment",
}

VALID_DOC_STATUSES = {"Draft", "In Review", "Approved", "Transferred", "Superseded"}

_SITE_ID_RE = re.compile(r"^SITE-\d{2}$")


class ValidationError(ValueError):
    pass


def validate_site_id(site_id: str) -> None:
    if not isinstance(site_id, str) or not _SITE_ID_RE.match(site_id):
        raise ValidationError(
            f"site_id '{site_id}' does not match required schema SITE-NN (e.g. SITE-01)"
        )


def standardize_parameter(parameter_type: str, value: float, unit: str) -> dict:
    """Convert (value, unit) into the canonical unit for parameter_type.

    Returns dict with standardized_value, standardized_unit, recorded_unit,
    recorded_value. Raises ValidationError for unknown type/unit or
    non-numeric value.
    """
    if parameter_type not in VALID_PARAMETER_TYPES:
        raise ValidationError(
            f"unknown parameter_type '{parameter_type}'; must be one of {sorted(VALID_PARAMETER_TYPES)}"
        )
    try:
        value = float(value)
    except (TypeError, ValueError):
        raise ValidationError(f"value '{value}' is not numeric")

    converters = _CONVERTERS[parameter_type]
    if unit not in converters:
        raise ValidationError(
            f"unit '{unit}' not recognized for parameter_type '{parameter_type}'; "
            f"accepted units: {sorted(converters.keys())}"
        )
    standardized_value = round(converters[unit](value), 6)
    return {
        "recorded_value": value,
        "recorded_unit": unit,
        "standardized_value": standardized_value,
        "standardized_unit": CANONICAL_UNITS[parameter_type],
    }


def make_findable_id(prefix: str, site_id: str, seq: int) -> str:
    """Build a FAIR 'findable' identifier: <PREFIX>-<SITE>-<zero-padded seq>."""
    return f"{prefix}-{site_id.replace('SITE-', 'SITE')}-{seq:06d}"


def validate_doc_type(doc_type: str) -> None:
    if doc_type not in VALID_DOC_TYPES:
        raise ValidationError(
            f"doc_type '{doc_type}' invalid; must be one of {sorted(VALID_DOC_TYPES)}"
        )


def validate_doc_status(status: str) -> None:
    if status not in VALID_DOC_STATUSES:
        raise ValidationError(
            f"status '{status}' invalid; must be one of {sorted(VALID_DOC_STATUSES)}"
        )


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")
