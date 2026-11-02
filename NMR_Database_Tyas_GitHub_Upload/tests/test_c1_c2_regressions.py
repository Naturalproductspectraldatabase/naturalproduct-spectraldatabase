"""Isolated NPDB C1/C2 regression tests; no app import, network, or production DB.

Run from a repository checkout:
    python -m unittest discover -s NMR_Database_Tyas_GitHub_Upload/tests -p 'test_c1_c2_regressions.py' -v

The intentionally failing expectations are annotated @expectedFailure to document
known defects on main. A fix should turn them into unexpected successes; then
remove @expectedFailure and keep the passing regression tests.
"""

import ast
import copy
from datetime import UTC, datetime
import inspect
from pathlib import Path
import unittest

import pandas as pd

APP_PATH = Path(__file__).resolve().parents[1] / "scripts" / "app.py"


def isolated_function(name, namespace):
    """Compile only the final definition of a named function from the real app.

    Never imports app.py or executes its top-level Streamlit application, and
    never uses the real Supabase client or real credentials.
    """
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
        snapshot_rows = pd.DataFrame([{"id": 101, "trivial_name": "old snapshot", "source_category": ""}])
        live_rows = pd.DataFrame([{"id": 101, "trivial_name": "fresh cloud", "source_category": "Sponge"}])
        namespace = {
            "st": FakeStreamlitCache(),
            "DATA_CACHE_TTL_SECONDS": 60,
            "SOURCE_NORMALIZATION_CACHE_VERSION": "v1",
            "get_npdb_read_backend": lambda: state["backend"],
            "get_db_signature": lambda: f"{state['backend']}-signature",
            "compound_select_columns": lambda: "id,trivial_name,source_category",
            "enrich_compounds_dataframe": lambda df: df,
            "supabase_select_df": lambda *a, **k: live_rows.copy(),
            "_snapshot_dataframe": lambda *a, **k: snapshot_rows.copy(),
            "_sqlite_dataframe": lambda *a, **k: pd.DataFrame(),
            "pd": pd,
        }
        return state, namespace

    @unittest.expectedFailure
    def test_c1_list_cache_refreshes_after_snapshot_to_cloud_transition(self):
        state, ns = self.make_namespace()
        isolated_function("_load_all_compounds_cached", ns)
        load_all = isolated_function("load_all_compounds", ns)
        self.assertEqual(load_all().iloc[0]["trivial_name"], "old snapshot")
        state["backend"] = "supabase"
        self.assertEqual(load_all().iloc[0]["trivial_name"], "fresh cloud")

    @unittest.expectedFailure
    def test_c1_record_cache_refreshes_after_snapshot_to_cloud_transition(self):
        state, ns = self.make_namespace()
        isolated_function("_load_compound_row_cached", ns)
        load_one = isolated_function("load_compound_row", ns)
        self.assertEqual(load_one(101).iloc[0]["trivial_name"], "old snapshot")
        state["backend"] = "supabase"
        self.assertEqual(load_one(101).iloc[0]["trivial_name"], "fresh cloud")

    def test_isolated_harness_uses_dummy_records_only(self):
        state, ns = self.make_namespace()
        self.assertEqual(state["backend"], "snapshot")
        self.assertFalse(any("SUPABASE" in key for key in ns))


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

    @unittest.expectedFailure
    def test_c2_transient_network_failure_must_not_cache_column_absent(self):
        state, probe = self.make_probe()
        try:
            self.assertFalse(probe("compounds", "curation_status"))
        except RuntimeError:
            pass  # Safe fix may propagate transient failure rather than cache False.
        state["healthy"] = True
        self.assertTrue(probe("compounds", "curation_status"))

    def test_c2_positive_probe_works_with_fake_network(self):
        state, probe = self.make_probe()
        state["healthy"] = True
        self.assertTrue(probe("compounds", "curation_status"))
        self.assertEqual(state["requests"], 1)

    @unittest.expectedFailure
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
            "supabase_update_row": lambda *a: patches.append(a),
            "use_local_read_backend": lambda: False,
            "invalidate_cached_views": lambda: None,
            "_upsert_compound_local": lambda row: None,
        }
        update = isolated_function("update_compound_record", ns)
        kwargs = {name: "" for name in inspect.signature(update).parameters}
        kwargs.update(compound_id=101, structure_image_path="dummy.png", curation_status="reviewed")
        try:
            update(**kwargs)
        except RuntimeError:
            pass  # Explicit refusal is an acceptable safe behavior.
        self.assertEqual(patches, [], "Unknown column status must block the save, not silently omit curation_status")


class ConcurrentEditRegressionTests(unittest.TestCase):
    @unittest.expectedFailure
    def test_c1_patch_requires_record_version_in_addition_to_id(self):
        calls = []

        def fake_request(*args, **kwargs):
            calls.append({"args": args, "kwargs": kwargs})
            return [{"id": 101}]

        ns = {
            "_json_ready": lambda x: x,
            "_supabase_request": fake_request,
            "record_audit_event": lambda *a, **k: None,
        }
        patch = isolated_function("supabase_update_row", ns)
        patch("compounds", 101, {"trivial_name": "edited", "updated_at": "2026-11-02T00:00:00Z"})
        self.assertEqual(len(calls), 1)
        filters = calls[0]["kwargs"]["query"]
        self.assertTrue(any(k in filters for k in ("updated_at", "version", "revision")), "PATCH needs an optimistic-concurrency predicate")


if __name__ == "__main__":
    unittest.main()
