"""Scientific 1D NMR peak matching.

Find a one-to-one, order-independent pairing with the maximum number of peaks
within tolerance and then minimum total absolute ppm difference.

Sorted one-dimensional matching admits an optimal non-crossing assignment:
dynamic programming uses O(len(query)*len(reference)) time and memory.
This is a numeric matching primitive, not chemical structure verification.
"""
from math import isfinite


def optimal_nmr_peak_matches(query_peaks, reference_peaks, tolerance):
    """Return [(query_shift, reference_shift, abs_delta), ...], sorted by query.

    Invalid/non-finite peak values are ignored, unlike missing reference
    metadata; negative or non-finite tolerances are invalid.
    """
    limit = float(tolerance)
    if not isfinite(limit) or limit < 0:
        raise ValueError("NMR peak-match tolerance must be a finite nonnegative number.")

    def valid_peaks(values):
        cleaned = []
        for raw in values:
            try:
                shift = float(raw)
            except (TypeError, ValueError, OverflowError):
                continue
            if isfinite(shift):
                cleaned.append(shift)
        return sorted(cleaned)

    query = valid_peaks(query_peaks)
    reference = valid_peaks(reference_peaks)
    n, m = len(query), len(reference)
    if not n or not m:
        return []

    counts = [[0] * (m + 1) for _ in range(n + 1)]
    costs = [[0.0] * (m + 1) for _ in range(n + 1)]
    choices = [[0] * (m + 1) for _ in range(n + 1)]
    # choice: 0 = skip query, 1 = skip reference, 2 = match

    for i in range(1, n + 1):
        for j in range(1, m + 1):
            best_count = counts[i - 1][j]
            best_cost = costs[i - 1][j]
            choice = 0

            c = counts[i][j - 1]
            cost = costs[i][j - 1]
            if c > best_count or (c == best_count and cost < best_cost):
                best_count, best_cost, choice = c, cost, 1

            difference = abs(query[i - 1] - reference[j - 1])
            if difference <= limit:
                c = counts[i - 1][j - 1] + 1
                cost = costs[i - 1][j - 1] + difference
                if c > best_count or (c == best_count and cost <= best_cost):
                    best_count, best_cost, choice = c, cost, 2

            counts[i][j] = best_count
            costs[i][j] = best_cost
            choices[i][j] = choice

    results = []
    i, j = n, m
    while i and j:
        choice = choices[i][j]
        if choice == 2:
            q, d = query[i - 1], reference[j - 1]
            results.append((q, d, abs(q - d)))
            i -= 1
            j -= 1
        elif choice == 1:
            j -= 1
        else:
            i -= 1
    results.reverse()
    return results
