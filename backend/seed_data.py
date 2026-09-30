"""
Simulates realistic multi-site tech-transfer documentation and
process-parameter data by calling the REAL Flask API endpoints (not by
writing to the DB directly) -- this doubles as an end-to-end smoke test of
the API surface. Fixed random seed (42) -> fully reproducible.

Run standalone with the app NOT running -- it starts the app in a
background thread on an ephemeral in-process test client instead, so no
extra terminal / port juggling is needed:

    python seed_data.py
"""
from __future__ import annotations

import random

import app as flask_app_module
import db

random.seed(42)

SITES = [
    ("SITE-01", "Cambridge Process Dev Lab", "Cambridge, MA, USA", "Origin R&D"),
    ("SITE-02", "Raleigh Manufacturing Site", "Raleigh, NC, USA", "Receiving GMP"),
    ("SITE-03", "Cork Manufacturing Site", "Cork, Ireland", "Receiving GMP"),
    ("SITE-04", "Singapore Manufacturing Site", "Singapore", "Receiving GMP"),
]

DOC_TYPES = list(flask_app_module.std.VALID_DOC_TYPES)
DOC_STATUSES = list(flask_app_module.std.VALID_DOC_STATUSES)

PARAM_DEFS = [
    ("Bioreactor Temperature", "temperature", ["C", "F", "K"], 36.0, 37.5),
    ("Bioreactor Pressure", "pressure", ["bar", "psi", "kPa"], 0.8, 1.3),
    ("Culture pH", "ph", ["pH"], 6.8, 7.3),
    ("Filter Differential Pressure", "pressure_diff", ["mbar"], 10.0, 80.0),
    ("Buffer Conductivity", "conductivity", ["mS/cm"], 12.0, 18.0),
    ("Feed Flow Rate", "flow_rate", ["L/min", "mL/min", "gal/min"], 0.5, 5.0),
    ("Agitator Mixing Speed", "mixing_speed", ["rpm"], 80.0, 220.0),
    ("Batch Mass Yield", "mass", ["kg", "g", "lb"], 40.0, 120.0),
    ("Harvest Volume", "volume", ["L", "mL", "gal"], 200.0, 800.0),
    ("Hold Time", "time", ["min", "h"], 30.0, 480.0),
]

DOC_TITLES = [
    "Batch Record Template Transfer",
    "Cell Culture SOP",
    "Downstream Purification Process Validation",
    "Analytical Method Transfer Protocol",
    "Bioreactor Equipment Qualification",
    "Raw Material Change Control",
    "Process Risk Assessment (FMEA)",
    "Viral Clearance Validation Report",
    "Cleaning Validation Protocol",
    "Tech Transfer Master Plan",
]

OWNERS = ["A. Kapoor", "M. Chen", "R. O'Sullivan", "S. Osei", "J. Nguyen", "L. Fitzgerald"]


def run_seed(client):
    for site_id, name, location, role in SITES:
        client.post("/api/sites", json={"site_id": site_id, "name": name, "location": location, "role": role})

    for site_id, *_ in SITES:
        n_docs = random.randint(8, 14)
        for _ in range(n_docs):
            client.post(
                "/api/documentation",
                json={
                    "site_id": site_id,
                    "doc_type": random.choice(DOC_TYPES),
                    "title": random.choice(DOC_TITLES),
                    "status": random.choices(DOC_STATUSES, weights=[2, 3, 3, 4, 1])[0],
                    "owner": random.choice(OWNERS),
                },
            )

        n_batches = random.randint(3, 5)
        for b in range(1, n_batches + 1):
            batch_id = f"{site_id}-BATCH-{b:03d}"
            for name, ptype, units, low, high in PARAM_DEFS:
                unit = random.choice(units)
                # generate a value near spec in the canonical unit, then
                # convert back to the randomly chosen recorded unit so the
                # standardization endpoint has real work to do
                target = random.uniform(low * 0.92, high * 1.08)
                value = _to_recorded_unit(ptype, unit, target)
                client.post(
                    "/api/parameters",
                    json={
                        "site_id": site_id,
                        "batch_id": batch_id,
                        "parameter_name": name,
                        "parameter_type": ptype,
                        "value": value,
                        "unit": unit,
                        "spec_low": low,
                        "spec_high": high,
                    },
                )


def _to_recorded_unit(ptype, unit, canonical_value):
    """Inverse of standardize.standardize_parameter, for seeding purposes."""
    if ptype == "temperature":
        return {"C": canonical_value, "F": canonical_value * 9 / 5 + 32, "K": canonical_value + 273.15}[unit]
    if ptype == "pressure":
        return {"bar": canonical_value, "psi": canonical_value / 0.0689476, "kPa": canonical_value * 100}[unit]
    if ptype == "mass":
        return {"kg": canonical_value, "g": canonical_value * 1000, "lb": canonical_value / 0.453592}[unit]
    if ptype == "volume":
        return {"L": canonical_value, "mL": canonical_value * 1000, "gal": canonical_value / 3.78541}[unit]
    if ptype == "flow_rate":
        return {"L/min": canonical_value, "mL/min": canonical_value * 1000, "gal/min": canonical_value / 3.78541}[unit]
    if ptype == "time":
        return {"min": canonical_value, "h": canonical_value / 60, "s": canonical_value * 60}[unit]
    return canonical_value


if __name__ == "__main__":
    db.reset_db()
    with flask_app_module.app.test_client() as client:
        run_seed(client)
    print("Seed complete ->", db.DB_PATH)
