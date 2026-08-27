from __future__ import annotations

import unittest

from scripts.analyze_cross_source_lag import fisher_interval, lag_candidates, pearson


class CrossSourceLagTests(unittest.TestCase):
    def test_pearson_detects_same_shape(self):
        self.assertAlmostEqual(pearson([1, 2, 3, 4], [2, 4, 6, 8]), 1.0)

    def test_positive_lead_is_external_before_jd(self):
        external = {f"2026-{month:02d}": float(month) for month in range(1, 9)}
        jd = {f"2026-{month + 2:02d}": float(month) for month in range(1, 9)}
        lead_two = next(item for item in lag_candidates(external, jd, max_lead=3) if item["lead_months"] == 2)
        self.assertAlmostEqual(lead_two["correlation"], 1.0)

    def test_fisher_interval_requires_four_samples(self):
        self.assertIsNone(fisher_interval(0.5, 3))
        self.assertEqual(len(fisher_interval(0.5, 8)), 2)


if __name__ == "__main__":
    unittest.main()
