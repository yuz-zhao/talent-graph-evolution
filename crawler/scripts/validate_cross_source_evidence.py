"""Acceptance checks for R03 formal cross-source evidence outputs."""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "crawler" / "data"


def main() -> int:
    evidence_path = DATA / "gold" / "evidence" / "skill_evidence.jsonl"
    result_path = DATA / "gold" / "evidence" / "skill_validation_results.json"
    evidence = [json.loads(line) for line in evidence_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    result = json.loads(result_path.read_text(encoding="utf-8"))
    job_skills = [x for x in result["skills"] if x["group_counts"]["job"] > 0]
    checks = {
        "evidence_not_empty": len(evidence) > 0,
        "all_evidence_has_url_and_text": all(x.get("source_url") and x.get("evidence_text") for x in evidence),
        "all_evidence_has_skill_id": all(str(x.get("skill_id", "")).startswith("skill_") for x in evidence),
        "all_evidence_is_versioned": all(x.get("algorithm_version") == result.get("algorithm_version") for x in evidence),
        "strong_requires_two_external_groups": all(x["independent_external_groups"] >= 2 for x in job_skills if x["validation_level"] == "strong"),
        "no_plagiarism_label_from_absence": all(x["validation_level"] not in {"suspicious", "plagiarism", "inflated"} for x in result["skills"]),
        "representative_evidence_returned": all(x.get("representative_evidence") for x in job_skills),
    }
    report = {"checks": checks, "counts": {"evidence": len(evidence), "job_skills": len(job_skills)}, "passed": all(checks.values())}
    out = DATA / "reports" / "cross_source_validation_acceptance.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
