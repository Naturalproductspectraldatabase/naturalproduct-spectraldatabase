"""Deterministic property/optimality tests for NPDB NMR peak matching.

Independent brute-force exhaustive assignment oracle on small synthetic spectra,
plus permutation, translation, zero-tolerance and repeated-peak invariance.
This tests a numeric matcher, NOT scientific compound identification.
Uses only Python stdlib. Never accesses NPDB production or third-party data.
"""
from itertools import combinations, permutations
from pathlib import Path
from random import Random
import math
import sys
import unittest

MODULES = Path(__file__).resolve().parents[1] / "scripts"
sys.path.insert(0, str(MODULES))
from npdb_peak_matching import optimal_nmr_peak_matches

def exhaustive_assignment(query, reference, tolerance):
    """Return max cardinality, minimum sum abs delta by all legal injections."""
    n, m = len(query), len(reference)
    best_count, best_cost = 0, 0.0
    for k in range(1, min(n, m) + 1):
        for selected_query in combinations(range(n), k):
            for selected_ref in permutations(range(m), k):
                diffs = [abs(query[a] - reference[b])
                         for a, b in zip(selected_query, selected_ref)]
                if all(d <= tolerance + 1e-14 for d in diffs):
                    cost = sum(diffs)
                    if k > best_count or (k == best_count and cost < best_cost):
                        best_count, best_cost = k, cost
    return best_count, best_cost


class DeterministicNMRProperties(unittest.TestCase):
    def test_seeded_exhaustive_comparison_on_300_synthetic_cases(self):
        rng = Random(20261103)
        for case in range(300):
            nq, nd = rng.randint(0, 4), rng.randint(0, 4)
            # Mix exact ties, close multiplets and distant shifts.
            query = [rng.choice(range(-50, 81)) / 100 for _ in range(nq)]
            reference = [rng.choice(range(-50, 81)) / 100 for _ in range(nd)]
            tolerance = rng.choice([0.00, 0.01, 0.02, 0.03, 0.05, 0.2])
            oracle_count, oracle_cost = exhaustive_assignment(query, reference, tolerance)
            actual = optimal_nmr_peak_matches(query, reference, tolerance)
            with self.subTest(case=case, q=query, ref=reference, tolerance=tolerance):
                self.assertEqual(len(actual), oracle_count)
                self.assertAlmostEqual(sum(x[2] for x in actual), oracle_cost, places=10)
                self.assertTrue(all(d <= tolerance + 1e-12 for _, _, d in actual))
                self.assertEqual([x[0] for x in actual],
                                 sorted(x[0] for x in actual))

    def test_permutation_invariance_on_tied_and_nearly_identical_peaks(self):
        q = [1.00, 1.00, 1.025, 3.0]
        ref = [0.98, 1.00, 1.025, 3.025]
        expected = optimal_nmr_peak_matches(q, ref, 0.03)
        for qperm in permutations(q):
            for rperm in permutations(ref):
                with self.subTest(q=qperm, ref=rperm):
                    self.assertEqual(optimal_nmr_peak_matches(qperm, rperm, 0.03),
                                     expected)

    def test_simultaneous_translation_preserves_matches_and_cost(self):
        q = [-0.15, 1.1, 3.2, 6.8]
        ref = [-0.16, 1.05, 3.25, 7.0]
        baseline = optimal_nmr_peak_matches(q, ref, 0.06)
        for offset in [-8.0, 2.0, 10.0]:
            moved = optimal_nmr_peak_matches([x + offset for x in q],
                                             [y + offset for y in ref], 0.06)
            self.assertEqual(len(moved), len(baseline))
            for (x, y, distance), (u, v, prior_distance) in zip(moved, baseline):
                self.assertAlmostEqual(x, u + offset, places=10)
                self.assertAlmostEqual(y, v + offset, places=10)
                self.assertAlmostEqual(distance, prior_distance, places=10)

    def test_exact_boundary_survives_binary_roundoff(self):
        self.assertEqual(
            len(optimal_nmr_peak_matches([-0.3], [-0.32], 0.02)),
            1,
            "Inclusive tolerance must include exactly 0.02 ppm difference",
        )

    def test_materially_outside_boundary_remains_unmatched(self):
        self.assertEqual(
            optimal_nmr_peak_matches([-0.3], [-0.320001], 0.02),
            [],
            "Roundoff protection must not create a meaningful false match",
        )

    def test_negative_delta_and_zero_tolerance(self):
        matched = optimal_nmr_peak_matches([-1.1, 0.0, 3.5],
                                           [-1.1, -1.1, 3.5], 0.0)
        self.assertEqual(len(matched), 2)
        self.assertEqual(sum(v[2] for v in matched), 0)

    def test_nonfinite_and_nonnumeric_peak_values_are_filtered(self):
        data = [2.0, "2.00", float("nan"), float("inf"), None, "garbage"]
        hits = optimal_nmr_peak_matches(data, [2.0, math.nan, "x"], 0)
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0], (2., 2., 0.))

    def test_malformed_tolerance_is_not_silently_accepted(self):
        for invalid in ["bad", -0.001, math.nan, math.inf, -math.inf]:
            with self.subTest(invalid=invalid):
                with self.assertRaises((TypeError, ValueError)):
                    optimal_nmr_peak_matches([1], [1], invalid)


if __name__ == "__main__":
    unittest.main()
