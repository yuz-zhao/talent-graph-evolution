"""验证岗位主 CSV 与岗位图谱导出的一致性和关键质量约束。"""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CSV_PATH = ROOT / "crawler/data/silver/jobs/jd_clean.csv"
GRAPH = ROOT / "knowledge_graph/import"


def load(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    rows = load(CSV_PATH)
    china = [row for row in rows if row.get("statistics_scope") == "china_main"]
    source_ids = [row.get("source_job_id") for row in rows]
    version_ids = [row.get("version_id") for row in rows]
    evidence_ok = True
    for row in rows:
        skills = {item for item in row.get("skill_standard", "").split(";") if item}
        try:
            evidence = json.loads(row.get("skill_evidence") or "[]")
        except json.JSONDecodeError:
            evidence_ok = False
            break
        proven = {item.get("skill") for item in evidence if item.get("snippet") and item.get("field") and item.get("method")}
        if not skills.issubset(proven):
            evidence_ok = False
            break

    job_nodes = load(GRAPH / "nodes_job.csv")
    skill_nodes = load(GRAPH / "nodes_skill.csv")
    skill_relations = load(GRAPH / "rel_job_requires_skill.csv")
    job_ids = {row.get("job_id:ID") for row in job_nodes}
    skill_ids = {row.get("skill_id:ID") for row in skill_nodes}
    relation_ok = all(
        row.get(":START_ID") in job_ids
        and row.get(":END_ID") in skill_ids
        and row.get("evidence")
        and row.get("evidence_field")
        and row.get("extraction_method")
        for row in skill_relations
    )
    checks = {
        "rows_2784": len(rows) == 2784,
        "source_job_id_unique": len(source_ids) == len(set(source_ids)) and all(source_ids),
        "version_id_unique": len(version_ids) == len(set(version_ids)) and all(version_ids),
        "canonical_job_id_nonempty": all(row.get("canonical_job_id") for row in rows),
        "english_is_reference": all(row.get("statistics_scope") == "overseas_reference" for row in rows if row.get("source_language") == "en"),
        "no_synthetic": all(row.get("is_synthetic") == "false" for row in rows),
        "skill_evidence_complete": evidence_ok,
        "job_graph_count_matches": len(job_nodes) == len(rows),
        "graph_skill_relations_valid": relation_ok,
        "china_source_url_effective_95": sum(row.get("source_url_status") in {"verified_live", "reachable_blocked"} for row in china) / max(len(china), 1) >= 0.95,
        "china_requirements_90": sum(bool(row.get("requirements")) for row in china) / max(len(china), 1) > 0.90,
        "china_standard_skill_95": sum(bool(row.get("skill_standard")) for row in china) / max(len(china), 1) >= 0.95,
    }
    result = {
        "rows": len(rows), "china_main": len(china),
        "job_nodes": len(job_nodes), "skill_relations": len(skill_relations),
        "checks": checks,
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
