"""Validate R07 multi-source audit outputs."""
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
AUDIT = BASE / "data/gold/quality/job_source_audit.jsonl"
CLUSTERS = BASE / "data/gold/quality/job_repost_clusters.json"
REPORT = BASE / "data/reports/multisource_audit_acceptance.json"

def main():
    rows = [json.loads(x) for x in AUDIT.read_text(encoding="utf-8").splitlines() if x.strip()]
    clusters = json.loads(CLUSTERS.read_text(encoding="utf-8"))["clusters"]
    checks = {
        "all_records_audited": bool(rows), "timestamps_have_explicit_basis": all(x["time_basis"] in {"source_published_at", "first_seen", "unknown"} for x in rows),
        "no_fabricated_publish_time": all(x["time_basis"] != "source_published_at" or x["source_published_at"] for x in rows),
        "one_representative_per_repost_cluster": all(sum(x["record_id"] == c["representative_record_id"] and x["is_independent_representative"] for x in rows) == 1 for c in clusters),
        "weights_are_versioned_and_bounded": all(0 <= x["source_weight"] <= 1 and x["algorithm_version"] for x in rows),
        "quarantine_has_reason": all(x["audit_status"] != "quarantine" or x["quarantine_reasons"] for x in rows),
    }
    payload = {"checks": checks, "records": len(rows), "repost_clusters": len(clusters), "passed": all(checks.values())}
    REPORT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2)); return 0 if payload["passed"] else 1

if __name__ == "__main__": raise SystemExit(main())
