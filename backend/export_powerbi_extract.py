"""
Builds the Power BI-ready CSV extract from the REAL SQLite database
(techtransfer.db), the same one the API serves from. Power BI itself is a
licensed Windows desktop application with no CLI/scriptable API and is not
installed/available in this (macOS, headless) environment, so no .pbix file
was built, opened, or run -- see the "Power BI" note in README.md. This
script produces exactly the flat, denormalized extract a Power BI "Get Data
-> Text/CSV" import would consume, joining documentation and parameter
tables on site_id.

Run with:  python export_powerbi_extract.py
"""
import csv
import os

import db

OUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "powerbi_extract.csv")


def build_extract():
    conn = db.get_connection()
    sites = {r["site_id"]: dict(r) for r in conn.execute("SELECT * FROM sites")}

    rows = []
    for r in conn.execute("SELECT * FROM documentation_records"):
        r = dict(r)
        site = sites.get(r["site_id"], {})
        rows.append(
            {
                "record_type": "documentation",
                "record_id": r["record_id"],
                "site_id": r["site_id"],
                "site_name": site.get("name", ""),
                "site_location": site.get("location", ""),
                "site_role": site.get("role", ""),
                "category": r["doc_type"],
                "name": r["title"],
                "status_or_spec": r["status"],
                "version": r["version"],
                "owner_or_batch": r["owner"],
                "recorded_value": "",
                "recorded_unit": "",
                "standardized_value": "",
                "standardized_unit": "",
                "in_spec": "",
                "schema_version": r["schema_version"],
                "timestamp": r["updated_at"],
            }
        )

    for r in conn.execute("SELECT * FROM process_parameters"):
        r = dict(r)
        site = sites.get(r["site_id"], {})
        rows.append(
            {
                "record_type": "process_parameter",
                "record_id": r["parameter_record_id"],
                "site_id": r["site_id"],
                "site_name": site.get("name", ""),
                "site_location": site.get("location", ""),
                "site_role": site.get("role", ""),
                "category": r["parameter_type"],
                "name": r["parameter_name"],
                "status_or_spec": f"[{r['spec_low']}, {r['spec_high']}]" if r["spec_low"] is not None else "",
                "version": "",
                "owner_or_batch": r["batch_id"],
                "recorded_value": r["recorded_value"],
                "recorded_unit": r["recorded_unit"],
                "standardized_value": r["standardized_value"],
                "standardized_unit": r["standardized_unit"],
                "in_spec": bool(r["in_spec"]),
                "schema_version": r["schema_version"],
                "timestamp": r["recorded_at"],
            }
        )
    conn.close()

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with open(OUT_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"Wrote {len(rows)} rows -> {OUT_PATH}")


if __name__ == "__main__":
    build_extract()
