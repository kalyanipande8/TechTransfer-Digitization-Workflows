"""
Tech-Transfer Digitization & Process Workflow Automation -- Flask REST API.

Real, runnable backend (no mocking) backed by real SQLite. Provides:
  - CRUD-ish endpoints for tech-transfer documentation records
  - CRUD-ish endpoints for process-parameter tracking across manufacturing
    sites, with FAIR-aligned data standardization (see standardize.py)
  - Summary/rollup endpoints the frontend dashboard consumes directly

Run with:  python app.py   (listens on http://127.0.0.1:5055)
"""
from __future__ import annotations

import os
import sqlite3

from flask import Flask, jsonify, request
from flask_cors import CORS

import db
import standardize as std

app = Flask(__name__)
CORS(app)


def get_db():
    return db.get_connection(db.DB_PATH)


@app.before_request
def _ensure_db():
    if not os.path.exists(db.DB_PATH):
        db.init_db(db.DB_PATH)


# ---------------------------------------------------------------------------
# Sites
# ---------------------------------------------------------------------------

@app.route("/api/sites", methods=["GET"])
def list_sites():
    conn = get_db()
    rows = conn.execute("SELECT * FROM sites ORDER BY site_id").fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/sites", methods=["POST"])
def create_site():
    payload = request.get_json(force=True) or {}
    site_id = payload.get("site_id", "")
    try:
        std.validate_site_id(site_id)
    except std.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    for field in ("name", "location", "role"):
        if not payload.get(field):
            return jsonify({"error": f"'{field}' is required"}), 400
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO sites (site_id, name, location, role) VALUES (?, ?, ?, ?)",
            (site_id, payload["name"], payload["location"], payload["role"]),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": f"site_id '{site_id}' already exists"}), 409
    conn.close()
    return jsonify({"site_id": site_id}), 201


# ---------------------------------------------------------------------------
# Documentation records
# ---------------------------------------------------------------------------

@app.route("/api/documentation", methods=["GET"])
def list_documentation():
    conn = get_db()
    query = "SELECT * FROM documentation_records WHERE 1=1"
    params = []
    if site_id := request.args.get("site_id"):
        query += " AND site_id = ?"
        params.append(site_id)
    if status := request.args.get("status"):
        query += " AND status = ?"
        params.append(status)
    if doc_type := request.args.get("doc_type"):
        query += " AND doc_type = ?"
        params.append(doc_type)
    query += " ORDER BY updated_at DESC"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/documentation/<record_id>", methods=["GET"])
def get_documentation(record_id):
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM documentation_records WHERE record_id = ?", (record_id,)
    ).fetchone()
    conn.close()
    if row is None:
        return jsonify({"error": "not found"}), 404
    return jsonify(dict(row))


@app.route("/api/documentation", methods=["POST"])
def create_documentation():
    payload = request.get_json(force=True) or {}
    site_id = payload.get("site_id", "")
    try:
        std.validate_site_id(site_id)
        std.validate_doc_type(payload.get("doc_type", ""))
        status = payload.get("status", "Draft")
        std.validate_doc_status(status)
    except std.ValidationError as e:
        return jsonify({"error": str(e)}), 400
    if not payload.get("title") or not payload.get("owner"):
        return jsonify({"error": "'title' and 'owner' are required"}), 400

    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM documentation_records WHERE site_id = ?", (site_id,)
    ).fetchone()["n"]
    record_id = std.make_findable_id("TTD", site_id, count + 1)
    now = std.utcnow_iso()
    conn.execute(
        """INSERT INTO documentation_records
           (record_id, site_id, doc_type, title, status, version, owner,
            schema_version, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            record_id,
            site_id,
            payload["doc_type"],
            payload["title"],
            status,
            int(payload.get("version", 1)),
            payload["owner"],
            std.SCHEMA_VERSION,
            now,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return jsonify({"record_id": record_id}), 201


@app.route("/api/documentation/<record_id>", methods=["PATCH"])
def update_documentation(record_id):
    payload = request.get_json(force=True) or {}
    conn = get_db()
    row = conn.execute(
        "SELECT * FROM documentation_records WHERE record_id = ?", (record_id,)
    ).fetchone()
    if row is None:
        conn.close()
        return jsonify({"error": "not found"}), 404

    status = payload.get("status", row["status"])
    try:
        std.validate_doc_status(status)
    except std.ValidationError as e:
        conn.close()
        return jsonify({"error": str(e)}), 400

    version = row["version"] + 1 if "status" in payload and status != row["status"] else row["version"]
    conn.execute(
        "UPDATE documentation_records SET status = ?, version = ?, updated_at = ? WHERE record_id = ?",
        (status, version, std.utcnow_iso(), record_id),
    )
    conn.commit()
    conn.close()
    return jsonify({"record_id": record_id, "status": status, "version": version})


# ---------------------------------------------------------------------------
# Process parameters
# ---------------------------------------------------------------------------

@app.route("/api/parameters", methods=["GET"])
def list_parameters():
    conn = get_db()
    query = "SELECT * FROM process_parameters WHERE 1=1"
    params = []
    if site_id := request.args.get("site_id"):
        query += " AND site_id = ?"
        params.append(site_id)
    if batch_id := request.args.get("batch_id"):
        query += " AND batch_id = ?"
        params.append(batch_id)
    if parameter_type := request.args.get("parameter_type"):
        query += " AND parameter_type = ?"
        params.append(parameter_type)
    query += " ORDER BY recorded_at DESC LIMIT 500"
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@app.route("/api/parameters", methods=["POST"])
def create_parameter():
    payload = request.get_json(force=True) or {}
    site_id = payload.get("site_id", "")
    try:
        std.validate_site_id(site_id)
        conv = std.standardize_parameter(
            payload.get("parameter_type", ""),
            payload.get("value"),
            payload.get("unit", ""),
        )
    except std.ValidationError as e:
        return jsonify({"error": str(e)}), 400

    if not payload.get("batch_id") or not payload.get("parameter_name"):
        return jsonify({"error": "'batch_id' and 'parameter_name' are required"}), 400

    spec_low = payload.get("spec_low")
    spec_high = payload.get("spec_high")
    in_spec = 1
    if spec_low is not None and conv["standardized_value"] < float(spec_low):
        in_spec = 0
    if spec_high is not None and conv["standardized_value"] > float(spec_high):
        in_spec = 0

    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM process_parameters WHERE site_id = ?", (site_id,)
    ).fetchone()["n"]
    parameter_record_id = std.make_findable_id("PPR", site_id, count + 1)
    now = std.utcnow_iso()
    conn.execute(
        """INSERT INTO process_parameters
           (parameter_record_id, site_id, batch_id, parameter_name, parameter_type,
            recorded_value, recorded_unit, standardized_value, standardized_unit,
            in_spec, spec_low, spec_high, schema_version, recorded_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            parameter_record_id,
            site_id,
            payload["batch_id"],
            payload["parameter_name"],
            payload["parameter_type"],
            conv["recorded_value"],
            conv["recorded_unit"],
            conv["standardized_value"],
            conv["standardized_unit"],
            in_spec,
            spec_low,
            spec_high,
            std.SCHEMA_VERSION,
            now,
        ),
    )
    conn.commit()
    conn.close()
    return (
        jsonify({"parameter_record_id": parameter_record_id, "in_spec": bool(in_spec), **conv}),
        201,
    )


# ---------------------------------------------------------------------------
# Dashboard summary rollups
# ---------------------------------------------------------------------------

@app.route("/api/summary", methods=["GET"])
def summary():
    conn = get_db()
    doc_by_status = conn.execute(
        "SELECT status, COUNT(*) AS n FROM documentation_records GROUP BY status"
    ).fetchall()
    doc_by_site = conn.execute(
        "SELECT site_id, COUNT(*) AS n FROM documentation_records GROUP BY site_id"
    ).fetchall()
    param_out_of_spec = conn.execute(
        "SELECT site_id, SUM(1 - in_spec) AS out_of_spec, COUNT(*) AS total "
        "FROM process_parameters GROUP BY site_id"
    ).fetchall()
    total_docs = conn.execute("SELECT COUNT(*) AS n FROM documentation_records").fetchone()["n"]
    total_params = conn.execute("SELECT COUNT(*) AS n FROM process_parameters").fetchone()["n"]
    total_sites = conn.execute("SELECT COUNT(*) AS n FROM sites").fetchone()["n"]
    conn.close()
    return jsonify(
        {
            "total_documentation_records": total_docs,
            "total_process_parameter_records": total_params,
            "total_sites": total_sites,
            "documentation_by_status": [dict(r) for r in doc_by_status],
            "documentation_by_site": [dict(r) for r in doc_by_site],
            "parameter_out_of_spec_by_site": [dict(r) for r in param_out_of_spec],
        }
    )


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    db.init_db()
    app.run(host="127.0.0.1", port=5055, debug=False)
