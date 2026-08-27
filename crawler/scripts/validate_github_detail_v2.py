"""验证 GitHub detail v2 的真实性、原始响应追溯和技能证据。"""
from __future__ import annotations

import json
import hashlib
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
TREND = BASE / "data/bronze/github_trend.jsonl"
DETAIL = BASE / "data/bronze/github_detail.jsonl"
RAW = BASE / "data/bronze/github/detail_api"
REPORT = BASE / "data/reports/github_detail_v2_quality_report.json"


def load(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def digest(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def main() -> int:
    trend, details = load(TREND), load(DETAIL)
    eligible = {str(row.get("repo_id")) for row in trend if row.get("repo_id")}
    repo_raw = {}
    readme_raw = {}
    for path in RAW.glob("*/*/repo.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            repo_raw[str(payload.get("id"))] = digest(payload)
        except (json.JSONDecodeError, OSError):
            pass
    for path in RAW.glob("*/*/readme.json"):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if payload.get("sha"):
                readme_raw[str(payload["sha"])] = digest(payload)
        except (json.JSONDecodeError, OSError):
            pass

    ids = [str(row.get("repo_id") or "") for row in details]
    fetched = [row for row in details if row.get("readme_status") == "fetched"]
    metric_trace = bool(details) and all(
        str(row.get("repo_id")) in repo_raw and row.get("stars") != "" and row.get("forks") != ""
        and row.get("repo_raw_hash") == repo_raw.get(str(row.get("repo_id"))) for row in details
    )
    readme_trace = bool(fetched) and all(
        row.get("readme_content") and row.get("readme_sha") in readme_raw
        and row.get("readme_raw_hash") == readme_raw.get(row.get("readme_sha"))
        and row.get("readme_branch") and row.get("readme_fetched_at") for row in fetched
    )
    relation_trace = True
    for row in details:
        evidence = row.get("skill_evidence") or []
        supported = {
            item.get("skill") for item in evidence
            if item.get("channel") in {"readme", "dependency"} and item.get("snippet") and item.get("source_path")
        }
        if not set(row.get("relationship_skills") or []).issubset(supported):
            relation_trace = False
    no_case_duplicates = all(
        len(items) == len({str(value).casefold() for value in items})
        for row in details for items in [row.get("observed_topics") or [], row.get("inferred_skills") or []]
    )
    coverage = len(fetched) / len(eligible) if eligible else 0
    detail_authenticity = len(fetched) / len(details) if details else 0
    checks = {
        "unique_repo_id": len(ids) == len(set(ids)) and "" not in ids,
        "all_repositories_in_trend_master": set(ids).issubset(eligible),
        "readme_authenticity_coverage_at_least_90_percent": coverage >= 0.90,
        "generated_readme_count_is_zero": sum(bool(row.get("readme_generated")) for row in details) == 0,
        "readme_api_raw_trace_complete": readme_trace,
        "stars_and_forks_api_raw_trace_complete": metric_trace,
        "project_skill_relations_have_text_or_dependency_evidence": relation_trace,
        "case_insensitive_skill_and_topic_deduplication": no_case_duplicates,
    }
    report = {
        "schema_version": "github_detail_v2", "eligible_api_repositories": len(eligible),
        "detail_repositories": len(details), "authentic_readmes": len(fetched),
        "master_readme_coverage": round(coverage, 6),
        "collected_detail_readme_rate": round(detail_authenticity, 6),
        "generated_readmes": sum(bool(row.get("readme_generated")) for row in details),
        "checks": checks, "passed": all(checks.values()),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
