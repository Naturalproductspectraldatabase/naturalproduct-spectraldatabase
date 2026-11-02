"""Regression tests for order independence and optimal 1H/13C peak search."""
import ast
import itertools
import math
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0,str(ROOT))
from npdb_peak_matching import optimal_nmr_peak_matches

APP = ROOT / "app.py"

class PeakMatchingTests(unittest.TestCase):
    def test_query_and_database_permutations_give_identical_pairs(self):
        query = (1.0,1.06,1.5)
        reference = (0.96,1.03,1.52)
        expected = optimal_nmr_peak_matches(query,reference,0.05)
        self.assertEqual(len(expected),3)
        for qq in itertools.permutations(query):
            for rr in itertools.permutations(reference):
                actual = optimal_nmr_peak_matches(qq,rr,0.05)
                self.assertEqual(actual, expected)

    def test_greedy_nearest_neighbor_loses_cardinality(self):
        # 1.0's closest match is 1.03, which would block 1.06.
        # The optimal matching reserves 1.03 for 1.06.
        matches = optimal_nmr_peak_matches([1.0,1.06],[1.03,0.96],0.05)
        self.assertEqual(len(matches),2)
        self.assertEqual([p[:2] for p in matches],[(1.0,0.96),(1.06,1.03)])

    def test_zero_tolerance_exact_shifts_only(self):
        matches=optimal_nmr_peak_matches([3.3,5.0],[3.3,5.000001],0)
        self.assertEqual([(a,b) for a,b,_ in matches],[(3.3,3.3)])

    def test_repeated_peaks_are_one_to_one(self):
        x=optimal_nmr_peak_matches([1.,1.,1.],[1.,1.],0)
        self.assertEqual(len(x),2)

    def test_ignores_nan_infinity_and_non_numeric_records(self):
        x=optimal_nmr_peak_matches([1.,float("nan"),"oops",float("inf")],[1.,float("-inf")],0)
        self.assertEqual(len(x),1)
        self.assertEqual(x[0],(1.,1.,0.))

    def test_rejects_invalid_tolerance(self):
        for tol in (-0.01,float("nan"),float("inf")):
            with self.subTest(tolerance=tol),self.assertRaises(ValueError):
                optimal_nmr_peak_matches([1.],[1.],tol)

    def test_count_and_distance_optimality_checked_by_brute_force(self):
        query=[1.00,1.04,1.08]
        ref=[0.98,1.03,1.06,1.11]
        tol=0.045
        actual=optimal_nmr_peak_matches(query,ref,tol)
        possibilities=[]
        for count in range(min(len(query),len(ref))+1):
            for idx_q in itertools.combinations(range(len(query)),count):
                for idx_d in itertools.permutations(range(len(ref)),count):
                    diffs=[abs(query[i]-ref[j]) for i,j in zip(idx_q,idx_d)]
                    if all(x<=tol for x in diffs):
                        possibilities.append((count,sum(diffs)))
        optimum=sorted(possibilities,key=lambda x:(-x[0],x[1]))[0]
        self.assertEqual(len(actual),optimum[0])
        self.assertAlmostEqual(sum(x[2] for x in actual),optimum[1],places=8)

    def test_live_app_uses_new_matcher_without_duplicated_greedy_loop(self):
        src=APP.read_text(encoding="utf-8")
        tree=ast.parse(src)
        funcs=[node for node in tree.body if isinstance(node,ast.FunctionDef) and node.name=="find_best_matches"]
        self.assertEqual(len(funcs),1)
        fn=ast.get_source_segment(src,funcs[0])
        self.assertIn("optimal_nmr_peak_matches",fn)
        self.assertNotIn("matched_db_indexes",fn)

if __name__=="__main__":
    unittest.main()
