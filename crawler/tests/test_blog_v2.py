import importlib.util
import sys
import unittest
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "spiders/tech/blog_spider.py"
SPEC = importlib.util.spec_from_file_location("blog_v2", PATH)
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)


class BlogV2Test(unittest.TestCase):
    def test_rfc2822_and_iso_dates(self):
        self.assertEqual(M.parse_date("Wed, 08 Jul 2026 10:00:00 GMT"), "2026-07-08T10:00:00Z")
        self.assertEqual(M.parse_date("2026-07-08T10:00:00+08:00"), "2026-07-08T02:00:00Z")

    def test_hotness_is_source_internal_and_bounded(self):
        rows = [
            {"source_name": "A", "published_at": "2026-01-01T00:00:00Z"},
            {"source_name": "A", "published_at": "2026-02-01T00:00:00Z"},
            {"source_name": "B", "published_at": "2020-01-01T00:00:00Z"},
        ]
        M.normalize_hotness(rows)
        self.assertEqual([row["hot_score"] for row in rows], [0.0, 1.0, 0.0])

    def test_skill_relation_has_real_evidence(self):
        row = {"title": "Deployment", "body_text": "We deploy Python services with Docker.", "rss_summary": ""}
        M.enrich_skills(row)
        self.assertTrue(row["relationship_skills"])
        self.assertTrue(all(item["evidence_text"] for item in row["skill_evidence"]))


if __name__ == "__main__": unittest.main()
