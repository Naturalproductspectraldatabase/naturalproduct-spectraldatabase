#!/usr/bin/env python3
"""Repair missing NPDB structure image assets from stored structure identifiers.

This script only creates/replaces generated structure images for rows that can
be rendered from SMILES, InChI, or an InChIKey resolved through PubChem. It does
not delete compounds or modify scientific metadata.
"""

from __future__ import annotations

import argparse
import base64
import csv
import io
import json
import os
import re
import sqlite3
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
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

from PIL import Image, ImageOps
from rdkit import Chem, RDLogger
from rdkit.Chem import AllChem, rdDepictor
from rdkit.Chem.Draw import rdMolDraw2D


RDLogger.DisableLog("rdApp.*")

PROJECT_DIR = Path(__file__).resolve().parents[1]
SECRETS_PATH = PROJECT_DIR / ".streamlit" / "secrets.toml"
DB_PATH = PROJECT_DIR / "database" / "nmr.db"
EXPORT_DIR = PROJECT_DIR / "data" / "exports" / "structure_repair"
IMAGE_SIZE = (1600, 1200)
HTTP_CONTEXT = ssl.create_default_context(cafile=certifi.where()) if certifi else None
INCHIKEY_RE = re.compile(r"^[A-Z]{14}-[A-Z]{10}-[A-Z]$")


def read_secrets() -> dict[str, Any]:
    secrets: dict[str, Any] = {}
    if SECRETS_PATH.exists():
        with SECRETS_PATH.open("rb") as handle:
            secrets.update(tomllib.load(handle))
    return secrets


def secret_value(secrets: dict[str, Any], *names: str) -> str:
    for name in names:
        env_value = os.environ.get(name)
        if env_value:
            return env_value.strip()
        value = secrets.get(name)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def decode_jwt_role(token: str) -> str:
    token = token.strip()
    if token.count(".") < 2:
        return ""
    try:
        payload = token.split(".")[1]
        payload += "=" * ((4 - len(payload) % 4) % 4)
        return str(json.loads(base64.urlsafe_b64decode(payload.encode("ascii"))).get("role", ""))
    except Exception:
        return ""


def is_write_key(token: str) -> bool:
    if not token:
        return False
    role = decode_jwt_role(token)
    if role:
        return role == "service_role"
    return token.startswith("sb_secret_")


def request_json(method: str, base_url: str, key: str, path: str, query: dict | None = None, body=None, json_body: bool = True):
    url = f"{base_url.rstrip('/')}{path}"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query, doseq=True, safe=',().:*+-')}"
    payload = None
    headers = {"apikey": key, "Authorization": f"Bearer {key}"}
    if body is not None:
        if json_body:
            payload = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        else:
            payload = body
    request = urllib.request.Request(url, data=payload, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=60, context=HTTP_CONTEXT) as response:
        raw = response.read()
    return json.loads(raw.decode("utf-8")) if raw else None


def paged_select(base_url: str, key: str, table: str, columns: str) -> list[dict]:
    rows: list[dict] = []
    start = 0
    page_size = 1000
    while True:
        end = start + page_size - 1
        url = (
            f"{base_url.rstrip()}/rest/v1/{table}?"
            + urllib.parse.urlencode({"select": columns, "order": "id.asc"}, safe=",")
        )
        request = urllib.request.Request(
            url,
            headers={
                "apikey": key,
                "Authorization": f"Bearer {key}",
                "Range-Unit": "items",
                "Range": f"{start}-{end}",
            },
            method="GET",
        )
        with urllib.request.urlopen(request, timeout=60, context=HTTP_CONTEXT) as response:
            page_rows = json.loads(response.read().decode("utf-8"))
        rows.extend(page_rows)
        if len(page_rows) < page_size:
            break
        start += page_size
    return rows


def resolve_inchikey_to_smiles(inchikey: str) -> str:
    if not INCHIKEY_RE.fullmatch(inchikey.upper()):
        return ""
    url = (
        "https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/inchikey/"
        f"{urllib.parse.quote(inchikey.upper())}/property/IsomericSMILES,CanonicalSMILES/JSON"
    )
    try:
        with urllib.request.urlopen(url, timeout=8, context=HTTP_CONTEXT) as response:
            payload = json.loads(response.read().decode("utf-8"))
        props = payload.get("PropertyTable", {}).get("Properties", [])
        if not props:
            return ""
        return str(props[0].get("IsomericSMILES") or props[0].get("CanonicalSMILES") or "").strip()
    except Exception:
        return ""


def mol_from_row(row: dict):
    for value in (row.get("smiles"), row.get("inchi")):
        text = str(value or "").strip()
        if not text:
            continue
        try:
            mol = Chem.MolFromInchi(text) if text.startswith("InChI=") else Chem.MolFromSmiles(text)
            if mol is not None:
                return mol, "inchi" if text.startswith("InChI=") else "smiles"
        except Exception:
            pass
    inchikey = str(row.get("inchikey") or "").strip().upper()
    smiles = resolve_inchikey_to_smiles(inchikey)
    if smiles:
        mol = Chem.MolFromSmiles(smiles)
        if mol is not None:
            return mol, "inchikey_pubchem"
    return None, ""


def render_mol_png(mol) -> bytes:
    draw_mol = Chem.Mol(mol)
    try:
        rdDepictor.Compute2DCoords(draw_mol)
        rdDepictor.StraightenDepiction(draw_mol)
    except Exception:
        try:
            AllChem.Compute2DCoords(draw_mol)
        except Exception:
            pass
    drawer = rdMolDraw2D.MolDraw2DCairo(*IMAGE_SIZE)
    options = drawer.drawOptions()
    for name, value in {
        "clearBackground": True,
        "padding": 0.10,
        "bondLineWidth": 3.0,
        "multipleBondOffset": 0.16,
        "minFontSize": 22,
        "maxFontSize": 44,
        "legendFontSize": 22,
        "additionalAtomLabelPadding": 0.14,
    }.items():
        if hasattr(options, name):
            try:
                setattr(options, name, value)
            except Exception:
                pass
    drawer.DrawMolecule(draw_mol)
    drawer.FinishDrawing()
    with Image.open(io.BytesIO(drawer.GetDrawingText())) as image:
        contained = ImageOps.contain(image.convert("RGBA"), IMAGE_SIZE, method=Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", IMAGE_SIZE, (255, 255, 255, 255))
        canvas.paste(contained, ((IMAGE_SIZE[0] - contained.width) // 2, (IMAGE_SIZE[1] - contained.height) // 2), contained)
        output = io.BytesIO()
        canvas.convert("RGB").save(output, format="PNG", optimize=True)
        return output.getvalue()


def upload_structure(base_url: str, key: str, compound_id: int, data: bytes) -> str:
    name = f"generated/compound_{compound_id}_structure_{datetime.now(UTC).strftime('%H%M%S_%f')}.png"
    path = f"/storage/v1/object/structures/{urllib.parse.quote(name, safe='/')}"
    request = urllib.request.Request(
        f"{base_url.rstrip()}{path}",
        data=data,
        method="POST",
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "image/png",
            "x-upsert": "true",
        },
    )
    with urllib.request.urlopen(request, timeout=60, context=HTTP_CONTEXT):
        pass
    return f"storage://structures/{name}"


def update_local_structure_path(compound_id: int, path: str) -> None:
    if not DB_PATH.exists():
        return
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "UPDATE compounds SET structure_image_path = ?, updated_at = ? WHERE id = ?",
            (path, datetime.now(UTC).isoformat(), compound_id),
        )
        conn.commit()
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="Write generated images to Supabase and update compound rows.")
    parser.add_argument("--include-existing-generated", action="store_true", help="Refresh all generated storage images, not only blank paths.")
    parser.add_argument("--name", action="append", default=[], help="Only repair rows whose trivial name contains this text. Can be repeated.")
    args = parser.parse_args()

    secrets = read_secrets()
    base_url = secret_value(secrets, "SUPABASE_URL")
    key = secret_value(secrets, "SUPABASE_SERVICE_ROLE_KEY", "SUPABASE_SECRET_KEY")
    if not base_url or not is_write_key(key):
        raise SystemExit("Supabase URL/service role key is required.")

    rows = paged_select(base_url, key, "compounds", "id,trivial_name,smiles,inchi,inchikey,structure_image_path")
    name_filters = [item.casefold() for item in args.name if item.strip()]
    report_rows = []
    for row in rows:
        compound_id = int(row["id"])
        trivial_name = str(row.get("trivial_name") or "")
        current_path = str(row.get("structure_image_path") or "").strip()
        if name_filters and not any(token in trivial_name.casefold() for token in name_filters):
            continue
        needs_repair = not current_path
        if args.include_existing_generated and current_path.startswith("storage://structures/generated/"):
            needs_repair = True
        if not needs_repair:
            continue
        mol, source = mol_from_row(row)
        status = "skipped"
        new_path = ""
        detail = "no renderable SMILES/InChI/InChIKey"
        if mol is not None:
            detail = source
            if args.apply:
                try:
                    new_path = upload_structure(base_url, key, compound_id, render_mol_png(mol))
                    request_json(
                        "PATCH",
                        base_url,
                        key,
                        "/rest/v1/compounds",
                        query={"id": f"eq.{compound_id}", "select": "id"},
                        body={"structure_image_path": new_path, "updated_at": datetime.now(UTC).isoformat()},
                    )
                    update_local_structure_path(compound_id, new_path)
                    status = "updated"
                except Exception as exc:
                    status = "error"
                    detail = str(exc)[:500]
            else:
                status = "would_update"
        report_rows.append(
            {
                "compound_id": compound_id,
                "trivial_name": trivial_name,
                "old_structure_image_path": current_path,
                "new_structure_image_path": new_path,
                "status": status,
                "detail": detail,
            }
        )

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    report_path = EXPORT_DIR / f"structure_image_repair_{datetime.now(UTC).strftime('%Y%m%d_%H%M%S')}.csv"
    with report_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "compound_id",
                "trivial_name",
                "old_structure_image_path",
                "new_structure_image_path",
                "status",
                "detail",
            ],
        )
        writer.writeheader()
        writer.writerows(report_rows)

    print(f"Rows inspected: {len(rows)}")
    print(f"Rows in report: {len(report_rows)}")
    print(f"Updated: {sum(1 for item in report_rows if item['status'] == 'updated')}")
    print(f"Report: {report_path}")
    return 1 if any(item["status"] == "error" for item in report_rows) else 0


if __name__ == "__main__":
    raise SystemExit(main())
