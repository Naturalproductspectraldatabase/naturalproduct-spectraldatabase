#!/usr/bin/env python3
"""Run safe owner/viewer workflow audits against the NPDB app.

The script creates temporary audit records, verifies save/read-back behavior,
then removes the temporary database rows and generated storage objects. It does
not read or modify Tyas' batch-import spreadsheets.
"""

from __future__ import annotations

import json
import ssl
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from streamlit.testing.v1 import AppTest

try:
    import certifi
except Exception:  # pragma: no cover
    certifi = None  # type: ignore

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover
    import tomli as tomllib  # type: ignore


PROJECT_DIR = Path(__file__).resolve().parents[1]
APP_PATH = PROJECT_DIR / "scripts" / "app.py"
SECRETS_PATH = PROJECT_DIR / ".streamlit" / "secrets.toml"
HTTP_CONTEXT = ssl.create_default_context(cafile=certifi.where()) if certifi else None


@dataclass
class Result:
    name: str
    ok: bool
    detail: str = ""


class AuditClient:
    def __init__(self) -> None:
        secrets = tomllib.load(SECRETS_PATH.open("rb"))
        self.url = str(secrets["SUPABASE_URL"]).rstrip("/")
        self.key = str(
            secrets.get("SUPABASE_SECRET_KEY")
            or secrets.get("SUPABASE_SERVICE_ROLE_KEY")
            or secrets.get("SUPABASE_SERVICE_KEY")
            or ""
        )
        if not self.key:
            raise RuntimeError("No server-side Supabase write key configured in local secrets.")

    def request(
        self,
        method: str,
        path: str,
        query: dict[str, str] | None = None,
        body: Any = None,
        prefer: str = "return=representation",
        json_body: bool = True,
    ) -> Any:
        endpoint = self.url + path
        if query:
            endpoint += "?" + urllib.parse.urlencode(query)
        data = None
        headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Prefer": prefer,
        }
        if body is not None:
            if json_body:
                headers["Content-Type"] = "application/json"
                data = json.dumps(body).encode("utf-8")
            else:
                data = body
        request = urllib.request.Request(endpoint, data=data, method=method, headers=headers)
        with urllib.request.urlopen(request, timeout=90, context=HTTP_CONTEXT) as response:
            payload = response.read().decode("utf-8")
        return json.loads(payload) if payload else []

    def delete_compound_tree(self, compound_id: int) -> None:
        for table in ("proton_nmr", "carbon_nmr", "spectra_files", "bioactivity_records"):
            self.request("DELETE", f"/rest/v1/{table}", {"compound_id": f"eq.{compound_id}"}, prefer="return=minimal")
        self.request("DELETE", "/rest/v1/compounds", {"id": f"eq.{compound_id}"}, prefer="return=minimal")

    def delete_structure_object(self, storage_url: str) -> None:
        if not storage_url.startswith("storage://structures/"):
            return
        object_path = storage_url.removeprefix("storage://structures/")
        encoded_path = urllib.parse.quote(object_path, safe="/")
        self.request("DELETE", f"/storage/v1/object/structures/{encoded_path}", prefer="return=minimal")


def authenticated_app(role: str = "owner_editor") -> AppTest:
    app = AppTest.from_file(str(APP_PATH), default_timeout=120)
    app.session_state["npdb_authenticated"] = True
    app.session_state["npdb_username"] = "npdb_tyas" if role == "owner_editor" else "npdb_tjomori"
    app.session_state["npdb_role"] = role
    return app


def widget_values(app: AppTest) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for collection in (app.text_input, app.text_area, app.selectbox):
        for widget in collection:
            key = getattr(widget, "key", None)
            if key:
                values[key] = getattr(widget, "value", None)
    return values


def test_new_submission_full_metadata(client: AuditClient) -> Result:
    name = f"__NPDB_AUDIT_UI_{int(time.time())}__"
    created_id: int | None = None
    generated_structure = ""
    try:
        app = authenticated_app("owner_editor")
        state = app.session_state
        state["nav_section"] = "Compound Workspace"
        state["compound_page"] = "New Submission"
        state["compound_wizard_step"] = 4
        values = {
            "wizard_trivial_name": name,
            "wizard_iupac_name": "audit iupac",
            "wizard_formula": "C7H8",
            "wizard_molecular_weight": "92.14",
            "wizard_smiles": "CC1=CC=CC=C1",
            "wizard_inchi": "",
            "wizard_inchikey": "",
            "wizard_compound_class_select": "Custom...",
            "wizard_compound_class_custom": "Audit Class",
            "wizard_compound_subclass_select": "Custom...",
            "wizard_compound_subclass_custom": "Audit Subclass",
            "wizard_data_source_select": "Custom...",
            "wizard_data_source_custom": "Audit Source",
            "wizard_source_category_select": "Custom...",
            "wizard_source_category_custom": "Marine Sponge",
            "wizard_source_organism": "Audit sp.",
            "wizard_sample_code": "AUDIT-SAMPLE",
            "wizard_collection_location": "Audit Bay",
            "wizard_gps_coordinates": "1.23,4.56",
            "wizard_depth_m": "12.5",
            "wizard_uv_data": "UV audit",
            "wizard_ftir_data": "FTIR audit",
            "wizard_cd_data": "ECD audit",
            "wizard_optical_rotation": "[a]D audit",
            "wizard_melting_point": "100-101 C",
            "wizard_crystallization_method": "MeOH",
            "wizard_ccdc_number": "CCDC-AUDIT",
            "wizard_hrms_data": "HRMS audit",
            "wizard_structure_path": "",
            "wizard_submission_spectrum_type_select": "Supporting Data",
            "wizard_submission_spectra_note": "",
            "wizard_journal_name": "Audit Journal",
            "wizard_article_title": "Audit Article",
            "wizard_publication_year": "2026",
            "wizard_volume": "1",
            "wizard_issue": "2",
            "wizard_pages": "3-4",
            "wizard_doi": "10.0000/npdb.audit",
            "wizard_curation_status": "Draft",
            "wizard_note": "audit note",
        }
        for key, value in values.items():
            state[key] = value
            state[f"_draft_{key}"] = value
        app.run(timeout=120)
        if app.exception:
            return Result("owner new submission page", False, str(app.exception[0]))
        app.button(key="wizard_submit_compound").click().run(timeout=120)
        if app.exception:
            return Result("owner new submission save", False, str(app.exception[0]))
        errors = [getattr(item, "value", str(item)) for item in app.error]
        if errors:
            return Result("owner new submission save", False, "; ".join(errors))

        rows = client.request(
            "GET",
            "/rest/v1/compounds",
            {
                "select": "id,trivial_name,source_category,source_organism,collection_location,gps_coordinates,uv_data,ftir_data,cd_data,optical_rotation,melting_point,crystallization_method,ccdc_number,hrms_data,data_source,structure_image_path",
                "trivial_name": f"eq.{name}",
            },
        )
        if not rows:
            return Result("owner new submission readback", False, "saved compound was not found")
        row = rows[0]
        created_id = int(row["id"])
        generated_structure = str(row.get("structure_image_path") or "")
        expected = {
            "source_category": "Marine Sponge",
            "source_organism": "Audit sp.",
            "collection_location": "Audit Bay",
            "gps_coordinates": "1.23,4.56",
            "uv_data": "UV audit",
            "ftir_data": "FTIR audit",
            "cd_data": "ECD audit",
            "optical_rotation": "[a]D audit",
            "melting_point": "100-101 C",
            "crystallization_method": "MeOH",
            "ccdc_number": "CCDC-AUDIT",
            "hrms_data": "HRMS audit",
            "data_source": "Audit Source",
        }
        for key, value in expected.items():
            if str(row.get(key) or "") != value:
                return Result("owner new submission readback", False, f"{key} mismatch")
        if not generated_structure:
            return Result("owner new submission auto structure", False, "no structure image path generated from SMILES")
        return Result("owner new submission full metadata", True, f"temporary compound {created_id} verified and cleaned")
    finally:
        if created_id is not None:
            client.delete_compound_tree(created_id)
        if generated_structure:
            client.delete_structure_object(generated_structure)


def test_update_metadata_record_switch(client: AuditClient) -> Result:
    stamp = int(time.time())
    name_a = f"__NPDB_AUDIT_SWITCH_A_{stamp}__"
    name_b = f"__NPDB_AUDIT_SWITCH_B_{stamp}__"
    created: list[int] = []
    try:
        for name, source in ((name_a, "Marine Sponge"), (name_b, "Marine Cyanobacteria")):
            row = {
                "trivial_name": name,
                "iupac_name": f"{name} iupac",
                "molecular_formula": "C1H1",
                "source_category": source,
                "source_organism": f"{source} org",
                "collection_location": f"{source} location",
                "data_source": "Audit",
                "curation_status": "Draft",
            }
            inserted = client.request("POST", "/rest/v1/compounds", {"select": "id,trivial_name"}, row)[0]
            created.append(int(inserted["id"]))

        id_a, id_b = created
        app = authenticated_app("owner_editor")
        app.session_state["nav_section"] = "Compound Workspace"
        app.session_state["compound_page"] = "Update Metadata"
        app.session_state["selected_compound_id"] = id_a
        app.run(timeout=120)
        if app.exception:
            return Result("update metadata initial record", False, str(app.exception[0]))
        label_b = f"{id_b} - {name_b}"
        app.selectbox(key="edit_compound_select").select(label_b).run(timeout=120)
        if app.exception:
            return Result("update metadata record switch", False, str(app.exception[0]))
        values = widget_values(app)
        checks = {
            f"edit_trivial_name_{id_b}": name_b,
            f"edit_source_organism_{id_b}": "Marine Cyanobacteria org",
            f"edit_collection_location_{id_b}": "Marine Cyanobacteria location",
        }
        for key, expected in checks.items():
            if values.get(key) != expected:
                return Result("update metadata record switch", False, f"{key} showed {values.get(key)!r}")
        return Result("update metadata record switch", True, "selected record values did not leak from previous record")
    finally:
        for compound_id in created:
            client.delete_compound_tree(compound_id)


def test_viewer_read_only_pages() -> Result:
    forbidden = ("Save New Record", "Save Changes", "Delete Compound", "Save Spectra File")
    scenarios = [
        ("viewer-new-submission", {"nav_section": "Compound Workspace", "compound_page": "New Submission"}),
        ("viewer-update-metadata", {"nav_section": "Compound Workspace", "compound_page": "Update Metadata"}),
        ("viewer-delete-record", {"nav_section": "Compound Workspace", "compound_page": "Delete Record"}),
        ("viewer-spectra-library", {"nav_section": "Spectra Library", "spectra_page": "Add Files"}),
    ]
    for name, state in scenarios:
        app = authenticated_app("viewer")
        for key, value in state.items():
            app.session_state[key] = value
        app.run(timeout=120)
        if app.exception:
            return Result(name, False, str(app.exception[0]))
        labels = {getattr(button, "label", "") for button in app.button}
        exposed = sorted(label for label in labels if any(text in label for text in forbidden))
        if exposed:
            return Result(name, False, f"viewer saw write buttons: {', '.join(exposed)}")
    return Result("viewer read-only pages", True, "write actions are hidden for viewer role in audited pages")


def main() -> int:
    client = AuditClient()
    results = [
        test_update_metadata_record_switch(client),
        test_new_submission_full_metadata(client),
        test_viewer_read_only_pages(),
    ]
    failed = [item for item in results if not item.ok]
    for item in results:
        status = "PASS" if item.ok else "FAIL"
        print(f"{status}  {item.name}" + (f" - {item.detail}" if item.detail else ""))
    print()
    print(f"Deep workflow checks: {len(results) - len(failed)} passed, {len(failed)} failed.")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
