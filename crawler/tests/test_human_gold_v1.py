import json
import unittest
from collections import Counter
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
GOLD = BASE / "data" / "gold" / "human" / "v1.1"


def load_jsonl(name):
    return [json.loads(line) for line in (GOLD / name).read_text(encoding="utf-8").splitlines() if line.strip()]


class HumanGoldV1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.jd = load_jsonl("gold_jd_v1.1.jsonl")
        cls.resumes = load_jsonl("gold_resume_v1.1.jsonl")
        cls.matches = load_jsonl("gold_match_v1.1.jsonl")
        cls.inputs = load_jsonl("match_inputs_v1.1.jsonl")

    def test_counts_and_unique_ids(self):
        self.assertEqual((len(self.jd), len(self.resumes), len(self.matches), len(self.inputs)), (100, 30, 400, 400))
        self.assertEqual(len({x["sample_id"] for x in self.jd}), 100)
        self.assertEqual(len({x["resume_id"] for x in self.resumes}), 30)
        self.assertEqual(len({x["pair_id"] for x in self.matches}), 400)

    def test_splits(self):
        self.assertEqual(Counter(x["split"] for x in self.jd), Counter({"development":20,"validation":20,"test":60}))
        self.assertEqual(Counter(x["split"] for x in self.resumes), Counter({"development":5,"validation":5,"test":20}))

    def test_match_references_and_distribution(self):
        jd_ids = {x["sample_id"] for x in self.jd}
        test_resume_ids = {x["resume_id"] for x in self.resumes if x["split"] == "test"}
        self.assertTrue(all(x["jd_sample_id"] in jd_ids and x["resume_id"] in test_resume_ids for x in self.matches))
        self.assertEqual(Counter(x["relevance"] for x in self.matches), Counter({0:110,1:128,2:89,3:73}))
        self.assertEqual(set(Counter(x["resume_id"] for x in self.matches).values()), {20})

    def test_no_match_input_label_leakage(self):
        forbidden = {"relevance","level","matched_skills","missing_skills","reason","candidate_design_stratum"}
        self.assertFalse({key for row in self.inputs for key in row} & forbidden)


if __name__ == "__main__":
    unittest.main()
