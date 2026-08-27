"""arXiv v2 数据质量验收。"""
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "data/bronze/papers_trend.jsonl"
QUARANTINE = BASE / "data/quarantine/arxiv_irrelevant.jsonl"
REPORT = BASE / "data/reports/arxiv_v2_quality_report.json"
ALLOWED = {"cs.AI", "cs.LG", "cs.CL", "cs.CV", "cs.IR", "cs.DB", "cs.NI", "cs.RO"}

def load(path):
    rows = []
    if path.exists():
        for line in path.read_text(encoding="utf-8-sig").splitlines():
            try: rows.append(json.loads(line))
            except json.JSONDecodeError: pass
    return rows

rows, isolated = load(SOURCE), load(QUARANTINE)
def valid_date(value):
    try: datetime.fromisoformat(str(value).replace("Z", "+00:00")); return True
    except (ValueError, TypeError): return False

category_complete = sum(bool(row.get("primary_category") and row.get("categories")) for row in rows) / len(rows) if rows else 0
date_valid = sum(valid_date(row.get("published_at")) for row in rows) / len(rows) if rows else 0
unrelated = sum(row.get("primary_category") not in ALLOWED for row in rows) / len(rows) if rows else 1
relation_count = sum(len(row.get("relationship_skills") or []) for row in rows)
evidence_valid = True
for row in rows:
    abstract_evidence = {
        item.get("skill") for item in (row.get("skill_evidence") or [])
        if item.get("source_field") == "abstract" and item.get("evidence_sentence")
    }
    if not set(row.get("relationship_skills") or []).issubset(abstract_evidence):
        evidence_valid = False
checks = {
    "unrelated_paper_ratio_below_5_percent": unrelated < .05,
    "category_completeness_at_least_98_percent": category_complete >= .98,
    "published_date_validity_at_least_98_percent": date_valid >= .98,
    "paper_skill_relations_nonzero": relation_count > 0,
    "every_relation_has_abstract_evidence": relation_count > 0 and evidence_valid,
}
report = {
    "schema_version": "arxiv_v2", "formal_papers": len(rows), "isolated_papers": len(isolated),
    "unrelated_ratio": round(unrelated, 6), "category_completeness": round(category_complete, 6),
    "published_date_validity": round(date_valid, 6), "paper_skill_relation_candidates": relation_count,
    "checks": checks, "passed": all(checks.values()),
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if report["passed"] else 1)
