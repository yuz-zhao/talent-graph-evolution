from __future__ import annotations

import unittest

from scripts.detect_job_skill_evolution import beta_stats, classify_events, ewma_cusum, mann_kendall


def skill(name, support, total=20, relation="required", sources=3):
    mean, variance = beta_stats(support, total)
    return {
        "skill": name,
        "posterior_share": mean,
        "posterior_variance": variance,
        "weighted_support": support,
        "support_count": support,
        "source_count": sources if support else 0,
        "dominant_relation": relation if support else "absent",
        "evidence": [{"source_url": "https://example.org/job"}] if support else [],
    }


def window(month, skills, jd_count=20, source_count=3):
    return {
        "job_name": "测试岗位",
        "month": month,
        "jd_count": jd_count,
        "effective_jd_weight": jd_count,
        "source_count": source_count,
        "source_weight_distribution": {
            f"source-{index}": 1 / source_count for index in range(source_count)
        },
        "skills": skills,
    }


class JobSkillEvolutionTests(unittest.TestCase):
    def status(self, snapshots, skill_name="Python"):
        events, _ = classify_events(snapshots)
        return [event for event in events if event["skill"] == skill_name][-1]

    def test_added_requires_significant_multi_source_support(self):
        event = self.status([window("2026-01", []), window("2026-02", [skill("Python", 10)])])
        self.assertEqual(event["status"], "added")
        self.assertGreaterEqual(event["probability_up"], 0.95)

    def test_relation_change_is_modified(self):
        event = self.status([
            window("2026-01", [skill("Python", 10, relation="preferred")]),
            window("2026-02", [skill("Python", 10, relation="required")]),
        ])
        self.assertEqual(event["status"], "modified")

    def test_unchanged_skill_is_sustained(self):
        event = self.status([window("2026-01", [skill("Python", 10)]), window("2026-02", [skill("Python", 10)])])
        self.assertEqual(event["status"], "sustained")

    def test_low_window_support_is_insufficient(self):
        event = self.status([
            window("2026-01", [skill("Python", 1, total=2, sources=1)], jd_count=2, source_count=1),
            window("2026-02", [skill("Python", 2, total=2, sources=1)], jd_count=2, source_count=1),
        ])
        self.assertEqual(event["status"], "insufficient_evidence")
        self.assertTrue(event["fallback_reason"])

    def test_deletion_requires_two_declining_windows(self):
        event = self.status([
            window("2026-01", [skill("Python", 18)]),
            window("2026-02", [skill("Python", 8)]),
            window("2026-03", []),
        ])
        self.assertEqual(event["status"], "deleted")
        self.assertGreaterEqual(event["probability_down"], 0.95)

    def test_mann_kendall_detects_monotonic_growth(self):
        result = mann_kendall([0.05, 0.08, 0.12, 0.18, 0.25, 0.33])
        self.assertEqual(result["direction"], "increasing")
        self.assertLessEqual(result["p_value"], 0.10)

    def test_ewma_cusum_detects_upward_change(self):
        result = ewma_cusum([0.05, 0.05, 0.05, 0.30, 0.35, 0.40])
        self.assertTrue(result["detected"])
        self.assertEqual(result["direction"], "up")


if __name__ == "__main__":
    unittest.main()
