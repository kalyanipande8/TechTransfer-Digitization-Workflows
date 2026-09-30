"""SQLite persistence layer -- real on-disk database, no mocking."""
from __future__ import annotations

import os
import sqlite3

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "techtransfer.db")

SCHEMA = """
CREATE TABLE IF NOT EXISTS documentation_records (
    record_id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL,
    doc_type TEXT NOT NULL,
    title TEXT NOT NULL,
    status TEXT NOT NULL,
    version INTEGER NOT NULL DEFAULT 1,
    owner TEXT NOT NULL,
    schema_version TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS process_parameters (
    parameter_record_id TEXT PRIMARY KEY,
    site_id TEXT NOT NULL,
    batch_id TEXT NOT NULL,
    parameter_name TEXT NOT NULL,
    parameter_type TEXT NOT NULL,
    recorded_value REAL NOT NULL,
    recorded_unit TEXT NOT NULL,
    standardized_value REAL NOT NULL,
    standardized_unit TEXT NOT NULL,
    in_spec INTEGER NOT NULL,
    spec_low REAL,
    spec_high REAL,
    schema_version TEXT NOT NULL,
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sites (
    site_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    location TEXT NOT NULL,
    role TEXT NOT NULL
);
"""


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db(db_path: str = DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def reset_db(db_path: str = DB_PATH) -> None:
    """Drop and recreate all tables -- used by tests for isolation."""
    conn = get_connection(db_path)
    try:
        conn.executescript(
            """
            DROP TABLE IF EXISTS documentation_records;
            DROP TABLE IF EXISTS process_parameters;
            DROP TABLE IF EXISTS sites;
            """
        )
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()
