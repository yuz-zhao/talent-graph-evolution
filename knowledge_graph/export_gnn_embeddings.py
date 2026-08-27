"""Export only online-serving GraphSAGE embeddings to a compact JSON artifact."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import torch

BASE = Path(__file__).resolve().parent
MODEL = BASE / "gnn_models" / "hetero_graphsage_embeddings.pt"
REPORT = BASE / "gnn_models" / "hetero_graphsage_training_report.json"
OUTPUT = BASE / "gnn_models" / "online_embeddings.json"


def main():
    payload = torch.load(MODEL, weights_only=False)
    report = json.loads(REPORT.read_text(encoding="utf-8"))
    names = {}
    with (BASE / "gnn_dataset" / "nodes.jsonl").open(encoding="utf-8") as handle:
        for line in handle:
            row = json.loads(line)
            if row["node_type"] in {"skill", "job_cluster"}:
                names[(row["node_type"], row["source_id"])] = row["features"].get("name")
    exported = {}
    for node_type in ("skill", "job_cluster"):
        node_payload = payload[node_type]
        exported[node_type] = {}
        for source_id, vector in zip(node_payload["source_ids"], node_payload["embeddings"].tolist()):
            name = names.get((node_type, source_id))
            if name:
                exported[node_type][name] = [round(value, 7) for value in vector]
    source_hash = hashlib.sha256(MODEL.read_bytes()).hexdigest()
    result = {
        "version":"hetero_graphsage_unsupervised_v1", "source_model_sha256":source_hash,
        "training_objective":report["training_objective"], "claim_scope":report["claim_scope"],
        "supervised_talent_job_ranker_trained":False, "dimension":report["hidden_dimension"],
        "embeddings":exported,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(json.dumps({"output":str(OUTPUT),"dimension":result["dimension"],"counts":{key:len(value) for key,value in exported.items()},"source_model_sha256":source_hash}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
