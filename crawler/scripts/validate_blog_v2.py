"""官方技术博客 v2 验收。"""
import json
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PATH = BASE / "data/bronze/blogs_trend.jsonl"
REPORT = BASE / "data/reports/blog_v2_quality_report.json"
rows = [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()] if PATH.exists() else []

def valid_date(value):
    try: datetime.fromisoformat(str(value).replace("Z", "+00:00")); return True
    except (ValueError, TypeError): return False

date_rate = sum(valid_date(row.get("published_at")) for row in rows) / len(rows) if rows else 0
domestic = {row["source_name"] for row in rows if row.get("source_region") == "domestic"}
international = {row["source_name"] for row in rows if row.get("source_region") == "international"}
relation_count = sum(len(row.get("relationship_skills") or []) for row in rows)
evidence_valid = True
for row in rows:
    supported = {item.get("skill") for item in row.get("skill_evidence") or [] if item.get("evidence_text")}
    if not set(row.get("relationship_skills") or []).issubset(supported): evidence_valid = False
checks = {
    "date_validity_at_least_98_percent": date_rate >= .98,
    "hot_score_between_zero_and_one": all(0 <= float(row.get("hot_score")) <= 1 for row in rows),
    "generated_template_summary_count_is_zero": all(row.get("summary_origin") != "inferred" for row in rows),
    "every_article_has_real_summary_or_body_evidence": all(row.get("rss_summary") or row.get("body_text") for row in rows),
    "at_least_three_domestic_official_sources": len(domestic) >= 3,
    "at_least_three_international_official_sources": len(international) >= 3,
    "blog_skill_relations_nonzero": relation_count > 0,
    "every_blog_skill_relation_has_evidence": relation_count > 0 and evidence_valid,
}
report = {
    "schema_version": "blog_v2", "articles": len(rows), "date_validity": round(date_rate, 6),
    "domestic_sources": sorted(domestic), "international_sources": sorted(international),
    "body_snapshots": sum(row.get("body_status") == "fetched" for row in rows),
    "rss_or_publisher_summaries": sum(bool(row.get("rss_summary")) for row in rows),
    "blog_skill_relation_candidates": relation_count, "checks": checks, "passed": all(checks.values()),
}
REPORT.parent.mkdir(parents=True, exist_ok=True)
REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2))
raise SystemExit(0 if report["passed"] else 1)
