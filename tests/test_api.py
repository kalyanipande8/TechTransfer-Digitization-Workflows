"""
Real API tests against Flask's test client (in-process, no mocking of
business logic) and a real temp-file SQLite database. Run with:

    pytest -q
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest

import app as flask_app_module
import db as db_module
import standardize as std


@pytest.fixture()
def client(tmp_path, monkeypatch):
    test_db_path = str(tmp_path / "test_techtransfer.db")
    monkeypatch.setattr(db_module, "DB_PATH", test_db_path)
    db_module.init_db(test_db_path)
    flask_app_module.app.config["TESTING"] = True
    with flask_app_module.app.test_client() as c:
        yield c


# ---------------------------------------------------------------------------
# standardize.py unit tests
# ---------------------------------------------------------------------------

def test_temperature_conversion_fahrenheit_to_celsius():
    out = std.standardize_parameter("temperature", 98.6, "F")
    assert out["standardized_unit"] == "C"
    assert abs(out["standardized_value"] - 37.0) < 0.01


def test_temperature_conversion_kelvin_to_celsius():
    out = std.standardize_parameter("temperature", 310.15, "K")
    assert abs(out["standardized_value"] - 37.0) < 0.01


def test_pressure_conversion_psi_to_bar():
    out = std.standardize_parameter("pressure", 14.5038, "psi")
    assert out["standardized_unit"] == "bar"
    assert abs(out["standardized_value"] - 1.0) < 0.01


def test_unknown_parameter_type_rejected():
    with pytest.raises(std.ValidationError):
        std.standardize_parameter("bogus_type", 1.0, "C")


def test_unknown_unit_rejected():
    with pytest.raises(std.ValidationError):
        std.standardize_parameter("temperature", 1.0, "rankine")


def test_non_numeric_value_rejected():
    with pytest.raises(std.ValidationError):
        std.standardize_parameter("temperature", "not-a-number", "C")


def test_site_id_schema_validation():
    std.validate_site_id("SITE-01")  # should not raise
    with pytest.raises(std.ValidationError):
        std.validate_site_id("site1")


def test_findable_id_format():
    fid = std.make_findable_id("TTD", "SITE-02", 7)
    assert fid == "TTD-SITE02-000007"


# ---------------------------------------------------------------------------
# API endpoint tests
# ---------------------------------------------------------------------------

def test_health(client):
    resp = client.get("/api/health")
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "ok"


def test_create_and_list_site(client):
    resp = client.post(
        "/api/sites",
        json={"site_id": "SITE-01", "name": "Test Site", "location": "Boston", "role": "GMP"},
    )
    assert resp.status_code == 201
    resp = client.get("/api/sites")
    assert resp.status_code == 200
    sites = resp.get_json()
    assert len(sites) == 1
    assert sites[0]["site_id"] == "SITE-01"


def test_create_site_bad_id_rejected(client):
    resp = client.post(
        "/api/sites", json={"site_id": "boston-1", "name": "x", "location": "y", "role": "z"}
    )
    assert resp.status_code == 400


def test_create_documentation_record(client):
    client.post("/api/sites", json={"site_id": "SITE-01", "name": "x", "location": "y", "role": "z"})
    resp = client.post(
        "/api/documentation",
        json={
            "site_id": "SITE-01",
            "doc_type": "SOP",
            "title": "Cell Culture SOP",
            "status": "Draft",
            "owner": "A. Kapoor",
        },
    )
    assert resp.status_code == 201
    record_id = resp.get_json()["record_id"]
    assert record_id.startswith("TTD-SITE01-")

    resp = client.get(f"/api/documentation/{record_id}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "Draft"
    assert body["schema_version"] == std.SCHEMA_VERSION


def test_documentation_status_transition_bumps_version(client):
    client.post("/api/sites", json={"site_id": "SITE-01", "name": "x", "location": "y", "role": "z"})
    resp = client.post(
        "/api/documentation",
        json={"site_id": "SITE-01", "doc_type": "SOP", "title": "t", "status": "Draft", "owner": "o"},
    )
    record_id = resp.get_json()["record_id"]
    resp = client.patch(f"/api/documentation/{record_id}", json={"status": "In Review"})
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "In Review"
    assert body["version"] == 2


def test_create_documentation_invalid_doc_type_rejected(client):
    client.post("/api/sites", json={"site_id": "SITE-01", "name": "x", "location": "y", "role": "z"})
    resp = client.post(
        "/api/documentation",
        json={"site_id": "SITE-01", "doc_type": "Not A Real Type", "title": "t", "owner": "o"},
    )
    assert resp.status_code == 400


def test_create_parameter_with_unit_conversion(client):
    client.post("/api/sites", json={"site_id": "SITE-02", "name": "x", "location": "y", "role": "z"})
    resp = client.post(
        "/api/parameters",
        json={
            "site_id": "SITE-02",
            "batch_id": "SITE-02-BATCH-001",
            "parameter_name": "Bioreactor Temperature",
            "parameter_type": "temperature",
            "value": 98.6,
            "unit": "F",
            "spec_low": 36.0,
            "spec_high": 37.5,
        },
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["standardized_unit"] == "C"
    assert abs(body["standardized_value"] - 37.0) < 0.01
    assert body["in_spec"] is True
    assert body["parameter_record_id"].startswith("PPR-SITE02-")


def test_create_parameter_out_of_spec_flagged(client):
    client.post("/api/sites", json={"site_id": "SITE-02", "name": "x", "location": "y", "role": "z"})
    resp = client.post(
        "/api/parameters",
        json={
            "site_id": "SITE-02",
            "batch_id": "b1",
            "parameter_name": "Culture pH",
            "parameter_type": "ph",
            "value": 9.5,
            "unit": "pH",
            "spec_low": 6.8,
            "spec_high": 7.3,
        },
    )
    assert resp.status_code == 201
    assert resp.get_json()["in_spec"] is False


def test_parameter_filtering_by_site(client):
    client.post("/api/sites", json={"site_id": "SITE-01", "name": "a", "location": "b", "role": "c"})
    client.post("/api/sites", json={"site_id": "SITE-02", "name": "a", "location": "b", "role": "c"})
    for site in ("SITE-01", "SITE-02"):
        client.post(
            "/api/parameters",
            json={
                "site_id": site,
                "batch_id": "b1",
                "parameter_name": "Agitator Mixing Speed",
                "parameter_type": "mixing_speed",
                "value": 150,
                "unit": "rpm",
            },
        )
    resp = client.get("/api/parameters?site_id=SITE-01")
    rows = resp.get_json()
    assert len(rows) == 1
    assert rows[0]["site_id"] == "SITE-01"


def test_summary_endpoint(client):
    client.post("/api/sites", json={"site_id": "SITE-01", "name": "a", "location": "b", "role": "c"})
    client.post(
        "/api/documentation",
        json={"site_id": "SITE-01", "doc_type": "SOP", "title": "t", "status": "Approved", "owner": "o"},
    )
    client.post(
        "/api/parameters",
        json={
            "site_id": "SITE-01",
            "batch_id": "b1",
            "parameter_name": "Harvest Volume",
            "parameter_type": "volume",
            "value": 500,
            "unit": "L",
        },
    )
    resp = client.get("/api/summary")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["total_documentation_records"] == 1
    assert body["total_process_parameter_records"] == 1
    assert body["total_sites"] == 1
