"""R04 acceptance checks without requiring network access."""
from __future__ import annotations
import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def lines(path): return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def main() -> int:
    temporal = lines(BASE / "data/gold/temporal/job_temporal_index.jsonl")
    versions = lines(BASE / "data/gold/temporal/job_versions.jsonl")
    snapshot_report = json.loads((BASE / "data/reports/job_temporal_snapshot_report.json").read_text(encoding="utf-8"))
    health = json.loads((BASE / "data/reports/source_health_report.json").read_text(encoding="utf-8"))
    checks = {
        "temporal_index_not_empty": bool(temporal),
        "publication_and_observation_are_separate": all("source_published_at" in x and "first_seen_at" in x and "observed_at" in x for x in temporal),
        "missing_publication_not_fabricated": all(x["source_published_at"] or not x["temporal_eligible"] for x in temporal),
        "eligible_jobs_have_quarter": all(x["publication_quarter"] for x in temporal if x["temporal_eligible"]),
        "versions_have_batches": bool(versions) and all(x["crawl_batch_id"] for x in versions),
        "snapshot_written": Path(BASE / snapshot_report["snapshot_path"]).exists(),
        "source_health_available": health.get("source_count", 0) > 0,
        "scheduler_registry_exists": (BASE / "config/schedule_registry.json").exists(),
    }
    report = {"checks": checks, "counts": {"jobs": len(temporal), "versions": len(versions), "sources": health.get("source_count", 0)}, "passed": all(checks.values())}
    (BASE / "data/reports/temporal_pipeline_acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)); return 0 if report["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
