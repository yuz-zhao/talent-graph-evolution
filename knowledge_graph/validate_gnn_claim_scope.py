"""Fail closed when the unsupervised GNN is presented as a supervised matcher."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GATE = ROOT / "knowledge_graph" / "gnn_dataset" / "training_gate.json"
TRAINING = ROOT / "knowledge_graph" / "gnn_models" / "hetero_graphsage_training_report.json"
ONLINE = ROOT / "knowledge_graph" / "gnn_models" / "online_embeddings.json"
SERVER = ROOT / "server" / "index.js"
OUTPUT = ROOT / "crawler" / "data" / "reports" / "gnn_claim_scope_acceptance.json"


def main() -> None:
    gate = json.loads(GATE.read_text(encoding="utf-8"))
    training = json.loads(TRAINING.read_text(encoding="utf-8"))
    online = json.loads(ONLINE.read_text(encoding="utf-8"))
    server = SERVER.read_text(encoding="utf-8")
    fusion_block = re.search(r"const normalized = normalizedWeightedScore\(\{(.+?)\}\s*,\s*(.+?)\)", server, re.S)
    fusion_text = fusion_block.group(0) if fusion_block else ""
    explicit_zero_weight = bool(re.search(r"gnn\s*:\s*\.0+", server))
    policy = gate.get("serving_policy", {})
    checks = {
        "objective_is_unsupervised_edge_reconstruction": training.get("training_objective") == "unsupervised typed-edge reconstruction",
        "supervised_ranker_is_not_claimed": training.get("supervised_talent_job_ranker_trained") is False,
        "formal_matching_accuracy_is_blocked": training.get("formal_matching_accuracy_eligible") is False,
        "online_artifact_scope_is_representation_only": online.get("claim_scope") == "graph representation pretraining only",
        "serving_mode_is_shadow_only": policy.get("mode") == "shadow_only",
        "production_weight_is_zero": policy.get("production_weight") == 0,
        "gnn_does_not_affect_ranking": policy.get("affects_ranking") is False and ("gnn:" not in fusion_text or explicit_zero_weight),
        "api_exposes_claim_boundary": all(token in server for token in ["evaluationMode:'shadow_only'", "affectsRanking:false", "formalMatchingAccuracyEligible:false"]),
    }
    result = {
        "schema_version": "1.0.0",
        "passed": all(checks.values()),
        "model_positioning": "unsupervised heterogeneous GraphSAGE auxiliary representation in shadow evaluation",
        "checks": checks,
        "observed_behavior_readiness": gate.get("observed", {}),
        "activation_gate": gate.get("required_thresholds", {}),
        "allowed_claim": gate.get("allowed_claim"),
        "prohibited_claims": [
            "GNN is the trained core talent-job matching model",
            "edge-reconstruction loss proves matching accuracy",
            "GNN improves ranking before an independent downstream evaluation",
        ],
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if not result["passed"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
