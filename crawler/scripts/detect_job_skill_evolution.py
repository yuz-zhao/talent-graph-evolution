"""Detect evidence-gated skill evolution from reconstructed job versions."""
from __future__ import annotations

import json
import math
import random
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

BASE = Path(__file__).resolve().parents[1]
VERSIONS = BASE / "data" / "gold" / "temporal" / "job_versions.jsonl"
SNAPSHOTS = BASE / "data" / "gold" / "temporal" / "job_skill_monthly_snapshots.jsonl"
EVENTS = BASE / "data" / "gold" / "temporal" / "job_skill_change_events.jsonl"
LIFECYCLE = BASE / "data" / "gold" / "temporal" / "skill_lifecycle_trends.jsonl"
REPORT = BASE / "data" / "reports" / "job_skill_evolution_report.json"
RULES = BASE / "config" / "evidence_rules.json"
SOURCE_AUDIT = BASE / "data" / "gold" / "quality" / "job_source_audit.jsonl"
VERSION = "job_skill_evolution_v3"
POSTERIOR_DRAWS = 1000


def load_jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def canonical_url(value):
    try:
        parts = urlsplit(str(value or "").strip())
        query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")))
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower().removeprefix("www."), parts.path.rstrip("/"), query, ""))
    except ValueError:
        return str(value or "").strip()


def clamp(value, low=0.0, high=1.0):
    try:
        return max(low, min(high, float(value)))
    except (TypeError, ValueError):
        return low


def parse_date(value):
    text = str(value or "").strip()
    if len(text) < 7:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        try:
            return datetime.strptime(text[:10], "%Y-%m-%d").replace(tzinfo=timezone.utc)
        except ValueError:
            return None


def normal_cdf(value):
    return 0.5 * (1.0 + math.erf(value / math.sqrt(2.0)))


def beta_stats(support, total):
    alpha = max(0.0, support) + 1.0
    beta = max(0.0, total - support) + 1.0
    denominator = alpha + beta
    mean = alpha / denominator
    variance = alpha * beta / (denominator * denominator * (denominator + 1.0))
    return mean, variance


def quantile(values, probability):
    ordered = sorted(values)
    position = (len(ordered) - 1) * probability
    lower = int(math.floor(position))
    upper = int(math.ceil(position))
    if lower == upper:
        return ordered[lower]
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def posterior_difference(current_support, current_total, previous_support, previous_total, threshold, seed):
    """Directly sample the two Beta posteriors; robust for sparse/extreme cohorts."""
    rng = random.Random(seed)
    current_alpha, current_beta = max(0.0, current_support) + 1.0, max(0.0, current_total - current_support) + 1.0
    previous_alpha, previous_beta = max(0.0, previous_support) + 1.0, max(0.0, previous_total - previous_support) + 1.0
    differences = [
        rng.betavariate(current_alpha, current_beta) - rng.betavariate(previous_alpha, previous_beta)
        for _ in range(POSTERIOR_DRAWS)
    ]
    return {
        "probability_up": sum(value > threshold for value in differences) / POSTERIOR_DRAWS,
        "probability_down": sum(value < -threshold for value in differences) / POSTERIOR_DRAWS,
        "credible_interval_95": [quantile(differences, 0.025), quantile(differences, 0.975)],
        "draws": POSTERIOR_DRAWS,
    }


def source_mix_distance(previous, current):
    """Total-variation distance: 0=same source mix, 1=disjoint source mix."""
    keys = set(previous) | set(current)
    p_total, c_total = sum(previous.values()), sum(current.values())
    if p_total <= 0 or c_total <= 0:
        return 1.0
    return 0.5 * sum(abs(previous.get(key, 0) / p_total - current.get(key, 0) / c_total) for key in keys)


def difference_probability(current, previous, threshold):
    mean = current[0] - previous[0]
    std = math.sqrt(max(1e-12, current[1] + previous[1]))
    up = 1.0 - normal_cdf((threshold - mean) / std)
    down = normal_cdf((-threshold - mean) / std)
    return up, down


def month_of(row):
    stamp = parse_date(row.get("source_published_at"))
    return stamp.strftime("%Y-%m") if stamp else ""


def evidence_weight(row, source_reliability, newest_date, audit=None):
    reliability = clamp((audit or {}).get("source_weight"), 0.0, 1.0) or source_reliability.get(row.get("source_type"), source_reliability.get("job", 0.8))
    url_validity = 1.0 if str(row.get("source_url", "")).startswith(("http://", "https://")) else 0.0
    text_length = len(str(row.get("description") or "")) + len(str(row.get("requirements") or ""))
    text_completeness = min(1.0, max(0.25, text_length / 500.0))
    published = parse_date(row.get("source_published_at"))
    age_days = max(0, (newest_date - published).days) if published else 3650
    recency = math.exp(-math.log(2.0) * age_days / 730.0)
    duplicate_probability = clamp(row.get("duplicate_score"), 0.0, 0.95)
    evidence_score = clamp(row.get("evidence_score"), 0.0, 1.0) or 0.75
    return reliability * url_validity * text_completeness * recency * (1.0 - duplicate_probability) * evidence_score


def dominant_relation(counter):
    priority = {"required": 3, "preferred": 2, "mentioned": 1}
    if not counter:
        return "mentioned"
    return max(counter, key=lambda name: (counter[name], priority.get(name, 0)))


def mann_kendall(values):
    n = len(values)
    if n < 4:
        return {"z": 0.0, "p_value": 1.0, "direction": "insufficient_evidence"}
    score = sum((values[j] > values[i]) - (values[j] < values[i]) for i in range(n - 1) for j in range(i + 1, n))
    ties = Counter(values)
    variance = (n * (n - 1) * (2 * n + 5) - sum(t * (t - 1) * (2 * t + 5) for t in ties.values())) / 18.0
    if variance <= 0:
        z = 0.0
    elif score > 0:
        z = (score - 1) / math.sqrt(variance)
    elif score < 0:
        z = (score + 1) / math.sqrt(variance)
    else:
        z = 0.0
    p_value = 2.0 * (1.0 - normal_cdf(abs(z)))
    direction = "increasing" if z > 0 else "decreasing" if z < 0 else "stable"
    return {"z": round(z, 6), "p_value": round(p_value, 6), "direction": direction}


def ewma_cusum(values, alpha=0.35):
    if len(values) < 4:
        return {"detected": False, "direction": "none", "change_index": None, "score": 0.0}
    baseline_values = values[: min(3, len(values))]
    baseline = sum(baseline_values) / len(baseline_values)
    variance = sum((value - baseline) ** 2 for value in baseline_values) / max(1, len(baseline_values) - 1)
    sigma = max(math.sqrt(variance), 0.01)
    positive = negative = 0.0
    best_score, best_index, best_direction = 0.0, None, "none"
    ewma = values[0]
    for index, value in enumerate(values[1:], 1):
        ewma = alpha * value + (1.0 - alpha) * ewma
        residual = ewma - baseline
        positive = max(0.0, positive + residual - 0.5 * sigma)
        negative = min(0.0, negative + residual + 0.5 * sigma)
        score = max(positive, abs(negative)) / sigma
        if score > best_score:
            best_score, best_index = score, index
            best_direction = "up" if positive >= abs(negative) else "down"
    return {"detected": best_score >= 3.0, "direction": best_direction, "change_index": best_index, "score": round(best_score, 6)}


def build_lifecycle_trends(snapshots):
    monthly_totals = defaultdict(float)
    monthly_jd = Counter()
    by_skill = defaultdict(lambda: defaultdict(lambda: {"support": 0.0, "required": 0, "mentions": 0, "companies": set(), "evidence": []}))
    for snapshot in snapshots:
        month = snapshot["month"]
        monthly_totals[month] += float(snapshot.get("effective_jd_weight") or 0)
        monthly_jd[month] += int(snapshot.get("jd_count") or 0)
        for item in snapshot.get("skills") or []:
            target = by_skill[item["skill"]][month]
            target["support"] += float(item.get("weighted_support") or 0)
            target["required"] += int((item.get("relation_counts") or {}).get("required") or 0)
            target["mentions"] += int(item.get("support_count") or 0)
            target["companies"].update(item.get("companies") or [])
            for evidence in item.get("evidence") or []:
                if evidence.get("source_url") and len(target["evidence"]) < 3:
                    target["evidence"].append(evidence)
    months = sorted(monthly_totals)
    results = []
    for skill, monthly in by_skill.items():
        active_months = [month for month in months if month in monthly]
        series = []
        for month in active_months:
            item = monthly[month]
            series.append({
                "month": month,
                "jd_share": round(item["support"] / max(monthly_totals[month], 1e-9), 6),
                "required_share": round(item["required"] / max(item["mentions"], 1), 6),
                "independent_company_count": len(item["companies"]),
                "jd_count": monthly_jd[month],
            })
        values = [item["jd_share"] for item in series]
        trend = mann_kendall(values)
        change = ewma_cusum(values)
        total_mentions = sum(monthly[month]["mentions"] for month in active_months)
        fallback_reason = None
        if len(series) < 4 or total_mentions < 8:
            state, fallback_reason = "insufficient_evidence", "requires_four_months_and_eight_mentions"
        elif trend["p_value"] <= 0.10 and trend["direction"] == "decreasing":
            state = "declining"
        elif change["detected"] and change["direction"] == "up" and trend["direction"] != "decreasing":
            state = "emerging"
        elif trend["p_value"] <= 0.10 and trend["direction"] == "increasing":
            state = "growth"
        elif values[-1] >= 0.02 and total_mentions >= 20:
            state = "mature"
        else:
            state = "observed"
        evidence = []
        for month in reversed(active_months):
            evidence.extend(monthly[month]["evidence"])
            if len(evidence) >= 3:
                break
        results.append({
            "skill": skill, "lifecycle": state, "window_start": active_months[0], "window_end": active_months[-1],
            "window_count": len(series), "total_mentions": total_mentions, "trend_test": trend,
            "change_point": change, "series": series, "evidence": evidence[:3], "fallback_reason": fallback_reason,
            "algorithm_mode": "monthly_mann_kendall_ewma_cusum", "algorithm_version": VERSION,
        })
    return sorted(results, key=lambda row: (row["lifecycle"] == "insufficient_evidence", -row["total_mentions"], row["skill"]))


def build_snapshots(versions):
    rules = json.loads(RULES.read_text(encoding="utf-8"))
    source_reliability = rules.get("source_reliability", {})
    audit_by_url = {}
    if SOURCE_AUDIT.exists():
        audit_by_url = {x.get("canonical_source_url"): x for x in load_jsonl(SOURCE_AUDIT) if x.get("canonical_source_url")}
    latest = {}
    for row in versions:
        if row.get("is_current") or row.get("version_number", 0) >= latest.get(row.get("record_id"), {}).get("version_number", 0):
            latest[row.get("record_id")] = row
    dates = [parse_date(row.get("source_published_at")) for row in latest.values()]
    dates = [value for value in dates if value]
    newest_date = max(dates) if dates else datetime.now(timezone.utc)
    grouped = defaultdict(list)
    excluded = Counter()
    for row in latest.values():
        audit = audit_by_url.get(canonical_url(row.get("source_url")))
        job_name = str(row.get("standard_job_name") or row.get("job_title") or "").strip()
        month = month_of(row)
        if audit and audit.get("audit_status") == "quarantine":
            excluded["source_quality_quarantine"] += 1
        elif audit and not audit.get("is_independent_representative", True):
            excluded["repost_cluster_duplicate"] += 1
        elif not job_name:
            excluded["missing_job_name"] += 1
        elif not month:
            excluded["missing_publication_month"] += 1
        elif not row.get("skill_snapshot"):
            excluded["missing_skill_snapshot"] += 1
        else:
            grouped[(job_name, month)].append(row)

    snapshots = []
    for (job_name, month), rows in grouped.items():
        total_weight = 0.0
        source_weights = defaultdict(float)
        sources = set()
        companies = set()
        regions = set()
        skill_data = defaultdict(lambda: {
            "weighted_support": 0.0, "support_count": 0, "sources": set(), "companies": set(),
            "relations": Counter(), "evidence": [],
        })
        for row in rows:
            audit = audit_by_url.get(canonical_url(row.get("source_url")))
            weight = evidence_weight(row, source_reliability, newest_date, audit)
            if weight <= 0:
                continue
            total_weight += weight
            source = row.get("source") or "unknown"
            source_weights[source] += weight
            company = row.get("company") or "unknown"
            sources.add(source)
            if company != "unknown": companies.add(company)
            if row.get("location"): regions.add(row["location"])
            relations = row.get("skill_relation_snapshot") or {}
            evidence = row.get("skill_evidence_snapshot") or {}
            for skill in row.get("skill_snapshot") or []:
                item = skill_data[skill]
                item["weighted_support"] += weight
                item["support_count"] += 1
                item["sources"].add(source)
                if company != "unknown": item["companies"].add(company)
                relation = relations.get(skill) or "mentioned"
                item["relations"][relation] += 1
                if len(item["evidence"]) < 3:
                    detail = evidence.get(skill) or {}
                    item["evidence"].append({
                        "source_url": row.get("source_url") or "",
                        "source": source,
                        "company": "" if company == "unknown" else company,
                        "snippet": detail.get("snippet") or "",
                        "confidence": detail.get("confidence"),
                        "version_id": row.get("version_id"),
                    })
        skills = []
        for skill, item in skill_data.items():
            mean, variance = beta_stats(item["weighted_support"], total_weight)
            skills.append({
                "skill": skill,
                "weighted_support": round(item["weighted_support"], 6),
                "posterior_share": round(mean, 6),
                "posterior_variance": round(variance, 8),
                "support_count": item["support_count"],
                "source_count": len(item["sources"]),
                "company_count": len(item["companies"]),
                "companies": sorted(item["companies"]),
                "dominant_relation": dominant_relation(item["relations"]),
                "relation_counts": dict(item["relations"]),
                "required_support_count": item["relations"].get("required", 0),
                "required_share": round(item["relations"].get("required", 0) / max(item["support_count"], 1), 6),
                "evidence": item["evidence"],
            })
        skills.sort(key=lambda item: (-item["posterior_share"], item["skill"]))
        snapshots.append({
            "job_name": job_name, "month": month, "jd_count": len(rows),
            "effective_jd_weight": round(total_weight, 6), "source_count": len(sources),
            "company_count": len(companies), "region_count": len(regions), "skills": skills,
            "source_weight_distribution": {key: round(value, 6) for key, value in sorted(source_weights.items())},
            "algorithm_version": VERSION,
        })
    snapshots.sort(key=lambda row: (row["job_name"], row["month"]))
    return snapshots, excluded


def classify_events(snapshots):
    by_job = defaultdict(list)
    for snapshot in snapshots:
        by_job[snapshot["job_name"]].append(snapshot)
    events = []
    for job_name, windows in by_job.items():
        windows.sort(key=lambda row: row["month"])
        for index in range(1, len(windows)):
            previous, current = windows[index - 1], windows[index]
            older = windows[index - 2] if index >= 2 else None
            previous_map = {item["skill"]: item for item in previous["skills"]}
            current_map = {item["skill"]: item for item in current["skills"]}
            older_map = {item["skill"]: item for item in older["skills"]} if older else {}
            all_skills = sorted(set(previous_map) | set(current_map))
            minimum_n = min(previous["jd_count"], current["jd_count"])
            threshold = max(0.08, min(0.30, 0.50 / math.sqrt(max(1, minimum_n))))
            for skill in all_skills:
                p = previous_map.get(skill, {"posterior_share": 0.0, "posterior_variance": 0.0, "support_count": 0, "source_count": 0, "dominant_relation": "absent", "evidence": []})
                c = current_map.get(skill, {"posterior_share": 0.0, "posterior_variance": 0.0, "support_count": 0, "source_count": 0, "dominant_relation": "absent", "evidence": []})
                o = older_map.get(skill, {"posterior_share": 0.0, "support_count": 0})
                seed = sum(ord(char) for char in f"{job_name}|{skill}|{previous['month']}|{current['month']}")
                posterior = posterior_difference(
                    c.get("weighted_support", 0), current.get("effective_jd_weight", 0),
                    p.get("weighted_support", 0), previous.get("effective_jd_weight", 0), threshold, seed,
                )
                up, down = posterior["probability_up"], posterior["probability_down"]
                mix_distance = source_mix_distance(previous.get("source_weight_distribution", {}), current.get("source_weight_distribution", {}))
                status = "sustained"
                fallback_reason = None
                relation_changed = p["dominant_relation"] != c["dominant_relation"] and "absent" not in {p["dominant_relation"], c["dominant_relation"]}
                modification_dimensions = []
                if relation_changed:
                    modification_dimensions.append("requirement_type")
                required_delta = float(c.get("required_share", 0)) - float(p.get("required_share", 0))
                if abs(required_delta) >= 0.20 and min(p["support_count"], c["support_count"]) >= 3:
                    modification_dimensions.append("required_frequency_ratio")
                window_ready = previous["jd_count"] >= 3 and current["jd_count"] >= 3 and previous["source_count"] >= 2 and current["source_count"] >= 2
                if not window_ready:
                    status, fallback_reason = "insufficient_evidence", "window_support_or_source_count_below_threshold"
                elif modification_dimensions and p["support_count"] >= 3 and c["support_count"] >= 3 and c["source_count"] >= 2:
                    status = "modified"
                elif p["support_count"] <= 1 and c["support_count"] >= 3 and c["source_count"] >= 2 and up >= 0.95:
                    status = "added"
                elif p["support_count"] >= 3 and c["support_count"] <= 1:
                    two_declines = bool(older and o["support_count"] >= 3 and o["posterior_share"] > p["posterior_share"] > c["posterior_share"])
                    if two_declines and down >= 0.95:
                        status = "deleted"
                    else:
                        status, fallback_reason = "insufficient_evidence", "deletion_requires_two_declining_windows"
                elif (up >= 0.95 or down >= 0.95) and max(p["support_count"], c["support_count"]) < 3:
                    status, fallback_reason = "insufficient_evidence", "skill_support_below_threshold"
                evidence = (c.get("evidence") or p.get("evidence") or [])[:3]
                # Publication requires continuity in the preceding window; a one-window
                # spike remains a statistical signal but is not a confirmed evolution.
                publication_status = "confirmed_evolution" if (
                    status in {"added", "modified"}
                    and p["support_count"] >= 2
                    and p["source_count"] >= 2
                ) else ("statistical_signal" if status in {"added", "modified"} else "not_applicable")
                events.append({
                    "event_id": f"{VERSION}:{job_name}:{previous['month']}:{current['month']}:{skill}",
                    "job_name": job_name, "skill": skill, "from_month": previous["month"], "to_month": current["month"],
                    "status": status, "previous_share": p["posterior_share"], "current_share": c["posterior_share"],
                    "delta_share": round(c["posterior_share"] - p["posterior_share"], 6),
                    "delta_threshold": round(threshold, 6), "probability_up": round(up, 6), "probability_down": round(down, 6),
                    "previous_support": p["support_count"], "current_support": c["support_count"],
                    "previous_sources": p["source_count"], "current_sources": c["source_count"],
                    "previous_relation": p["dominant_relation"], "current_relation": c["dominant_relation"],
                    "previous_required_share": p.get("required_share", 0), "current_required_share": c.get("required_share", 0),
                    "modification_dimensions": modification_dimensions,
                    "posterior_difference_ci95": [round(value, 6) for value in posterior["credible_interval_95"]],
                    "posterior_draws": posterior["draws"],
                    "source_mix_distance": round(mix_distance, 6),
                    "source_mix_warning": mix_distance >= 0.35,
                    "fallback_reason": fallback_reason, "evidence": evidence,
                    "publication_status": publication_status,
                    "algorithm_mode": "monthly_cohort_beta_monte_carlo", "algorithm_version": VERSION,
                })
    return events, by_job


def write_jsonl(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")


def main() -> int:
    versions = load_jsonl(VERSIONS)
    snapshots, excluded = build_snapshots(versions)
    events, by_job = classify_events(snapshots)
    lifecycle = build_lifecycle_trends(snapshots)
    write_jsonl(SNAPSHOTS, snapshots)
    write_jsonl(EVENTS, events)
    write_jsonl(LIFECYCLE, lifecycle)
    status_counts = Counter(event["status"] for event in events)
    raw_change_counts = Counter()
    for row in versions:
        if row.get("version_number", 0) <= 1:
            continue
        changes = row.get("observed_skill_changes") or {}
        raw_change_counts["added"] += len(changes.get("added") or [])
        raw_change_counts["removed"] += len(changes.get("removed") or [])
        raw_change_counts["relation_changed"] += len(changes.get("relation_changed") or [])
    formal_examples = sorted(
        ({"job_name": name, "window_count": len(rows), "months": [row["month"] for row in rows]} for name, rows in by_job.items() if len(rows) >= 3),
        key=lambda item: (-item["window_count"], item["job_name"]),
    )[:20]
    report = {
        "algorithm_version": VERSION, "input_versions": len(versions),
        "input_records": len({row.get("record_id") for row in versions}),
        "monthly_snapshots": len(snapshots), "change_events": len(events), "lifecycle_skills": len(lifecycle),
        "lifecycle_counts": dict(Counter(item["lifecycle"] for item in lifecycle)),
        "status_counts": dict(status_counts), "raw_version_change_counts": dict(raw_change_counts),
        "excluded_latest_records": dict(excluded),
        "jobs_with_three_or_more_windows": sum(len(rows) >= 3 for rows in by_job.values()),
        "formal_example_candidates": formal_examples,
        "supported_statuses": ["added", "deleted", "modified", "sustained", "insufficient_evidence"],
        "human_review_claimed": False,
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
