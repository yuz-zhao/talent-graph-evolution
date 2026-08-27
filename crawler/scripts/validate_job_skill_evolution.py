"""Acceptance checks for evidence-gated job skill evolution."""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    snapshots = load_jsonl(BASE / "data/gold/temporal/job_skill_monthly_snapshots.jsonl")
    events = load_jsonl(BASE / "data/gold/temporal/job_skill_change_events.jsonl")
    lifecycle = load_jsonl(BASE / "data/gold/temporal/skill_lifecycle_trends.jsonl")
    report = json.loads((BASE / "data/reports/job_skill_evolution_report.json").read_text(encoding="utf-8"))
    allowed = {"added", "deleted", "modified", "sustained", "insufficient_evidence"}
    checks = {
        "all_19035_versions_processed": report.get("input_versions") == 19035,
        "monthly_snapshots_available": bool(snapshots),
        "change_events_available": bool(events),
        "three_window_examples_available": report.get("jobs_with_three_or_more_windows", 0) > 0,
        "only_supported_statuses": all(event.get("status") in allowed for event in events),
        "insufficient_events_explain_fallback": all(
            event.get("fallback_reason") for event in events if event.get("status") == "insufficient_evidence"
        ),
        "formal_changes_have_evidence_urls": all(
            any(item.get("source_url") for item in event.get("evidence", []))
            for event in events if event.get("status") in {"added", "deleted", "modified"}
        ),
        "confirmed_evolution_requires_prior_continuity": all(
            event.get("previous_support", 0) >= 2 and event.get("previous_sources", 0) >= 2
            for event in events if event.get("publication_status") == "confirmed_evolution"
        ),
        "all_change_signals_have_publication_status": all(
            event.get("publication_status") in {"confirmed_evolution", "statistical_signal", "not_applicable"}
            for event in events
        ),
        "deletion_requires_three_windows": all(
            event.get("previous_support", 0) >= 3 and event.get("probability_down", 0) >= 0.95
            for event in events if event.get("status") == "deleted"
        ),
        "algorithm_mode_exposed": all(event.get("algorithm_mode") and event.get("algorithm_version") for event in events),
        "lifecycle_trends_available": bool(lifecycle),
        "lifecycle_window_and_version_exposed": all(
            item.get("window_start") and item.get("window_end") and item.get("algorithm_mode") and item.get("algorithm_version")
            for item in lifecycle
        ),
        "lifecycle_insufficient_explained": all(
            item.get("fallback_reason") for item in lifecycle if item.get("lifecycle") == "insufficient_evidence"
        ),
        "independent_company_count_exposed": all(
            all("independent_company_count" in point for point in item.get("series", [])) for item in lifecycle
        ),
        "formal_lifecycle_has_evidence": all(
            any(evidence.get("source_url") for evidence in item.get("evidence", []))
            for item in lifecycle if item.get("lifecycle") not in {"insufficient_evidence", "observed"}
        ),
    }
    result = {"passed": all(checks.values()), "checks": checks, "counts": {"snapshots": len(snapshots), "events": len(events), "lifecycle": len(lifecycle)}, "status_counts": report.get("status_counts", {}), "lifecycle_counts": report.get("lifecycle_counts", {})}
    out = BASE / "data/reports/job_skill_evolution_acceptance.json"
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
