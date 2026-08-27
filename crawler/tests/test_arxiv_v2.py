import importlib.util
import sys
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "spiders/tech/arxiv_spider.py"
SPEC = importlib.util.spec_from_file_location("arxiv_v2", PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class ArxivV2Test(unittest.TestCase):
    def test_skill_evidence_uses_sentence(self):
        skills, evidence = MODULE.skill_evidence("RAG with Python", "We use Docker for deployment.")
        self.assertTrue(skills)
        self.assertTrue(all(item["evidence_sentence"] for item in evidence))
        self.assertEqual(len(skills), len({skill.casefold() for skill in skills}))

    def test_parse_metadata_lists(self):
        xml = f'''<entry xmlns="{MODULE.ATOM}" xmlns:arxiv="{MODULE.ARXIV}">
        <id>https://arxiv.org/abs/2601.12345v2</id><title>Machine Learning for Networks</title>
        <summary>A machine learning approach for wireless network protocols.</summary>
        <author><name>Alice</name></author><author><name>Bob</name></author>
        <published>2026-01-01T00:00:00Z</published><updated>2026-01-02T00:00:00Z</updated>
        <arxiv:primary_category term="cs.NI"/><category term="cs.NI"/><category term="cs.LG"/>
        </entry>'''
        row = MODULE.parse_entry(ET.fromstring(xml), "test", "2026-08-02T00:00:00Z")
        self.assertEqual(row["arxiv_id"], "2601.12345")
        self.assertEqual(row["version"], 2)
        self.assertEqual(row["authors"], ["Alice", "Bob"])
        self.assertEqual(row["categories"], ["cs.NI", "cs.LG"])


if __name__ == "__main__": unittest.main()
