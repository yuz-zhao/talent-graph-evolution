"""Build a strict temporal index for current real job records."""
from __future__ import annotations
import json
from collections import Counter, defaultdict
from pathlib import Path
import sys

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))
from utils.time_utils import normalize_source_time, parse_datetime

GOLD = BASE / "data/gold/records"
OUT = BASE / "data/gold/temporal/job_temporal_index.jsonl"
REPORT = BASE / "data/reports/job_temporal_quality_report.json"


def load_jobs():
    for path in GOLD.glob("*_job.jsonl"):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            env = json.loads(line); payload = env.get("payload") or {}
            synthetic = str(payload.get("is_synthetic", "")).strip().lower() in {"1", "true", "yes"} or payload.get("data_provenance") == "synthetic"
            if env.get("lifecycle_status") == "expired" or synthetic:
                continue
            yield path.stem, env, payload


def main() -> int:
    rows = []
    per_source_dates = defaultdict(list)
    for filename, env, payload in load_jobs():
        observed = env.get("last_seen_at") or env.get("crawled_at") or payload.get("observed_at") or ""
        raw = env.get("source_published_at") or payload.get("source_published_at") or payload.get("publish_time") or payload.get("published_at") or payload.get("date_posted") or ""
        parsed = normalize_source_time(raw, observed)
        source = env.get("source_platform") or payload.get("source_name") or filename
        date_key = parsed["source_published_at"][:10] if parsed["source_published_at"] else ""
        if date_key: per_source_dates[source].append(date_key)
        rows.append({
            "record_id": env.get("record_id"),
            "canonical_job_id": payload.get("canonical_job_id") or env.get("record_id"),
            "source": source,
            "source_url": env.get("source_url") or payload.get("source_url") or "",
            "job_title": payload.get("job_title") or payload.get("title") or "",
            "standard_job_name": payload.get("standard_job_name") or "",
            "location": payload.get("location") or "",
            "first_seen_at": env.get("first_seen_at") or "",
            "last_seen_at": env.get("last_seen_at") or "",
            "observed_at": observed,
            "observed_date": observed[:10],
            **parsed,
            "publication_quarter": "",
            "temporal_eligible": False,
            "temporal_exclusion_reason": "",
            "crawl_batch_id": env.get("crawl_batch_id") or "",
        })

    source_quality = {}
    suspicious_sources = set()
    for source, dates in per_source_dates.items():
        top_date, top_count = Counter(dates).most_common(1)[0]
        concentration = top_count / max(len(dates), 1)
        suspicious = len(dates) >= 20 and concentration >= 0.80
        if suspicious: suspicious_sources.add(source)
        source_quality[source] = {"valid_dates": len(dates), "top_date": top_date, "top_date_ratio": round(concentration, 4), "suspicious_uniform_date": suspicious}

    for row in rows:
        stamp = parse_datetime(row["source_published_at"])
        if not stamp:
            row["temporal_exclusion_reason"] = "missing_or_invalid_source_published_at"
        elif row["source"] in suspicious_sources:
            row["temporal_exclusion_reason"] = "suspicious_uniform_source_date"
        else:
            row["temporal_eligible"] = True
            row["publication_quarter"] = f"{stamp.year}-Q{(stamp.month - 1) // 3 + 1}"

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows: handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    valid = sum(bool(x["source_published_at"]) for x in rows)
    eligible = sum(x["temporal_eligible"] for x in rows)
    report = {
        "total_jobs": len(rows), "valid_source_published_at": valid,
        "published_at_coverage": round(valid / max(len(rows), 1), 4),
        "trend_eligible_jobs": eligible, "trend_eligible_rate": round(eligible / max(len(rows), 1), 4),
        "first_seen_coverage": round(sum(bool(x["first_seen_at"]) for x in rows) / max(len(rows), 1), 4),
        "suspicious_uniform_date_sources": sorted(suspicious_sources), "source_quality": source_quality,
        "missing_dates_are_not_imputed": True,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
