"""NPDB real local SQLite persistence checks: isolated AST of production functions.

This test imports no Streamlit app, reads no .streamlit secrets, opens no network
connection and uses only a brand-new TemporaryDirectory database. Every field
is read back via a distinct SQLite connection (not an in-memory fake store).
"""
import ast
from datetime import UTC, datetime
import inspect
from pathlib import Path
import sqlite3
import tempfile
import unittest
from authorization_fixture import bind_authorization


APP = Path(__file__).resolve().parents[1] / "scripts" / "app.py"

def load_function(name, namespace):
    if "require_backend_permission" not in namespace:
        for key, value in bind_authorization().items():
            namespace.setdefault(key, value)
    tree = ast.parse(APP.read_text(encoding="utf-8"), filename=str(APP))
    definitions = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == name]
    assert definitions, f"App function {name!r} must exist"
    exec(compile(ast.Module(body=[definitions[-1]], type_ignores=[]), str(APP), "exec"), namespace)
    return namespace[name]


class ProductionFunctionSqliteRoundtrip(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="npdb-synthetic-sqlite-")
        self.addCleanup(self.tmp.cleanup)
        self.db_file = Path(self.tmp.name) / "synthetic-only.sqlite3"
        self.events = []
        self.invalidations = []
        self.network_invocations = []

        def connection():
            c = sqlite3.connect(self.db_file)
            c.execute("PRAGMA foreign_keys = ON")
            return c

        def forbid_network(*args, **kwargs):
            self.network_invocations.append((args, kwargs))
            raise AssertionError("No production network or Supabase access is permitted")

        self.ns = {
            "get_connection": connection,
            "ensure_write_target_ready": lambda: None,
            "use_supabase_write_backend": lambda: False,
            "supabase_insert_row": forbid_network,
            "supabase_update_row": forbid_network,
            "supabase_column_available": forbid_network,
            "_auto_structure_image_path": lambda *args, **kwargs: "",
            "record_audit_event": lambda *args, **kwargs: self.events.append((args, kwargs)),
            "invalidate_cached_views": lambda: self.invalidations.append(True),
            "maybe_blank": lambda x: str(x or "").strip(),
            "CURATION_STATUS_OPTIONS": ["imported", "curated", "reviewed"],
            "datetime": datetime,
            "UTC": UTC,
        }
        for name in (
            "ensure_columns_with_cursor",
            "ensure_database_schema",
            "_sqlite_columns",
            "_sqlite_upsert_row",
            "normalize_curation_status",
            "insert_compound_record",
        ):
            load_function(name, self.ns)
        self.ns["ensure_database_schema"]()

    def example_submission(self):
        fields = {
            "trivial_name": "SYNTHETIC-SPEC-0001",
            "iupac_name": "synthetic non-research example name",
            "molecular_formula": "C2H6O",
            "compound_class": "synthetic class",
            "compound_subclass": "synthetic subclass",
            "smiles": "",
            "inchi": "",
            "inchikey": "",
            "source_category": "Test organism",
            "source_organism": "Syntheticus exemplaris",
            "source_material": "synthetic dry sample",
            "sample_code": "QA-TEST-001",
            "collection_location": "TEST-NOT-REAL-LOCATION",
            "gps_coordinates": "NOT-A-REAL-GPS",
            "depth_m": 12.5,
            "uv_data": "UV lambda_max 220 nm synthetic",
            "ftir_data": "IR nu 1700 cm-1 synthetic",
            "cd_data": "ECD test synthetic",
            "optical_rotation": "[alpha]D +12.1 synthetic",
            "melting_point": "120-122 C synthetic",
            "crystallization_method": "test solvent evaporation",
            "structure_image_path": "",
            "journal_name": "Journal of Synthetic Test Data",
            "article_title": "Synthetic persistence fixture; not a publication",
            "publication_year": "2026",
            "volume": "1",
            "issue": "2",
            "pages": "10-20",
            "doi": "10.0000/synthetic-not-real",
            "ccdc_number": "TEST-CCDC-ONLY",
            "molecular_weight": 46.07,
            "hrms_data": "test m/z 100.1234",
            "data_source": "Synthetic QA",
            "curation_status": "imported",
            "note": "Synthetic test note. No real compound data.",
        }
        signature = inspect.signature(self.ns["insert_compound_record"])
        self.assertEqual(set(signature.parameters), set(fields),
                         "Any added or removed compound metadata field requires updating this test.")
        return fields

    def query_one(self, table, identifier):
        with self.ns["get_connection"]() as conn:
            conn.row_factory = sqlite3.Row
            return conn.execute(f"SELECT * FROM {table} WHERE id = ?", (identifier,)).fetchone()

    def test_every_submitted_field_roundtrips_through_real_sqlite_connection(self):
        fields = self.example_submission()
        new_id = self.ns["insert_compound_record"](**fields)
        self.assertIsInstance(new_id, int)
        self.assertGreater(new_id, 0)
        persisted = self.query_one("compounds", new_id)
        self.assertIsNotNone(persisted)
        for field, expected in fields.items():
            self.assertEqual(persisted[field], expected,
                             f"{field} changed or vanished during SQLite insert/read-back")
        self.assertTrue(persisted["created_at"])
        self.assertTrue(persisted["updated_at"])
        self.assertEqual(self.query_one("compounds", new_id)["sample_code"], "QA-TEST-001")
        self.assertEqual(len(self.network_invocations), 0)
        self.assertEqual(len(self.events), 1, "Successful insert should emit exactly one audit call")
        self.assertEqual(self.events[0][0][:2], ("insert", "compounds"))

    def test_partial_update_preserves_unmodified_source_and_spectra(self):
        fields = self.example_submission()
        new_id = self.ns["insert_compound_record"](**fields)
        changed = self.ns["_sqlite_upsert_row"]("compounds", {
            "id": new_id, "trivial_name": "SYNTHETIC-RENAMED-0001",
            "updated_at": datetime.now(UTC).isoformat(),
        })
        self.assertEqual(changed, new_id)
        persisted = self.query_one("compounds", new_id)
        self.assertEqual(persisted["trivial_name"], "SYNTHETIC-RENAMED-0001")
        for field, expected in fields.items():
            if field == "trivial_name":
                continue
            self.assertEqual(persisted[field], expected,
                             f"Unmodified field {field} must survive partial update")

    def test_foreign_key_constraints_block_orphan_nmr_and_allow_child_records(self):
        with self.ns["get_connection"]() as conn:
            with self.assertRaises(sqlite3.IntegrityError):
                conn.execute("INSERT INTO proton_nmr (compound_id,delta_ppm) VALUES (?,?)", (999999, 3.52))
        new_id = self.ns["insert_compound_record"](**self.example_submission())
        with self.ns["get_connection"]() as conn:
            conn.execute("INSERT INTO proton_nmr (compound_id,delta_ppm,solvent,instrument_mhz) VALUES (?,?,?,?)", (new_id, 3.52, "CDCl3", 500))
            conn.execute("INSERT INTO carbon_nmr (compound_id,delta_ppm,solvent) VALUES (?,?,?)", (new_id, 55.2, "CDCl3"))
            conn.execute("INSERT INTO spectra_files (compound_id,spectrum_type,file_path) VALUES (?,?,?)", (new_id, "1H", "synthetic-no-file"))
            conn.execute("INSERT INTO bioactivity_records (compound_id,activity_label) VALUES (?,?)", (new_id, "synthetic no activity"))
        with self.ns["get_connection"]() as conn:
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM proton_nmr WHERE compound_id=?", (new_id,)).fetchone()[0], 1)
            self.assertEqual(conn.execute("SELECT COUNT(*) FROM carbon_nmr WHERE compound_id=?", (new_id,)).fetchone()[0], 1)
            conn.execute("DELETE FROM compounds WHERE id=?", (new_id,))
            for table in ("proton_nmr","carbon_nmr","spectra_files","bioactivity_records"):
                self.assertEqual(conn.execute(f"SELECT COUNT(*) FROM {table} WHERE compound_id=?", (new_id,)).fetchone()[0], 0)


if __name__ == "__main__":
    unittest.main()
