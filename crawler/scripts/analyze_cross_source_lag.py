"""Estimate evidence-gated lead/lag associations between external signals and JD demand."""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
LIFECYCLE = BASE / "data/gold/temporal/skill_lifecycle_trends.jsonl"
ARXIV = BASE / "data/gold/records/arxiv_paper.jsonl"
BLOG = BASE / "data/gold/records/blog_technology_article.jsonl"
OUTPUT = BASE / "data/gold/temporal/skill_cross_source_lag.jsonl"
REPORT = BASE / "data/reports/cross_source_lag_report.json"
VERSION = "cross_source_lag_v1"


def load_jsonl(path):
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def shift_month(month, offset):
    stamp = datetime.strptime(month, "%Y-%m")
    value = stamp.year * 12 + stamp.month - 1 + offset
    return f"{value // 12:04d}-{value % 12 + 1:02d}"


def pearson(left, right):
    if len(left) != len(right) or len(left) < 2:
        return None
    left_mean, right_mean = sum(left) / len(left), sum(right) / len(right)
    numerator = sum((a - left_mean) * (b - right_mean) for a, b in zip(left, right))
    left_ss = sum((a - left_mean) ** 2 for a in left)
    right_ss = sum((b - right_mean) ** 2 for b in right)
    if left_ss <= 0 or right_ss <= 0:
        return None
    return numerator / math.sqrt(left_ss * right_ss)


def fisher_interval(correlation, sample_size, confidence_z=1.96):
    if correlation is None or sample_size <= 3:
        return None
    bounded = max(-0.999999, min(0.999999, correlation))
    transformed = math.atanh(bounded)
    margin = confidence_z / math.sqrt(sample_size - 3)
    return [round(math.tanh(transformed - margin), 6), round(math.tanh(transformed + margin), 6)]


def lag_candidates(external, jd, max_lead=6, minimum_pairs=6):
    candidates = []
    for lead in range(max_lead + 1):
        pairs = [(value, jd[shift_month(month, lead)]) for month, value in external.items() if shift_month(month, lead) in jd]
        if len(pairs) < minimum_pairs:
            continue
        correlation = pearson([pair[0] for pair in pairs], [pair[1] for pair in pairs])
        if correlation is None:
            continue
        interval = fisher_interval(correlation, len(pairs))
        candidates.append({
            "lead_months": lead,
            "correlation": round(correlation, 6),
            "confidence_interval_95": interval,
            "sample_size": len(pairs),
            "window_start": min(month for month in external if shift_month(month, lead) in jd),
            "window_end": max(month for month in external if shift_month(month, lead) in jd),
        })
    return candidates


def external_monthly(rows, official_only=False):
    totals = Counter()
    skills = defaultdict(Counter)
    evidence = defaultdict(list)
    for row in rows:
        payload = row.get("payload") or {}
        if official_only and not str(payload.get("source_kind") or "").startswith("official"):
            continue
        published = row.get("source_published_at") or payload.get("published_at") or ""
        if len(str(published)) < 7:
            continue
        month = str(published)[:7]
        totals[month] += 1
        for skill in payload.get("relationship_skills") or payload.get("inferred_skills") or []:
            skills[skill][month] += 1
            if len(evidence[skill]) < 3 and row.get("source_url"):
                evidence[skill].append({"source_url": row["source_url"], "published_at": published, "source": row.get("source_platform")})
    shares = {
        skill: {month: monthly.get(month, 0) / total for month, total in totals.items()}
        for skill, monthly in skills.items()
    }
    return shares, evidence, totals


def analyze(lifecycle, sources):
    jd_by_skill = {row["skill"]: {point["month"]: point["jd_share"] for point in row.get("series") or []} for row in lifecycle}
    results = []
    for source_name, (series_by_skill, evidence, totals) in sources.items():
        for skill in sorted(set(jd_by_skill) & set(series_by_skill)):
            candidates = lag_candidates(series_by_skill[skill], jd_by_skill[skill])
            source_mentions = sum(1 for value in series_by_skill[skill].values() if value > 0)
            if source_mentions < 4 or not candidates:
                results.append({
                    "skill": skill, "source": source_name, "status": "insufficient_evidence",
                    "fallback_reason": "requires_four_active_source_months_and_six_overlapping_months",
                    "source_active_months": source_mentions, "candidates": [], "evidence": evidence[skill],
                    "claim_scope": "exploratory_association", "algorithm_version": VERSION,
                })
                continue
            best = max(candidates, key=lambda item: (item["correlation"], item["sample_size"], -item["lead_months"]))
            interval = best["confidence_interval_95"] or [-1, 1]
            supported = best["correlation"] > 0 and interval[0] > 0
            results.append({
                "skill": skill, "source": source_name, "status": "supported" if supported else "exploratory",
                "best_lead_months": best["lead_months"], "correlation": best["correlation"],
                "confidence_interval_95": interval, "sample_size": best["sample_size"],
                "window_start": best["window_start"], "window_end": best["window_end"],
                "source_active_months": source_mentions, "candidates": candidates, "evidence": evidence[skill],
                "fallback_reason": None if supported else "confidence_interval_includes_zero",
                "claim_scope": "exploratory_association", "causal_claim": False, "algorithm_version": VERSION,
            })
    return results


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("".join(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")


def main():
    lifecycle = load_jsonl(LIFECYCLE)
    arxiv = external_monthly(load_jsonl(ARXIV))
    blog = external_monthly(load_jsonl(BLOG), official_only=True)
    results = analyze(lifecycle, {"arxiv": arxiv, "official_blog": blog})
    write_jsonl(OUTPUT, results)
    counts = Counter(row["status"] for row in results)
    report = {
        "algorithm_version": VERSION, "results": len(results), "status_counts": dict(counts),
        "source_months": {"arxiv": len(arxiv[2]), "official_blog": len(blog[2])},
        "github_status": "unavailable", "github_fallback_reason": "no_reliable_monthly_star_fork_or_skill_history",
        "claim_scope": "exploratory_association", "causal_claim": False,
    }
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
