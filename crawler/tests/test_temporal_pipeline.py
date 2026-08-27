import unittest
from crawler.utils.time_utils import normalize_source_time


class TemporalPipelineTest(unittest.TestCase):
    def test_iso_source_time(self):
        value = normalize_source_time("2026-07-31", "2026-08-02T00:00:00+00:00")
        self.assertTrue(value["source_published_at"].startswith("2026-07-31"))
        self.assertEqual(value["time_source"], "source_field")

    def test_missing_time_is_not_imputed(self):
        value = normalize_source_time("", "2026-08-02T00:00:00+00:00")
        self.assertEqual(value["source_published_at"], "")
        self.assertEqual(value["time_source"], "unknown")

    def test_relative_time_uses_observation_anchor(self):
        value = normalize_source_time("3天前", "2026-08-02T00:00:00+00:00")
        self.assertTrue(value["source_published_at"].startswith("2026-07-30"))
        self.assertEqual(value["time_source"], "relative_text")

    def test_future_time_is_rejected(self):
        value = normalize_source_time("2030-01-01", "2026-08-02T00:00:00+00:00")
        self.assertEqual(value["source_published_at"], "")
        self.assertEqual(value["time_source"], "invalid")


if __name__ == "__main__": unittest.main()
