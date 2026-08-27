"""R04 isolated-source incremental pipeline with downstream snapshots and monitoring."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
RUNS = BASE / "data/reports/pipeline_runs"
DOWNSTREAM = [
    ("audit_multisource_data.py", BASE / "scripts/audit_multisource_data.py"),
    ("validate_multisource_audit.py", BASE / "scripts/validate_multisource_audit.py"),
    ("build_job_temporal_index.py", BASE / "scripts/build_job_temporal_index.py"),
    ("build_job_versions.py", BASE / "scripts/build_job_versions.py"),
    ("build_temporal_snapshots.py", BASE / "scripts/build_temporal_snapshots.py"),
    ("detect_job_skill_evolution.py", BASE / "scripts/detect_job_skill_evolution.py"),
    ("validate_job_skill_evolution.py", BASE / "scripts/validate_job_skill_evolution.py"),
    ("build_source_health_report.py", BASE / "scripts/build_source_health_report.py"),
    ("etl_build_graph.py", BASE.parent / "knowledge_graph/etl_build_graph.py"),
    ("build_cross_source_evidence.py", BASE / "scripts/build_cross_source_evidence.py"),
    ("validate_cross_source_evidence.py", BASE / "scripts/validate_cross_source_evidence.py"),
    ("build_rag_evaluation.py", BASE / "scripts/build_rag_evaluation.py"),
    ("discover_new_jobs_v3.py", BASE / "scripts/discover_new_jobs_v3.py"),
    ("validate_new_job_discovery_v3.py", BASE / "scripts/validate_new_job_discovery_v3.py"),
]


def execute(args: list[str], timeout: int) -> dict:
    started = datetime.now(timezone.utc)
    try:
        completed = subprocess.run(args, cwd=BASE.parent, text=True, capture_output=True, timeout=timeout)
        return {"status": "success" if completed.returncode == 0 else "failed", "return_code": completed.returncode, "stdout": completed.stdout[-4000:], "stderr": completed.stderr[-4000:], "duration_seconds": round((datetime.now(timezone.utc)-started).total_seconds(), 2)}
    except subprocess.TimeoutExpired as exc:
        return {"status": "timeout", "return_code": None, "stdout": str(exc.stdout or "")[-4000:], "stderr": str(exc.stderr or "")[-4000:], "duration_seconds": round((datetime.now(timezone.utc)-started).total_seconds(), 2)}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sources", default="")
    parser.add_argument("--from-existing", action="store_true")
    parser.add_argument("--skip-collection", action="store_true")
    parser.add_argument("--timeout-minutes", type=int, default=90)
    args = parser.parse_args()
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report = {"run_id": run_id, "started_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(), "sources": {}, "downstream": {}}
    if not args.skip_collection:
        for source in [x.strip() for x in args.sources.split(",") if x.strip()]:
            command = [sys.executable, str(BASE / "scripts/run_collection.py"), "--sources", source]
            if args.from_existing: command.append("--from-existing")
            report["sources"][source] = execute(command, args.timeout_minutes * 60)
    for name, script in DOWNSTREAM:
        report["downstream"][name] = execute([sys.executable, str(script)], args.timeout_minutes * 60)
    report["finished_at"] = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    failures = [name for name, item in {**report["sources"], **report["downstream"]}.items() if item["status"] != "success"]
    report["status"] = "success" if not failures else "partial_failed"
    report["failed_steps"] = failures
    RUNS.mkdir(parents=True, exist_ok=True)
    (RUNS / f"{run_id}.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)); return 0 if not failures else 2


if __name__ == "__main__": raise SystemExit(main())
