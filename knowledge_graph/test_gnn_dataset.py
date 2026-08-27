import json
import subprocess
import sys
import unittest
from pathlib import Path

BASE = Path(__file__).resolve().parent


class GnnDatasetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        subprocess.run([sys.executable, str(BASE / "build_gnn_dataset.py")], check=True, capture_output=True, text=True)
        cls.manifest = json.loads((BASE / "gnn_dataset" / "manifest.json").read_text(encoding="utf-8"))
        cls.gate = json.loads((BASE / "gnn_dataset" / "training_gate.json").read_text(encoding="utf-8"))

    def test_graph_has_core_node_and_edge_types(self):
        self.assertGreater(self.manifest["node_counts"]["job"], 0)
        self.assertGreater(self.manifest["node_counts"]["skill"], 0)
        self.assertGreater(self.manifest["edge_counts"]["job_requires_skill"], 0)

    def test_edges_keep_audit_features(self):
        self.assertEqual(self.manifest["edge_features"], ["confidence","observed_at","source_url","evidence_text","requirement_type"])

    def test_training_is_blocked_without_outcome_edges(self):
        self.assertEqual(self.gate["status"], "unsupervised_gnn_trained_supervised_ranker_blocked")
        self.assertTrue(self.gate["gnn_representation_model_trained"])
        self.assertFalse(self.gate["supervised_talent_job_ranker_trained"])
        self.assertEqual(self.manifest["contains_interaction_labels"], False)
        self.assertEqual(self.gate["observed"]["postgres_non_demo_actions"], 3)
        self.assertEqual(self.gate["observed"]["strong_outcomes_in_dataset"], 0)


if __name__ == "__main__":
    unittest.main()
