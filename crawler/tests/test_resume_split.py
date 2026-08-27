import csv, json, re, unittest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1] / "data/clean"

class ResumeSplitTest(unittest.TestCase):
    def test_public_profile_skills_have_repo_evidence(self):
        with (BASE / "profiles_github_public.csv").open("r", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 120)
        self.assertTrue(all(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", row["display_name"]) for row in rows))
        for row in rows:
            skills, evidence = json.loads(row["skills"]), json.loads(row["skill_evidence"])
            supported = {item["skill"] for item in evidence if item.get("repository_url") and item.get("repo_id")}
            self.assertTrue(set(skills).issubset(supported))
            self.assertEqual(row["random_supplemented_fields"], "0")

    def test_synthetic_names_and_exclusions(self):
        with (BASE / "resumes_synthetic_demo.csv").open("r", encoding="utf-8-sig") as handle:
            rows = list(csv.DictReader(handle))
        self.assertEqual(len(rows), 380)
        self.assertEqual(len({row["display_name"] for row in rows}), 380)
        self.assertTrue(all(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", row["display_name"]) for row in rows))
        self.assertTrue(all(row["statistics_scope"] == row["accuracy_evaluation_scope"] == "excluded" for row in rows))

    def test_evaluation_file_contains_no_unapproved_records(self):
        path = BASE / "resumes_anonymized_evaluation.jsonl"
        rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        self.assertTrue(all(row["authorization_status"] == "granted" and not row["is_synthetic"] for row in rows))

if __name__ == "__main__": unittest.main()
