"""Actual serializer/asset callables must deny stale identities before body execution."""
import ast
from pathlib import Path
import unittest
from authorization_fixture import bind_authorization

APP=Path(__file__).resolve().parents[1]/'scripts/app.py'
TARGETS=('export_name_results','export_structure_search_results','export_similarity_results_13c',
 'export_similarity_results_1h','export_similarity_results_combined','build_compound_summary_text',
 'build_compound_record_bundle','export_bioactivity_results','download_dataframe_button',
 '_asset_bytes_from_source','read_scientific_asset','read_remote_scientific_asset')


class SinkAuthorization(unittest.TestCase):
    def test_actual_wrapped_sinks_deny_revoked_identity_before_argument_or_io_processing(self):
        tree=ast.parse(APP.read_text())
        ns=bind_authorization()
        # Real function definitions, including the outer auth decorator. Postponed
        # annotation evaluation avoids importing application/UI/data dependencies.
        for name in TARGETS:
            node=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name][-1]
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(APP),'exec',flags=__import__('__future__').annotations.compiler_flag),ns)
        ns['st'].session_state['npdb_authenticated']=False
        for name in TARGETS:
            with self.subTest(sink=name):
                # Missing arguments would raise TypeError if the original body
                # or signature dispatch ran before current authorization.
                with self.assertRaises(PermissionError):ns[name]()
