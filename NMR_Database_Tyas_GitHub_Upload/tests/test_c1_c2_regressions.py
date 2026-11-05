"""Isolated C1/C2 regression tests against real app.py function definitions.

Run from a repository checkout:
    python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_c1_c2_regressions.py' -v

The suite uses dummy records and mocked Supabase/Streamlit interfaces.
It does not import app.py as a full app, read secrets, or contact production.
The tests are intended to pass on the C1/C2 fix branch (and to fail on main).
"""

import ast
import copy
from datetime import UTC, datetime
import inspect
from functools import wraps
from pathlib import Path
import unittest
from authorization_fixture import bind_authorization

import pandas as pd

APP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "app.py"


def isolated_function(name, namespace):
    """Compile only the final definition of a named function from the real app.

    Never imports app.py or executes its top-level Streamlit application, and
    never uses the real Supabase client or real credentials.
    """
    if "require_backend_permission" not in namespace:
        for key, value in bind_authorization(role="viewer").items():
            namespace.setdefault(key, value)
    tree = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
    matches = [node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == name]
    if not matches:
        raise AssertionError(f"Expected function {name!r} not found in {APP_PATH}")
    node = matches[-1]
    compiled = compile(ast.Module(body=[node], type_ignores=[]), str(APP_PATH), "exec")
    exec(compiled, namespace)  # Executing one isolated function definition, not app startup.
    return namespace[name]


class FakeStreamlitCache:
    """Small stand-in matching st.cache_data's underscore-argument exemption."""

    def cache_data(self, *args, **kwargs):
        def decorate(func):
            cache = {}
            signature = inspect.signature(func)

            @wraps(func)
            def wrapped(*positional, **named):
                bound = signature.bind(*positional, **named)
                bound.apply_defaults()
                cache_key = tuple(
                    (key, repr(value))
                    for key, value in bound.arguments.items()
                    if not key.startswith("_")
                )
                if cache_key not in cache:
                    cache[cache_key] = copy.deepcopy(func(*positional, **named))
                return copy.deepcopy(cache[cache_key])

            wrapped.clear = cache.clear
            return wrapped

        return decorate


class SourceAndCacheRegressionTests(unittest.TestCase):
    def make_namespace(self):
        state = {"backend": "snapshot"}
        snapshot_rows = pd.DataFrame([{"id": 101, "trivial_name": "old snapshot", "source_category": "", "gps_coordinates": "SYNTHETIC-GPS-SNAPSHOT"}])
        live_rows = pd.DataFrame([{"id": 101, "trivial_name": "fresh cloud", "source_category": "Sponge", "gps_coordinates": "SYNTHETIC-GPS-CLOUD"}])
        namespace = {
            "st": FakeStreamlitCache(),
            "DATA_CACHE_TTL_SECONDS": 60,
            "SOURCE_NORMALIZATION_CACHE_VERSION": "v1",
            "get_npdb_read_backend": lambda: state["backend"],
            "get_db_signature": lambda: f"{state['backend']}-signature",
            "current_backend_role": lambda: "viewer",
            "compound_select_columns": lambda: "id,trivial_name,source_category",
            "enrich_compounds_dataframe": lambda df: df,
            "supabase_select_df": lambda *a, **k: live_rows.copy(),
            "_snapshot_dataframe": lambda *a, **k: snapshot_rows.copy(),
            "_sqlite_dataframe": lambda *a, **k: pd.DataFrame(),
            "pd": pd,
        }
        # Cached read wrappers now enforce per-role GPS redaction after cache lookup.
        # Compile the actual helper into the isolated namespace rather than
        # replacing it with a no-op that could hide a privacy regression.
        isolated_function("redact_private_gps_for_current_user", namespace)
        return state, namespace

    def test_c1_list_cache_refreshes_after_snapshot_to_cloud_transition(self):
        state, ns = self.make_namespace()
        isolated_function("_load_all_compounds_cached", ns)
        load_all = isolated_function("load_all_compounds", ns)
        self.assertEqual(load_all().iloc[0]["trivial_name"], "old snapshot")
        self.assertIsNone(load_all().iloc[0]["gps_coordinates"])
        state["backend"] = "supabase"
        self.assertEqual(load_all().iloc[0]["trivial_name"], "fresh cloud")
        self.assertIsNone(load_all().iloc[0]["gps_coordinates"])

    def test_c1_record_cache_refreshes_after_snapshot_to_cloud_transition(self):
        state, ns = self.make_namespace()
        isolated_function("_load_compound_row_cached", ns)
        load_one = isolated_function("load_compound_row", ns)
        self.assertEqual(load_one(101).iloc[0]["trivial_name"], "old snapshot")
        self.assertIsNone(load_one(101).iloc[0]["gps_coordinates"])
        state["backend"] = "supabase"
        self.assertEqual(load_one(101).iloc[0]["trivial_name"], "fresh cloud")
        self.assertIsNone(load_one(101).iloc[0]["gps_coordinates"])

    def test_isolated_harness_uses_dummy_records_only(self):
        state, ns = self.make_namespace()
        self.assertEqual(state["backend"], "snapshot")
        self.assertFalse(any("SUPABASE" in key for key in ns))

    def test_target_function_definitions_are_present(self):
        tree = ast.parse(APP_PATH.read_text(encoding="utf-8"), filename=str(APP_PATH))
        names = {node.name for node in tree.body if isinstance(node, ast.FunctionDef)}
        expected = {
            "_load_all_compounds_cached", "_load_compound_row_cached",
            "load_all_compounds", "load_compound_row",
            "supabase_column_available", "update_compound_record", "supabase_update_row",
        }
        self.assertFalse(expected - names, f"Missing application functions: {expected - names}")


class ColumnProbeRegressionTests(unittest.TestCase):
    def make_probe(self):
        state = {"healthy": False, "requests": 0}

        def fake_request(*args, **kwargs):
            state["requests"] += 1
            if not state["healthy"]:
                raise RuntimeError("Supabase connection failed: timed out")
            return []

        ns = {
            "st": FakeStreamlitCache(),
            "use_supabase_backend": lambda: True,
            "_supabase_request": fake_request,
            "RuntimeError": RuntimeError,
        }
        probe = isolated_function("supabase_column_available", ns)
        return state, probe

    def test_c2_transient_network_failure_must_not_cache_column_absent(self):
        state, probe = self.make_probe()
        with self.assertRaises(RuntimeError):
            probe("compounds", "curation_status")
        state["healthy"] = True
        self.assertTrue(probe("compounds", "curation_status"))
        self.assertEqual(state["requests"], 2, "Transient errors must not poison the cache")

    def test_c2_positive_probe_works_with_fake_network(self):
        state, probe = self.make_probe()
        state["healthy"] = True
        self.assertTrue(probe("compounds", "curation_status"))
        self.assertEqual(state["requests"], 1)

    def test_c2_unknown_schema_must_block_write_instead_of_dropping_status(self):
        patches = []
        ns = {
            "UTC": UTC,
            "datetime": datetime,
            "ensure_write_target_ready": lambda: None,
            "maybe_blank": lambda val: str(val or "").strip(),
            "_auto_structure_image_path": lambda *a, **k: "dummy.png",
            "normalize_curation_status": lambda val, default="curated": val or default,
            "use_supabase_write_backend": lambda: True,
            "supabase_column_available": lambda *a, **k: False,  # Uncertain after network failure.
            "supabase_update_row": lambda *a, **k: patches.append((a, k)),
            "use_local_read_backend": lambda: False,
            "get_npdb_read_backend": lambda: "supabase",
            "invalidate_cached_views": lambda: None,
            "_upsert_compound_local": lambda row: None,
        }
        update = isolated_function("update_compound_record", ns)
        kwargs = {
            name: "" for name in inspect.signature(update).parameters
            if name != "original_row"
        }
        kwargs.update(compound_id=101, structure_image_path="dummy.png", curation_status="reviewed")
        original = {key: value for key, value in kwargs.items() if key != "compound_id"}
        original["updated_at"] = "2026-11-01T10:00:00+00:00"
        kwargs["original_row"] = original
        with self.assertRaisesRegex(RuntimeError, "curation_status"):
            update(**kwargs)
        self.assertEqual(patches, [], "Unknown column status must block writes")


class ConcurrentEditRegressionTests(unittest.TestCase):
    def test_c1_patch_requires_record_version_in_addition_to_id(self):
        calls = []

        def fake_request(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return [{"id": 101}]

        ns = {
            "_json_ready": lambda x: x,
            "maybe_blank": lambda x: str(x or "").strip(),
            "_supabase_request": fake_request,
            "record_audit_event": lambda *a, **k: None,
        }
        patch = isolated_function("supabase_update_row", ns)
        revision = "2026-11-01T10:00:00+00:00"
        patch(
            "compounds", 101, {"trivial_name": "edited", "updated_at": "2026-11-02T00:00:00Z"},
            expected_updated_at=revision,
        )
        self.assertEqual(len(calls), 1)
        filters = calls[0]["kwargs"]["query"]
        self.assertEqual(filters["id"], "eq.101")
        self.assertEqual(filters["updated_at"], "eq." + revision)

    def test_c1_stale_row_conflict_is_reported_and_not_audited(self):
        calls, events = [], []

        def fake_request(*args, **kwargs):
            calls.append(kwargs)
            return []  # Fake PostgREST: no row matched the original revision.

        ns = {
            "_json_ready": lambda x: x,
            "maybe_blank": lambda x: str(x or "").strip(),
            "_supabase_request": fake_request,
            "record_audit_event": lambda *a, **k: events.append((a, k)),
        }
        patch = isolated_function("supabase_update_row", ns)
        with self.assertRaisesRegex(RuntimeError, "changed or removed"):
            patch(
                "compounds", 101, {"trivial_name": "stale"},
                expected_updated_at="2026-11-01T10:00:00+00:00",
            )
        self.assertEqual(len(calls), 1)
        self.assertEqual(events, [], "Failed CAS must not generate a successful update audit event")

    def test_c1_missing_original_revision_blocks_compound_save(self):
        ns = {
            "UTC": UTC, "datetime": datetime,
            "ensure_write_target_ready": lambda: None,
            "maybe_blank": lambda x: str(x or "").strip(),
            "_auto_structure_image_path": lambda *a, **k: "dummy.png",
            "normalize_curation_status": lambda x, default="curated": x or default,
            "use_supabase_write_backend": lambda: True,
            "get_npdb_read_backend": lambda: "supabase",
        }
        update = isolated_function("update_compound_record", ns)
        kwargs = {
            name: "" for name in inspect.signature(update).parameters
            if name != "original_row"
        }
        kwargs.update(compound_id=101, structure_image_path="dummy.png")
        with self.assertRaisesRegex(RuntimeError, "original record revision"):
            update(**kwargs)

    def test_c1_compound_update_patches_only_changed_fields(self):
        patches = []
        ns = {
            "UTC": UTC, "datetime": datetime,
            "ensure_write_target_ready": lambda: None,
            "maybe_blank": lambda x: str(x or "").strip(),
            "_auto_structure_image_path": lambda *a, **k: "dummy.png",
            "normalize_curation_status": lambda x, default="curated": x or default,
            "use_supabase_write_backend": lambda: True,
            "get_npdb_read_backend": lambda: "supabase",
            "supabase_column_available": lambda *a, **k: True,
            "supabase_update_row": lambda *a, **k: patches.append((a, k)),
            "use_local_read_backend": lambda: False,
            "invalidate_cached_views": lambda: None,
            "_readback_value_matches": lambda old, new: old == new,
        }
        update = isolated_function("update_compound_record", ns)
        kwargs = {
            name: "" for name in inspect.signature(update).parameters
            if name != "original_row"
        }
        kwargs.update(
            compound_id=101, trivial_name="New name",
            structure_image_path="dummy.png", curation_status="reviewed",
        )
        baseline = {name: val for name, val in kwargs.items() if name != "compound_id"}
        baseline["trivial_name"] = "Old name"
        baseline["updated_at"] = "2026-11-01T12:00:00+00:00"
        kwargs["original_row"] = baseline
        update(**kwargs)
        self.assertEqual(len(patches), 1)
        args, call_kwargs = patches[0]
        self.assertEqual(args[:2], ("compounds", 101))
        self.assertEqual(set(args[2]), {"trivial_name", "updated_at"})
        self.assertEqual(args[2]["trivial_name"], "New name")
        self.assertEqual(call_kwargs["expected_updated_at"], baseline["updated_at"])

    def test_c1_noop_edit_does_not_write_whole_record(self):
        patches = []
        ns = {
            "UTC": UTC, "datetime": datetime,
            "ensure_write_target_ready": lambda: None,
            "maybe_blank": lambda x: str(x or "").strip(),
            "_auto_structure_image_path": lambda *a, **k: "dummy.png",
            "normalize_curation_status": lambda x, default="curated": x or default,
            "use_supabase_write_backend": lambda: True,
            "get_npdb_read_backend": lambda: "supabase",
            "supabase_column_available": lambda *a, **k: True,
            "supabase_update_row": lambda *a, **k: patches.append((a, k)),
            "use_local_read_backend": lambda: False,
            "invalidate_cached_views": lambda: None,
            "_readback_value_matches": lambda old, new: old == new,
        }
        update = isolated_function("update_compound_record", ns)
        kwargs = {
            name: "" for name in inspect.signature(update).parameters
            if name != "original_row"
        }
        kwargs.update(compound_id=101, structure_image_path="dummy.png", curation_status="reviewed")
        baseline = {name: val for name, val in kwargs.items() if name != "compound_id"}
        baseline["updated_at"] = "2026-11-01T12:00:00+00:00"
        kwargs["original_row"] = baseline
        update(**kwargs)
        self.assertEqual(patches, [], "A form with no changes must not PATCH 36 old fields")

    def test_c1_preflight_rejects_a_changed_cloud_revision(self):
        ns = {
            "use_supabase_write_backend": lambda: True,
            "get_npdb_read_backend": lambda: "supabase",
            "maybe_blank": lambda x: str(x or "").strip(),
            "datetime": datetime,
            "_supabase_request": lambda *a, **k: [
                {"id": 101, "updated_at": "2026-11-02T09:00:00+00:00"}
            ],
        }
        isolated_function("_revision_matches", ns)
        preflight = isolated_function("verify_compound_editor_revision", ns)
        with self.assertRaisesRegex(RuntimeError, "changed in another session"):
            preflight(101, "2026-11-01T09:00:00+00:00")

    def test_c1_revision_helper_accepts_equivalent_time_zone_offsets(self):
        ns = {"datetime": datetime, "maybe_blank": lambda x: str(x or "").strip()}
        matches = isolated_function("_revision_matches", ns)
        self.assertTrue(matches("2026-11-02T09:00:00+09:00", "2026-11-02T00:00:00+00:00"))
        self.assertFalse(matches("2026-11-02T00:00:01Z", "2026-11-02T00:00:00Z"))


if __name__ == "__main__":
    unittest.main()
