#!/usr/bin/env python3
"""Refresh the local SQLite mirror from the Supabase source of truth.

The script creates a timestamped local backup before replacing the core NPDB
tables. It prints counts only and never prints secrets.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore

try:
    import certifi
except Exception:  # pragma: no cover
    certifi = None  # type: ignore


PROJECT_DIR = Path(__file__).resolve().parents[1]
DB_PATH = PROJECT_DIR / "database" / "nmr.db"
SECRETS_PATH = PROJECT_DIR / ".streamlit" / "secrets.toml"
BACKUP_DIR = PROJECT_DIR / "database" / "backups"
PAGE_SIZE = 1000

CORE_TABLES = [
    "compounds",
    "proton_nmr",
    "carbon_nmr",
    "spectra_files",
    "bioactivity_records",
]
DELETE_ORDER = [
    "bioactivity_records",
    "spectra_files",
    "carbon_nmr",
    "proton_nmr",
    "compounds",
]


def read_secrets() -> dict[str, Any]:
    if not SECRETS_PATH.exists():
        raise RuntimeError(f"Missing Streamlit secrets: {SECRETS_PATH}")
    with SECRETS_PATH.open("rb") as handle:
        return tomllib.load(handle)


def http_context():
    if certifi is not None:
        return ssl.create_default_context(cafile=certifi.where())
    return ssl.create_default_context()


def sqlite_columns(table_name: str) -> list[str]:
    with sqlite3.connect(DB_PATH) as connection:
        rows = connection.execute(f"PRAGMA table_info({table_name})").fetchall()
    columns = [row[1] for row in rows]
    if not columns:
        raise RuntimeError(f"Local table is missing or has no columns: {table_name}")
    return columns


def supabase_rows(url: str, key: str, table_name: str, columns: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    start = 0
    context = http_context()
    while True:
        end = start + PAGE_SIZE - 1
        query = urllib.parse.urlencode({"select": ",".join(columns), "order": "id.asc"}, safe=",().:*+-")
        endpoint = f"{url.rstrip('/')}/rest/v1/{table_name}?{query}"
        request = urllib.request.Request(
            endpoint,
            method="GET",
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Range-Unit": "items",
                "Range": f"{start}-{end}",
            },
        )
        try:
            with urllib.request.urlopen(request, timeout=60, context=context) as response:
                page_rows = json.loads(response.read().decode("utf-8") or "[]")
        except urllib.error.HTTPError as exc:
            details = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(f"Supabase read failed for {table_name}: {exc.code} {exc.reason}: {details}") from exc
        if isinstance(page_rows, dict):
            page_rows = [page_rows]
        rows.extend(page_rows)
        if len(page_rows) < PAGE_SIZE:
            break
        start += PAGE_SIZE
    return rows


def backup_database() -> Path:
    if not DB_PATH.exists():
        raise RuntimeError(f"Local SQLite database not found: {DB_PATH}")
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"nmr_before_supabase_sync_{timestamp}.db"
    shutil.copy2(DB_PATH, backup_path)
    return backup_path


def replace_table_rows(table_rows: dict[str, list[dict[str, Any]]], table_columns: dict[str, list[str]]) -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute("PRAGMA foreign_keys = OFF")
        try:
            cursor = connection.cursor()
            for table_name in DELETE_ORDER:
                cursor.execute(f"DELETE FROM {table_name}")
            for table_name in CORE_TABLES:
                columns = table_columns[table_name]
                placeholders = ", ".join("?" for _ in columns)
                insert_sql = f"INSERT INTO {table_name} ({', '.join(columns)}) VALUES ({placeholders})"
                values = [
                    [row.get(column) for column in columns]
                    for row in table_rows[table_name]
                ]
                cursor.executemany(insert_sql, values)
            connection.commit()
        finally:
            connection.execute("PRAGMA foreign_keys = ON")


def main() -> int:
    secrets = read_secrets()
    url = str(secrets.get("SUPABASE_URL", "")).strip()
    key = str(secrets.get("SUPABASE_SERVICE_ROLE_KEY") or secrets.get("SUPABASE_SECRET_KEY") or secrets.get("SUPABASE_ANON_KEY") or "").strip()
    if not url or not key:
        raise RuntimeError("Supabase URL/key is not configured in local Streamlit secrets.")

    backup_path = backup_database()
    table_columns = {table_name: sqlite_columns(table_name) for table_name in CORE_TABLES}
    table_rows = {
        table_name: supabase_rows(url, key, table_name, table_columns[table_name])
        for table_name in CORE_TABLES
    }
    replace_table_rows(table_rows, table_columns)

    print(f"backup created: {backup_path}")
    for table_name in CORE_TABLES:
        print(f"synced {table_name}: {len(table_rows[table_name])} rows")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"sync failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
