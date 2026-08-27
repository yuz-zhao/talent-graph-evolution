"""Build an auditable heterogeneous graph dataset without claiming a trained GNN."""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
IMPORT = BASE / "import"
OUTPUT = BASE / "gnn_dataset"
csv.field_size_limit(16 * 1024 * 1024)

NODE_FILES = {
    "talent": ("nodes_talent.csv", "talent_id:ID"),
    "job": ("nodes_job.csv", "job_id:ID"),
    "skill": ("nodes_skill.csv", "skill_id:ID"),
    "job_cluster": ("nodes_job_cluster.csv", "cluster_id:ID"),
    "company": ("nodes_company.csv", "company_id:ID"),
    "certificate": ("nodes_certificate.csv", "certificate_id:ID"),
    "course": ("nodes_course.csv", "course_id:ID"),
    "project": ("nodes_tech_project.csv", "project_id:ID"),
}

EDGE_FILES = {
    "talent_has_skill": ("rel_talent_has_skill.csv", "talent", "skill"),
    "job_requires_skill": ("rel_job_requires_skill.csv", "job", "skill"),
    "job_belongs_cluster": ("rel_job_belongs_cluster.csv", "job", "job_cluster"),
    "company_posts_job": ("rel_company_posts_job.csv", "company", "job"),
    "certificate_certifies_skill": ("rel_certificate_certifies_skill.csv", "certificate", "skill"),
    "course_teaches_skill": ("rel_course_teaches_skill.csv", "course", "skill"),
    "project_uses_skill": ("rel_tech_project_uses_tech.csv", "project", "skill"),
    "skill_parent": ("rel_skill_parent.csv", "skill", "skill"),
}


def rows(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        yield from csv.DictReader(handle)


def parse_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        try:
            return datetime.strptime(str(value)[:10], "%Y-%m-%d")
        except ValueError:
            return None


def build():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    node_ids, node_counts = {}, {}
    nodes_tmp, edges_tmp = OUTPUT / "nodes.jsonl.tmp", OUTPUT / "edges.jsonl.tmp"
    with nodes_tmp.open("w", encoding="utf-8") as target:
        for node_type, (filename, id_column) in NODE_FILES.items():
            node_ids[node_type] = set()
            for index, row in enumerate(rows(IMPORT / filename)):
                source_id = row.get(id_column, "").strip()
                if not source_id:
                    continue
                node_ids[node_type].add(source_id)
                target.write(json.dumps({"node_type":node_type, "node_index":index, "source_id":source_id, "features":{key:value for key,value in row.items() if key != id_column}}, ensure_ascii=False) + "\n")
            node_counts[node_type] = len(node_ids[node_type])

    edge_counts, invalid_edges, edge_times = Counter(), Counter(), []
    with edges_tmp.open("w", encoding="utf-8") as target:
        for relation, (filename, source_type, target_type) in EDGE_FILES.items():
            for row in rows(IMPORT / filename):
                source, destination = row.get(":START_ID", "").strip(), row.get(":END_ID", "").strip()
                if source not in node_ids[source_type] or destination not in node_ids[target_type]:
                    invalid_edges[relation] += 1
                    continue
                observed = row.get("observed_at") or row.get("time_window")
                parsed = parse_time(observed)
                if parsed:
                    edge_times.append(parsed)
                payload = {
                    "source_type":source_type, "source_id":source, "relation":relation,
                    "target_type":target_type, "target_id":destination,
                    "confidence":float(row.get("confidence:float") or .5),
                    "observed_at":observed or None, "source_url":row.get("source_url") or None,
                    "evidence_text":row.get("evidence_text") or None,
                    "requirement_type":row.get("requirement_type") or None,
                }
                target.write(json.dumps(payload, ensure_ascii=False) + "\n")
                edge_counts[relation] += 1

    cutoff = sorted(edge_times)[max(0, int(len(edge_times) * .8) - 1)] if edge_times else None
    manifest = {
        "dataset_version":"heterogeneous_graph_v1", "task":"talent_job_link_prediction",
        "node_counts":node_counts, "edge_counts":dict(edge_counts), "invalid_edge_counts":dict(invalid_edges),
        "edge_features":["confidence","observed_at","source_url","evidence_text","requirement_type"],
        "split_policy":{"method":"edge_time_80_20", "cutoff":cutoff.isoformat() if cutoff else None, "time_coverage":round(len(edge_times)/max(1,sum(edge_counts.values())),4)},
        "label_source":"external_behavior_table_required", "contains_interaction_labels":False,
    }
    behavior_path = OUTPUT / "behavior_readiness_audit.json"
    behavior = json.loads(behavior_path.read_text(encoding="utf-8")) if behavior_path.exists() else {}
    gate = {
        "status":"unsupervised_gnn_trained_supervised_ranker_blocked", "gnn_representation_model_trained":True, "supervised_talent_job_ranker_trained":False,
        "current_production_method":"diversified_feedback_matching_v8_with_gnn_shadow_evaluation",
        "serving_policy":{"mode":"shadow_only","production_weight":0,"affects_ranking":False,"formal_matching_accuracy_eligible":False},
        "required_thresholds":{"non_synthetic_interactions":3000,"real_talent_profiles":300,"strong_outcomes":["applied","interviewed","hired"]},
        "observed":{"graph_talent_profiles":node_counts.get("talent",0),"interaction_labels_in_dataset":0,"postgres_total_actions":behavior.get("total_actions"),"postgres_demo_actions":behavior.get("demo_actions"),"postgres_non_demo_actions":behavior.get("non_demo_actions"),"strong_outcomes_in_dataset":behavior.get("non_demo_strong_outcomes",0)},
        "blocking_reasons":["heterogeneous graph has no talent-to-job outcome edges","independent strong interaction labels are below training threshold","current public talent profiles are not authorized resume outcomes"],
        "allowed_claim":"unsupervised heterogeneous GraphSAGE representation model trained; no supervised talent-job matching accuracy claim",
    }
    nodes_tmp.replace(OUTPUT / "nodes.jsonl")
    edges_tmp.replace(OUTPUT / "edges.jsonl")
    (OUTPUT / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUTPUT / "training_gate.json").write_text(json.dumps(gate, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"manifest":manifest,"training_gate":gate}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    build()
