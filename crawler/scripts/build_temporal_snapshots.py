"""Create reproducible observation and publication-quarter metrics."""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

BASE = Path(__file__).resolve().parents[1]
INDEX = BASE / "data/gold/temporal/job_temporal_index.jsonl"
SNAPSHOTS = BASE / "data/snapshots/jobs"
REPORT = BASE / "data/reports/job_temporal_snapshot_report.json"


def main() -> int:
    rows = [json.loads(x) for x in INDEX.read_text(encoding="utf-8").splitlines() if x.strip()]
    now = datetime.now(ZoneInfo("Asia/Shanghai")).replace(microsecond=0)
    date = now.date().isoformat(); target = SNAPSHOTS / date; target.mkdir(parents=True, exist_ok=True)
    source_counts = Counter(x["source"] for x in rows)
    observed_counts = Counter(x["observed_date"] for x in rows if x["observed_date"])
    quarter_source = defaultdict(Counter); quarter_family = defaultdict(Counter); quarter_total = Counter()
    for row in rows:
        if not row["temporal_eligible"]: continue
        quarter = row["publication_quarter"]
        quarter_total[quarter] += 1; quarter_source[quarter][row["source"]] += 1
        quarter_family[quarter][row["standard_job_name"] or "未标准化"] += 1
    metrics = {
        "snapshot_type": "observation_metrics", "snapshot_date": date, "generated_at": now.isoformat(),
        "active_jobs": len(rows), "source_counts": dict(source_counts), "observed_date_counts": dict(observed_counts),
        "publication_quarters": {q: {"eligible_unique_jobs": quarter_total[q], "source_counts": dict(quarter_source[q]), "top_job_families": dict(quarter_family[q].most_common(30))} for q in sorted(quarter_total)},
        "batch_ids": sorted({x["crawl_batch_id"] for x in rows if x["crawl_batch_id"]}),
        "warning": "Publication trends exclude missing, invalid and suspiciously uniform source dates. Observation dates are not publication dates."
    }
    (target / "metrics.json").write_text(json.dumps(metrics, ensure_ascii=False, indent=2), encoding="utf-8")
    report = {"snapshot_date": date, "snapshot_path": str((target / 'metrics.json').relative_to(BASE)).replace('\\','/'), "active_jobs": len(rows), "publication_quarters": len(quarter_total), "batch_count": len(metrics["batch_ids"]), "passed": bool(rows)}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)); return 0 if rows else 1


if __name__ == "__main__": raise SystemExit(main())
