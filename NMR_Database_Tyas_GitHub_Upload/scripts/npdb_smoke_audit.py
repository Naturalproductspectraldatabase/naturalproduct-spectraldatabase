#!/usr/bin/env python3
"""Run a safe NPDB smoke audit without printing credentials or keys.

This script is intended for local maintenance after edits, credential updates,
or Streamlit Cloud redeploys. It checks that the local project, deployed clone,
Supabase-backed data, and private credential report still agree.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import hmac
import json
import os
import re
import sqlite3
import ssl
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib  # type: ignore

try:
    import certifi
except Exception:  # pragma: no cover - optional local convenience
    certifi = None  # type: ignore


LOCAL_PROJECT = Path(os.environ.get("NPDB_LOCAL_PROJECT_DIR", "/Users/triandatyas/Desktop/NMR_Database_Tyas_GitHub_Upload"))
DEPLOY_PROJECT = Path(os.environ.get("NPDB_DEPLOY_PROJECT_DIR", Path(__file__).resolve().parents[1]))
REPO_ROOT = Path(os.environ.get("NPDB_REPO_ROOT", DEPLOY_PROJECT.parent))

LOCAL_APP = LOCAL_PROJECT / "scripts" / "app.py"
DEPLOY_APP = DEPLOY_PROJECT / "scripts" / "app.py"
LOCAL_SECRETS = LOCAL_PROJECT / ".streamlit" / "secrets.toml"
PRIVATE_CREDENTIALS = LOCAL_PROJECT / "data" / "exports" / "credentials" / "npdb_user_credentials_private.csv"
LOCAL_DB = LOCAL_PROJECT / "database" / "nmr.db"

BASELINE_TABLE_COUNTS = {
    "compounds": 3985,
    "proton_nmr": 138,
    "carbon_nmr": 115,
    "spectra_files": 14,
    "bioactivity_records": 14631,
}
CORE_TABLES = tuple(BASELINE_TABLE_COUNTS.keys())
PRIVATE_STORAGE_BUCKETS = ("structures", "spectra", "exports")
EXPECTED_SOURCE_ROWS = {
    4: ("Marine Cyanobacteria", "Oscillatoria sp."),
    5: ("Marine Sponge", "Haliclona sp."),
}
EXPECTED_SPECTRA_TYPES = {
    6: {"1H", "13C"},
}
FORBIDDEN_SPECTRA_TYPES = {
    6: {"Supporting Data"},
}
HTTP_CONTEXT = ssl.create_default_context(cafile=certifi.where()) if certifi else None


@dataclass
class CheckResult:
    name: str
    ok: bool
    detail: str = ""


class Audit:
    def __init__(self) -> None:
        self.results: list[CheckResult] = []

    def pass_(self, name: str, detail: str = "") -> None:
        self.results.append(CheckResult(name, True, detail))

    def fail(self, name: str, detail: str = "") -> None:
        self.results.append(CheckResult(name, False, detail))

    def require(self, condition: bool, name: str, detail: str = "") -> None:
        if condition:
            self.pass_(name, detail)
        else:
            self.fail(name, detail)

    def report(self) -> int:
        for result in self.results:
            status = "PASS" if result.ok else "FAIL"
            line = f"{status}  {result.name}"
            if result.detail:
                line += f" - {result.detail}"
            print(line)
        failures = [result for result in self.results if not result.ok]
        print()
        print(f"Audit complete: {len(self.results) - len(failures)} passed, {len(failures)} failed.")
        return 1 if failures else 0


def read_toml(path: Path) -> dict[str, Any]:
    with path.open("rb") as handle:
        return tomllib.load(handle)


def read_private_credentials(path: Path) -> dict[str, dict[str, str]]:
    with path.open(newline="", encoding="utf-8") as handle:
        return {row["username"]: row for row in csv.DictReader(handle)}


def verify_password(password: str, stored_hash: str) -> bool:
    try:
        scheme, iterations_text, salt, encoded_digest = stored_hash.split("$", 3)
        iterations = int(iterations_text)
    except ValueError:
        return False
    if scheme != "pbkdf2_sha256" or iterations < 390_000:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations)
    calculated = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return hmac.compare_digest(calculated, encoded_digest)


def find_secret(secrets: dict[str, Any], *names: str) -> str:
    for name in names:
        value = secrets.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def rest_count(url: str, key: str, table: str) -> int:
    endpoint = f"{url.rstrip('/')}/rest/v1/{urllib.parse.quote(table)}?select=id"
    request = urllib.request.Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Prefer": "count=exact",
            "Range": "0-0",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=30, context=HTTP_CONTEXT) as response:
        content_range = response.headers.get("Content-Range", "")
    match = re.search(r"/(\d+|\*)$", content_range)
    if not match or match.group(1) == "*":
        raise RuntimeError(f"Could not read count for table {table}")
    return int(match.group(1))


def rest_compound_source(url: str, key: str, compound_id: int) -> tuple[str, str]:
    query = urllib.parse.urlencode(
        {
            "select": "id,source_category,source_organism",
            "id": f"eq.{compound_id}",
        }
    )
    endpoint = f"{url.rstrip('/')}/rest/v1/compounds?{query}"
    request = urllib.request.Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=30, context=HTTP_CONTEXT) as response:
        payload = response.read().decode("utf-8")
    rows = json.loads(payload)
    if not rows:
        raise RuntimeError(f"Compound {compound_id} not found")
    row = rows[0]
    return str(row.get("source_category") or ""), str(row.get("source_organism") or "")


def rest_spectra_types(url: str, key: str, compound_id: int) -> set[str]:
    query = urllib.parse.urlencode(
        {
            "select": "spectrum_type",
            "compound_id": f"eq.{compound_id}",
        }
    )
    endpoint = f"{url.rstrip('/')}/rest/v1/spectra_files?{query}"
    request = urllib.request.Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=30, context=HTTP_CONTEXT) as response:
        payload = response.read().decode("utf-8")
    rows = json.loads(payload)
    return {str(row.get("spectrum_type") or "") for row in rows}


def rest_sequence_insert_healthcheck(url: str, key: str) -> tuple[bool, str]:
    """Safely prove that Supabase can auto-assign a fresh compound ID."""
    endpoint = f"{url.rstrip('/')}/rest/v1/compounds?select=id"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    payload = {
        "trivial_name": "__NPDB_SEQUENCE_HEALTHCHECK__",
        "iupac_name": "__NPDB_SEQUENCE_HEALTHCHECK__",
        "molecular_formula": "H2O",
        "data_source": "Healthcheck",
        "curation_status": "Draft",
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    inserted_id: int | None = None
    try:
        with urllib.request.urlopen(request, timeout=30, context=HTTP_CONTEXT) as response:
            rows = json.loads(response.read().decode("utf-8") or "[]")
        if rows and rows[0].get("id") is not None:
            inserted_id = int(rows[0]["id"])
            return True, f"auto ID {inserted_id} assigned and cleaned up"
        return False, "insert returned no ID"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:160]
        return False, f"HTTP {exc.code}: {detail}"
    except Exception as exc:
        return False, exc.__class__.__name__
    finally:
        if inserted_id is not None:
            delete_endpoint = f"{url.rstrip('/')}/rest/v1/compounds?id=eq.{inserted_id}"
            delete_request = urllib.request.Request(
                delete_endpoint,
                headers={**headers, "Prefer": "return=minimal"},
                method="DELETE",
            )
            try:
                urllib.request.urlopen(delete_request, timeout=30, context=HTTP_CONTEXT).close()
            except Exception:
                pass


def rest_audit_event_healthcheck(url: str, key: str) -> tuple[bool, str]:
    endpoint = f"{url.rstrip('/')}/rest/v1/audit_events?select=id"
    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Prefer": "return=representation",
    }
    payload = {
        "actor_username": "npdb_smoke_audit",
        "actor_role": "system",
        "action": "healthcheck",
        "table_name": "audit_events",
        "backend": "supabase",
        "details": {"safe": "temporary"},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    row_id: int | None = None
    try:
        with urllib.request.urlopen(request, timeout=30, context=HTTP_CONTEXT) as response:
            rows = json.loads(response.read().decode("utf-8") or "[]")
        if rows and rows[0].get("id") is not None:
            row_id = int(rows[0]["id"])
            return True, f"temporary audit event {row_id} created and cleaned up"
        return False, "insert returned no ID"
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")[:160]
        return False, f"HTTP {exc.code}: {detail}"
    except Exception as exc:
        return False, exc.__class__.__name__
    finally:
        if row_id is not None:
            delete_endpoint = f"{url.rstrip('/')}/rest/v1/audit_events?id=eq.{row_id}"
            delete_request = urllib.request.Request(
                delete_endpoint,
                headers={**headers, "Prefer": "return=minimal"},
                method="DELETE",
            )
            try:
                urllib.request.urlopen(delete_request, timeout=30, context=HTTP_CONTEXT).close()
            except Exception:
                pass


def rest_storage_buckets(url: str, key: str) -> dict[str, dict[str, Any]]:
    endpoint = f"{url.rstrip('/')}/storage/v1/bucket"
    request = urllib.request.Request(
        endpoint,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
        },
        method="GET",
    )
    with urllib.request.urlopen(request, timeout=30, context=HTTP_CONTEXT) as response:
        rows = json.loads(response.read().decode("utf-8") or "[]")
    return {str(row.get("name") or ""): row for row in rows if isinstance(row, dict)}


def rest_storage_list_count(url: str, key: str, bucket: str) -> int:
    endpoint = f"{url.rstrip('/')}/storage/v1/object/list/{urllib.parse.quote(bucket)}"
    body = json.dumps({"prefix": "", "limit": 1, "offset": 0}).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30, context=HTTP_CONTEXT) as response:
        rows = json.loads(response.read().decode("utf-8") or "[]")
    return len(rows) if isinstance(rows, list) else 0


def sqlite_count(db_path: Path, table: str) -> int:
    with sqlite3.connect(db_path) as connection:
        return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def sqlite_source(db_path: Path, compound_id: int) -> tuple[str, str]:
    with sqlite3.connect(db_path) as connection:
        row = connection.execute(
            "SELECT source_category, source_organism FROM compounds WHERE id = ?",
            (compound_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError(f"Compound {compound_id} not found")
    return str(row[0] or ""), str(row[1] or "")


def sqlite_spectra_types(db_path: Path, compound_id: int) -> set[str]:
    with sqlite3.connect(db_path) as connection:
        rows = connection.execute(
            "SELECT spectrum_type FROM spectra_files WHERE compound_id = ?",
            (compound_id,),
        ).fetchall()
    return {str(row[0] or "") for row in rows}


def run_command(args: list[str], cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, cwd=str(cwd), text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    audit = Audit()

    for label, path in (
        ("local app", LOCAL_APP),
        ("deploy app", DEPLOY_APP),
        ("local Streamlit secrets", LOCAL_SECRETS),
        ("private credential CSV", PRIVATE_CREDENTIALS),
        ("local SQLite database", LOCAL_DB),
    ):
        audit.require(path.exists(), f"{label} exists", str(path))

    if not all(path.exists() for path in (LOCAL_APP, DEPLOY_APP, LOCAL_SECRETS, PRIVATE_CREDENTIALS, LOCAL_DB)):
        return audit.report()

    audit.require(file_hash(LOCAL_APP) == file_hash(DEPLOY_APP), "local app matches deploy app")

    compile_result = run_command([sys.executable, "-m", "py_compile", str(LOCAL_APP), str(DEPLOY_APP)], cwd=REPO_ROOT)
    audit.require(compile_result.returncode == 0, "app.py compiles with current Python")

    try:
        secrets = read_toml(LOCAL_SECRETS)
        audit.pass_("local secrets parse as TOML")
    except Exception as exc:
        audit.fail("local secrets parse as TOML", exc.__class__.__name__)
        return audit.report()

    backend = str(secrets.get("NPDB_READ_BACKEND", "")).strip().lower()
    audit.require(backend == "supabase", "read backend is Supabase", backend or "missing")

    approved_users = secrets.get("NPDB_APPROVED_USERS")
    audit.require(isinstance(approved_users, list), "approved users are configured")
    if isinstance(approved_users, list):
        audit.require(len(approved_users) == 101, "approved user count", str(len(approved_users)))
    else:
        approved_users = []

    try:
        credential_rows = read_private_credentials(PRIVATE_CREDENTIALS)
        audit.pass_("private credential CSV parses")
    except Exception as exc:
        audit.fail("private credential CSV parses", exc.__class__.__name__)
        credential_rows = {}

    users_by_name = {
        str(user.get("username", "")): user
        for user in approved_users
        if isinstance(user, dict) and str(user.get("username", "")).strip()
    }
    for username, expected_role in (("npdb_tyas", "owner_editor"), ("npdb_tjomori", "viewer")):
        user = users_by_name.get(username)
        row = credential_rows.get(username)
        audit.require(user is not None, f"{username} configured in secrets")
        audit.require(row is not None, f"{username} available in private credential CSV")
        if user and row:
            audit.require(str(user.get("role", "")) == expected_role, f"{username} role", expected_role)
            stored_hash = str(user.get("password_hash", ""))
            audit.require(verify_password(row.get("password", ""), stored_hash), f"{username} private password matches deployed hash")

    url = find_secret(secrets, "SUPABASE_URL")
    service_key = find_secret(secrets, "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY")
    anon_key = find_secret(secrets, "SUPABASE_ANON_KEY")
    audit.require(bool(url), "Supabase URL configured")
    audit.require(bool(service_key), "server-side Supabase write key configured")
    audit.require(bool(anon_key), "Supabase anon key configured")

    if url and service_key:
        ok, detail = rest_sequence_insert_healthcheck(url, service_key)
        audit.require(ok, "Supabase compound insert auto-ID healthcheck", detail)

        ok, detail = rest_audit_event_healthcheck(url, service_key)
        audit.require(ok, "Supabase audit_events write healthcheck", detail)

        try:
            buckets = rest_storage_buckets(url, service_key)
            for bucket in PRIVATE_STORAGE_BUCKETS:
                info = buckets.get(bucket)
                audit.require(info is not None, f"storage bucket {bucket} exists")
                if info is not None:
                    audit.require(info.get("public") is False, f"storage bucket {bucket} is private")
        except Exception as exc:
            audit.fail("Supabase storage bucket security audit", exc.__class__.__name__)

    local_counts: dict[str, int] = {}
    for table, baseline_count in BASELINE_TABLE_COUNTS.items():
        try:
            count = sqlite_count(LOCAL_DB, table)
            local_counts[table] = count
            audit.require(count >= baseline_count, f"local {table} count", f"{count} rows")
        except Exception as exc:
            audit.fail(f"local {table} count", exc.__class__.__name__)

    if url and service_key:
        for table in BASELINE_TABLE_COUNTS:
            try:
                count = rest_count(url, service_key, table)
                local_count = local_counts.get(table)
                if local_count is None:
                    audit.fail(f"Supabase {table} count", "local baseline missing")
                else:
                    audit.require(count == local_count, f"Supabase {table} count matches local", f"{count} rows")
            except Exception as exc:
                audit.fail(f"Supabase {table} count", exc.__class__.__name__)

        for compound_id, expected in EXPECTED_SOURCE_ROWS.items():
            try:
                cloud_value = rest_compound_source(url, service_key, compound_id)
                audit.require(cloud_value == expected, f"Supabase source fields for compound {compound_id}", "matches expected curated source")
            except Exception as exc:
                audit.fail(f"Supabase source fields for compound {compound_id}", exc.__class__.__name__)

        for compound_id, expected_types in EXPECTED_SPECTRA_TYPES.items():
            try:
                cloud_types = rest_spectra_types(url, service_key, compound_id)
                forbidden_types = FORBIDDEN_SPECTRA_TYPES.get(compound_id, set())
                audit.require(expected_types.issubset(cloud_types), f"Supabase spectra labels for compound {compound_id}", f"has {', '.join(sorted(expected_types))}")
                audit.require(not forbidden_types.intersection(cloud_types), f"Supabase spectra has no obsolete labels for compound {compound_id}")
            except Exception as exc:
                audit.fail(f"Supabase spectra labels for compound {compound_id}", exc.__class__.__name__)

    if url and anon_key:
        for table in CORE_TABLES:
            try:
                count = rest_count(url, anon_key, table)
                audit.require(count == 0, f"anon REST cannot read {table}", "0 exposed rows")
            except urllib.error.HTTPError as exc:
                audit.pass_(f"anon REST cannot read {table}", f"HTTP {exc.code}")
            except Exception as exc:
                audit.fail(f"anon REST cannot read {table}", exc.__class__.__name__)

        for bucket in PRIVATE_STORAGE_BUCKETS:
            try:
                count = rest_storage_list_count(url, anon_key, bucket)
                audit.require(count == 0, f"anon storage cannot list {bucket}", "0 exposed objects")
            except urllib.error.HTTPError as exc:
                audit.pass_(f"anon storage cannot list {bucket}", f"HTTP {exc.code}")
            except Exception as exc:
                audit.fail(f"anon storage cannot list {bucket}", exc.__class__.__name__)

    for compound_id, expected in EXPECTED_SOURCE_ROWS.items():
        try:
            local_value = sqlite_source(LOCAL_DB, compound_id)
            audit.require(local_value == expected, f"local source fields for compound {compound_id}", "matches expected curated source")
        except Exception as exc:
            audit.fail(f"local source fields for compound {compound_id}", exc.__class__.__name__)

    for compound_id, expected_types in EXPECTED_SPECTRA_TYPES.items():
        try:
            local_types = sqlite_spectra_types(LOCAL_DB, compound_id)
            forbidden_types = FORBIDDEN_SPECTRA_TYPES.get(compound_id, set())
            audit.require(expected_types.issubset(local_types), f"local spectra labels for compound {compound_id}", f"has {', '.join(sorted(expected_types))}")
            audit.require(not forbidden_types.intersection(local_types), f"local spectra has no obsolete labels for compound {compound_id}")
        except Exception as exc:
            audit.fail(f"local spectra labels for compound {compound_id}", exc.__class__.__name__)

    if (REPO_ROOT / ".git").exists():
        tracked_files = run_command(["git", "ls-files"], cwd=REPO_ROOT)
        if tracked_files.returncode == 0:
            tracked = set(tracked_files.stdout.splitlines())
            sensitive_tracked = [
                path
                for path in tracked
                if path.endswith(".streamlit/secrets.toml")
                or path.endswith("database/nmr.db")
                or "data/exports/credentials/" in path
            ]
            audit.require(not sensitive_tracked, "no private secrets, DB, or credential CSV tracked")
        else:
            audit.fail("git tracked-file audit", "git ls-files failed")

        jwt_header_probe = "eyJ" + "hbGciOi"
        token_scan = run_command(["git", "grep", "-Il", jwt_header_probe], cwd=REPO_ROOT)
        audit.require(token_scan.returncode in {1}, "no JWT-like keys tracked")

    return audit.report()


if __name__ == "__main__":
    raise SystemExit(main())
