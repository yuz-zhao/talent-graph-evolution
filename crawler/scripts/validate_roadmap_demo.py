#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    path = ROOT / "crawler/data/evaluation/roadmap_demo_cases.json"
    demo = json.loads(path.read_text(encoding="utf-8"))
    new_job = demo["new_job"]
    change = demo["existing_job_change"]
    checks = {
        "new_job_is_evidence_backed": new_job["candidate_type"] in {"early_watch", "capability_direction"} and bool(new_job["representative_evidence"]),
        "new_job_urls_present": all(item.get("source_url", "").startswith("http") and item.get("evidence_text") for item in new_job["representative_evidence"]),
        "new_job_versioned": new_job["algorithm_version"] == "new_job_discovery_v3.0.0",
        "existing_change_is_supported": change["status"] in {"added", "deleted", "modified", "sustained", "insufficient_evidence"},
        "existing_change_has_evidence": all(item.get("source_url", "").startswith("http") and item.get("snippet") for item in change["evidence"]),
        "existing_change_versioned": change["algorithm_version"] == "job_skill_evolution_v2",
        "no_human_gold_claim": demo.get("human_review_claimed", False) is False,
    }
    report = {"demo_version": demo.get("demo_version"), "checks": checks, "passed": all(checks.values())}
    out = ROOT / "crawler/data/reports/roadmap_demo_acceptance.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
