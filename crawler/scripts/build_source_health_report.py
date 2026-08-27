"""Aggregate collection batch reports into source health and alert states."""
from __future__ import annotations
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
REPORTS = BASE / "data/reports/collection"
OUT = BASE / "data/reports/source_health_report.json"
AUDIT = BASE / "data/reports/multisource_audit_report.json"


def main() -> int:
    aliases = {"Greenhouse":"enterprise-greenhouse", "Arbeitnow":"arbeitnow", "Remotive":"remotive", "国家大学生就业服务平台":"ncss", "智联招聘":"zhaopin", "猎聘":"liepin", "腾讯招聘官网":"tencent-careers", "中国电信招聘官网":"china-telecom-careers", "中国信通院招聘官网":"caict-careers"}
    audit_quality = {}
    if AUDIT.exists():
        try:
            raw_audit = json.loads(AUDIT.read_text(encoding="utf-8")).get("source_quality", {})
            audit_quality = {aliases.get(name, name): value for name, value in raw_audit.items()}
        except (OSError, json.JSONDecodeError):
            audit_quality = {}
    grouped = defaultdict(list)
    for path in REPORTS.glob("*.json"):
        try: report = json.loads(path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError): continue
        if report.get("source"):
            source = aliases.get(report["source"], report["source"])
            report["source"] = source
            grouped[source].append(report)
    sources = []
    for source, runs in grouped.items():
        runs.sort(key=lambda x: x.get("started_at") or "", reverse=True); latest = runs[0]
        recent = runs[:10]; failed = sum(x.get("status") not in {"success"} for x in recent)
        consecutive = 0
        for run in runs:
            if run.get("status") == "success": break
            consecutive += 1
        alerts = []
        if consecutive >= 3: alerts.append("consecutive_failures")
        if latest.get("fetched", 0) == 0: alerts.append("empty_latest_batch")
        if float(latest.get("quality", {}).get("published_at_coverage", 1)) < .95 and latest.get("data_type") == "job": alerts.append("low_publish_time_coverage")
        audit = audit_quality.get(source, {})
        sources.append({
            "source": source, "data_type": latest.get("data_type"), "last_run_at": latest.get("started_at"),
            "last_success_at": next((x.get("finished_at") for x in runs if x.get("status") == "success"), ""),
            "latest_status": latest.get("status"), "recent_runs": len(recent), "recent_failed_runs": failed,
            "consecutive_failures": consecutive, "latest_fetched": latest.get("fetched", 0),
            "latest_valid": latest.get("valid", 0), "latest_rejected": latest.get("rejected", 0),
            "latest_quality": latest.get("quality", {}), "alerts": alerts,
            "audit_quality": audit,
            "source_weight": audit.get("source_weight"),
            "audit_algorithm_version": audit.get("weight_version", ""),
        })
    sources.sort(key=lambda x: x["source"])
    payload = {"generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "source_count": len(sources), "healthy_sources": sum(not x["alerts"] and x["latest_status"] == "success" for x in sources), "alert_count": sum(len(x["alerts"]) for x in sources), "sources": sources}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
