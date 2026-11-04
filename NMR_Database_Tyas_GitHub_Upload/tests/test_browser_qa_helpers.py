"""Synthetic presentation tests; no approved taxonomy or contact is fabricated."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from npdb_browser_qa import category_counts,display_class_term,display_source_term,compound_open_label,approved_recovery_route

class BrowserQaHelpersTests(unittest.TestCase):
    def test_case_and_spacing_aggregation_preserves_original_inputs(self):
        values=['Marine alga','Marine Alga',' Marine  Alga ',None,'']
        original=list(values)
        result=category_counts(values)
        self.assertEqual(sum(row['Count'] for row in result),5)
        self.assertEqual(sorted(row['Count'] for row in result),[2,3])
        self.assertEqual(values,original)

    def test_class_alias_requires_explicit_owner_approval(self):
        self.assertEqual(display_class_term('Alkaloids', {}),'Alkaloids')
        self.assertEqual(display_class_term(' ALKALOIDS '),'Alkaloid')
        approved={'Alkaloids':'Alkaloid'}  # explicit synthetic owner-reviewed configuration
        self.assertEqual(display_class_term('Alkaloids',approved),'Alkaloid')
        self.assertEqual(display_class_term('Alkaloids',{'Alkaloids':'Alkaloid','alkaloids':'Other'}),'Alkaloids')

    def test_recovery_route_requires_explicit_safe_configuration(self):
        for value in ('',None,'javascript:alert(1)','file:///private','https://user:pass@example.invalid','mailto:contact@example.invalid?body=secret','https://example.invalid/\nsecret'):
            self.assertEqual(approved_recovery_route(value),'')
        self.assertEqual(approved_recovery_route('https://example.invalid/recovery'),'https://example.invalid/recovery')
        self.assertEqual(approved_recovery_route('mailto:approved@example.invalid'),'mailto:approved@example.invalid')

    def test_open_labels_include_compound_and_unique_id(self):
        self.assertEqual(compound_open_label(1,'Synthetic'),'Open Synthetic (#1)')
        self.assertNotEqual(compound_open_label(1,'Synthetic'),compound_open_label(2,'Synthetic'))

    def test_approved_vocabularies_are_separate(self):
        self.assertEqual(display_source_term(' Marine   Alga '),'Marine alga')
        self.assertEqual(display_class_term('Marine Alga'),'Marine Alga')
        self.assertEqual(display_source_term('Alkaloids'),'Alkaloids')
        self.assertEqual(display_class_term('Unreviewed synonym'),'Unreviewed synonym')

    def test_actual_filter_options_counts_and_results_preserve_rows(self):
        import ast
        import pandas as pd
        app=Path(__file__).resolve().parents[1]/'scripts/app.py'
        ns=dict(display_class_term=display_class_term,display_source_term=display_source_term,
                category_counts=category_counts,get_secret_object=lambda *a:None,
                clean_text=lambda v:str(v or '').strip() or '-')
        tree=ast.parse(app.read_text())
        for name in ('presentation_taxonomy_label','normalize_filter_value','build_filter_options','apply_dataframe_filters'):
            node=[n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name==name][-1]
            exec(compile(ast.Module(body=[node],type_ignores=[]),str(app),'exec'),ns)
        frame=pd.DataFrame([dict(id=1,compound_class='Alkaloid',source_category='Marine Alga'),
                            dict(id=2,compound_class=' ALKALOIDS ',source_category=' marine alga '),
                            dict(id=3,compound_class='Other',source_category='Other')])
        original=frame.copy(deep=True)
        self.assertEqual(ns['build_filter_options'](frame,'compound_class'),['All','Alkaloid','Other'])
        self.assertEqual(ns['build_filter_options'](frame,'source_category'),['All','Marine alga','Other'])
        result=ns['apply_dataframe_filters'](frame,class_filter='alkaloids',source_filter='MARINE ALGA')
        self.assertEqual(result['id'].tolist(),[1,2])
        groups=category_counts(display_class_term(v) for v in frame['compound_class'])
        self.assertEqual(sum(g['Count'] for g in groups),len(frame))
        self.assertEqual([g['Count'] for g in groups if g['Category']=='Alkaloid'],[2])
        pd.testing.assert_frame_equal(frame,original)
