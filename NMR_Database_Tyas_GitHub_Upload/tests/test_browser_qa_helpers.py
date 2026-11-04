"""Synthetic presentation tests; no approved taxonomy or contact is fabricated."""
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from npdb_browser_qa import category_counts,display_class_term,compound_open_label,approved_recovery_route

class BrowserQaHelpersTests(unittest.TestCase):
    def test_case_and_spacing_aggregation_preserves_original_inputs(self):
        values=['Marine alga','Marine Alga',' Marine  Alga ',None,'']
        original=list(values)
        result=category_counts(values)
        self.assertEqual(sum(row['Count'] for row in result),5)
        self.assertEqual(sorted(row['Count'] for row in result),[2,3])
        self.assertEqual(values,original)

    def test_class_plural_is_not_inferred_without_approved_mapping(self):
        self.assertEqual(display_class_term('Alkaloids'),'Alkaloids')
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
