import importlib.util
import sys
import unittest
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "spiders/tech/github_detail_spider.py"
SPEC = importlib.util.spec_from_file_location("github_detail_v2", MODULE_PATH)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


class GitHubDetailV2Test(unittest.TestCase):
    def test_case_insensitive_dedupe(self):
        self.assertEqual(MODULE.unique_casefold(["Docker", "docker", "Python"]), ["Docker", "Python"])

    def test_relationship_requires_readme_or_dependency_evidence(self):
        readme = "Built with Python and Docker."
        topics = ["python", "Kubernetes", "kubernetes"]
        languages = {"Python": 1000, "JavaScript": 20}
        dependencies = [{"path": "requirements.txt", "content": "fastapi==1.0\nredis==5.0"}]
        inferred, relationship, evidence = MODULE.build_skill_evidence(readme, topics, languages, dependencies)
        self.assertIn("Python", inferred)
        self.assertEqual(len(inferred), len({item.casefold() for item in inferred}))
        self.assertTrue(set(relationship).issubset({
            item["skill"] for item in evidence if item["channel"] in {"readme", "dependency"}
        }))
        self.assertTrue(all(item["snippet"] for item in evidence))

    def test_dependency_selection_prefers_root(self):
        tree = {"tree": [
            {"path": "service/package.json", "type": "blob"},
            {"path": "requirements.txt", "type": "blob"},
            {"path": "README.md", "type": "blob"},
        ]}
        self.assertEqual(MODULE.dependency_paths(tree, 2), ["requirements.txt", "service/package.json"])


if __name__ == "__main__":
    unittest.main()
