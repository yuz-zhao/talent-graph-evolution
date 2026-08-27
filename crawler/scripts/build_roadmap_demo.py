#!/usr/bin/env python3
"""Freeze deterministic, evidence-backed examples for the roadmap demo."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> int:
    candidates = json.loads((ROOT / "crawler/data/gold/new_jobs/new_job_candidates.json").read_text(encoding="utf-8"))
    candidate = next(item for item in candidates["candidates"] if item.get("candidate_type") == "early_watch" and item.get("representative_evidence"))
    change = next(json.loads(line) for line in (ROOT / "crawler/data/gold/temporal/job_skill_change_events.jsonl").read_text(encoding="utf-8").splitlines() if json.loads(line).get("status") in {"added", "deleted", "modified"} and json.loads(line).get("evidence"))
    demo = {
        "demo_version": "roadmap_demo_v1",
        "source_artifacts": [
            "crawler/data/gold/new_jobs/new_job_candidates.json",
            "crawler/data/gold/temporal/job_skill_change_events.jsonl",
        ],
        "new_job": {
            "candidate_id": candidate["candidate_id"], "name": candidate["name"],
            "candidate_type": candidate["candidate_type"], "parent_job": candidate["parent_job"],
            "confidence": candidate["confidence"], "score": candidate["score"],
            "top_skills": candidate["top_skills"], "representative_evidence": candidate["representative_evidence"][:3],
            "algorithm_version": candidate["algorithm_version"], "review_status": candidate["review_status"],
        },
        "existing_job_change": {
            "event_id": change["event_id"], "job_name": change["job_name"], "skill": change["skill"],
            "from_month": change["from_month"], "to_month": change["to_month"], "status": change["status"],
            "previous_share": change["previous_share"], "current_share": change["current_share"],
            "previous_relation": change["previous_relation"], "current_relation": change["current_relation"],
            "evidence": change["evidence"][:3], "algorithm_version": change["algorithm_version"],
        },
    }
    out = ROOT / "crawler/data/evaluation/roadmap_demo_cases.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(demo, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"passed": True, "output": out.relative_to(ROOT).as_posix(), "new_job": demo["new_job"]["name"], "existing_job": demo["existing_job_change"]["job_name"], "change_status": demo["existing_job_change"]["status"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
