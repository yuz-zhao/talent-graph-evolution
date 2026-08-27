"""Acceptance checks for cross-source lead/lag artifacts."""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]


def load_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main():
    rows = load_jsonl(BASE / "data/gold/temporal/skill_cross_source_lag.jsonl")
    report = json.loads((BASE / "data/reports/cross_source_lag_report.json").read_text(encoding="utf-8"))
    checks = {
        "results_available": bool(rows),
        "claim_scope_is_noncausal": report.get("causal_claim") is False and all(row.get("claim_scope") == "exploratory_association" for row in rows),
        "github_unavailable_is_explicit": report.get("github_status") == "unavailable" and bool(report.get("github_fallback_reason")),
        "insufficient_results_explain_reason": all(row.get("fallback_reason") for row in rows if row.get("status") == "insufficient_evidence"),
        "computed_results_have_statistics": all(
            row.get("sample_size", 0) >= 6 and row.get("confidence_interval_95") and row.get("window_start") and row.get("window_end")
            for row in rows if row.get("status") in {"supported", "exploratory"}
        ),
        "computed_results_have_evidence": all(
            any(item.get("source_url") for item in row.get("evidence", []))
            for row in rows if row.get("status") in {"supported", "exploratory"}
        ),
        "positive_lead_definition_exposed": all(
            row.get("best_lead_months", 0) >= 0 for row in rows if row.get("status") in {"supported", "exploratory"}
        ),
    }
    result = {"passed": all(checks.values()), "checks": checks, "counts": report.get("status_counts", {})}
    path = BASE / "data/reports/cross_source_lag_acceptance.json"
    path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
