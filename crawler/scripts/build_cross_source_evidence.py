"""Build evidence-level R03 cross-source validation from current graph exports.

The output is deterministic and only uses relationships with text and source URL.
Duplicate/reposted evidence is collapsed before scoring.
"""
from __future__ import annotations

import csv
import hashlib
import json
import math
import re
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[2]
IMPORT = ROOT / "knowledge_graph" / "import"
DATA = ROOT / "crawler" / "data"
CONFIG = ROOT / "crawler" / "config" / "evidence_rules.json"
EVIDENCE_OUT = DATA / "gold" / "evidence" / "skill_evidence.jsonl"
RESULT_OUT = DATA / "gold" / "evidence" / "skill_validation_results.json"
REPORT_OUT = DATA / "reports" / "cross_source_validation_report.json"

RELATIONS = {
    "job": "rel_job_requires_skill.csv",
    "project": "rel_tech_project_uses_tech.csv",
    "paper": "rel_paper_mentions_tech.csv",
    "blog": "rel_blog_mentions_tech.csv",
    "course": "rel_course_teaches_skill.csv",
    "certificate": "rel_certificate_certifies_skill.csv",
}


def read_csv(name: str) -> list[dict]:
    path = IMPORT / name
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def digest(*parts: str, length: int = 24) -> str:
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:length]


def domain(url: str) -> str:
    try:
        return urlsplit(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""


def parse_time(value: str) -> datetime | None:
    value = str(value or "").strip()
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)
    except ValueError:
        return None


def freshness(value: str, observed_at: datetime, half_life: int) -> float:
    stamp = parse_time(value)
    if not stamp:
        return 0.75
    days = max(0, (observed_at - stamp).days)
    return round(max(0.35, math.exp(-math.log(2) * days / max(half_life, 1))), 4)


def source_platform(group: str, url: str, job_source: str = "") -> str:
    if group == "job" and job_source:
        return job_source
    host = domain(url)
    if host:
        return host
    return group


def source_type(group: str, platform: str) -> str:
    official_tokens = ("careers", "career", "campus", "caict", "chinatelecom", "tencent")
    if group == "job" and any(token in platform.lower() for token in official_tokens):
        return "official_company"
    return group


def aggregate(scores: list[float]) -> float:
    remaining = 1.0
    for score in scores:
        remaining *= 1.0 - max(0.0, min(0.99, score))
    return round(1.0 - remaining, 4)


def main() -> int:
    rules = json.loads(CONFIG.read_text(encoding="utf-8"))
    observed_at = datetime.now(timezone.utc)
    skills = {row["skill_id:ID"]: row for row in read_csv("nodes_skill.csv")}
    jobs = {row["job_id:ID"]: row for row in read_csv("nodes_job.csv")}
    job_cluster = {job_id: clean_text(row.get("standard_name") or row.get("title") or "未标准化岗位") for job_id, row in jobs.items()}

    evidence: list[dict] = []
    rejected = defaultdict(int)
    for group, filename in RELATIONS.items():
        for row_index, row in enumerate(read_csv(filename), 2):
            skill_id = clean_text(row.get(":END_ID"))
            entity_id = clean_text(row.get(":START_ID"))
            text = clean_text(row.get("evidence_text"))
            url = clean_text(row.get("source_url"))
            try:
                relation_confidence = float(row.get("confidence:float") or 0)
            except ValueError:
                relation_confidence = 0.0
            if skill_id not in skills:
                rejected["unknown_skill_id"] += 1
                continue
            if not text:
                rejected["missing_evidence_text"] += 1
                continue
            if not url:
                rejected["missing_source_url"] += 1
                continue
            if relation_confidence < rules["thresholds"]["minimum_relation_confidence"]:
                rejected["low_relation_confidence"] += 1
                continue

            job_source = jobs.get(entity_id, {}).get("source_name", "")
            platform = source_platform(group, url, job_source)
            source_domain = domain(url)
            kind = source_type(group, platform)
            reliability = float(rules["source_reliability"].get(kind, rules["source_reliability"].get(group, 0.7)))
            skill_name = skills[skill_id].get("name", "")
            relevance = 1.0 if skill_name.casefold() in text.casefold() else 0.85
            fresh = freshness(row.get("observed_at", ""), observed_at, int(rules["freshness_half_life_days"]))
            score = round(relation_confidence * reliability * relevance * fresh, 4)
            normalized_text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", text.casefold())[:800]
            independent_group_id = digest(group, skill_id, normalized_text)
            batch_id = clean_text(row.get("batch_id") or row.get("collection_batch_id") or row.get("ingest_batch_id"))
            evidence_id = "EVD_" + digest(group, entity_id, skill_id, url, text)
            evidence.append({
                "evidence_id": evidence_id,
                "skill_id": skill_id,
                "skill_name": skill_name,
                "claim_type": {"job":"job_requirement","project":"project_usage","paper":"research_attention","blog":"industry_practice","course":"course_teaching","certificate":"certification_scope"}[group],
                "source_group": group,
                "source_type": kind,
                "source_platform": platform,
                "source_domain": source_domain,
                "source_entity_id": entity_id,
                "source_url": url,
                "evidence_text": text[:1000],
                "observed_at": row.get("observed_at", ""),
                "time_window": row.get("time_window", ""),
                "extraction_method": "graph_relation_evidence",
                "extraction_confidence": relation_confidence,
                "source_reliability": reliability,
                "relevance": relevance,
                "freshness": fresh,
                "evidence_score": score,
                "independent_group_id": independent_group_id,
                "batch_id": batch_id,
                "is_independent_representative": False,
                "graph_relation_file": filename,
                "graph_relation_row": row_index,
                "job_cluster": job_cluster.get(entity_id, "") if group == "job" else "",
                "algorithm_version": rules["version"],
            })

    # Collapse identical evidence text within a source group and skill; retain best-scoring representative.
    representatives: dict[tuple[str, str, str], dict] = {}
    for item in evidence:
        key = (item["skill_id"], item["source_group"], item["independent_group_id"])
        if key not in representatives or item["evidence_score"] > representatives[key]["evidence_score"]:
            representatives[key] = item
    representative_ids = {item["evidence_id"] for item in representatives.values()}
    for item in evidence:
        item["is_independent_representative"] = item["evidence_id"] in representative_ids

    by_skill: dict[str, list[dict]] = defaultdict(list)
    for item in representatives.values():
        by_skill[item["skill_id"]].append(item)

    results = []
    thresholds = rules["thresholds"]
    max_per_group = int(rules["maximum_evidence_per_skill_group"])
    for skill_id, items in by_skill.items():
        grouped: dict[str, list[dict]] = defaultdict(list)
        for item in items:
            grouped[item["source_group"]].append(item)
        group_scores = {}
        group_counts = {}
        for group in RELATIONS:
            selected = sorted(grouped[group], key=lambda x: x["evidence_score"], reverse=True)[:max_per_group]
            group_scores[group] = aggregate([x["evidence_score"] for x in selected])
            group_counts[group] = len(selected)
        overall = round(sum(float(rules["weights"][group]) * group_scores[group] for group in rules["weights"]), 4)
        external_groups = sum(1 for group in ("project", "paper", "blog", "course", "certificate") if group_counts[group] > 0)
        has_job_claim = group_counts["job"] > 0
        if has_job_claim and external_groups >= int(thresholds["minimum_independent_external_groups"]) and overall >= float(thresholds["strong"]):
            level = "strong"
        elif has_job_claim and (external_groups >= 1 or overall >= float(thresholds["moderate"])):
            level = "moderate"
        elif has_job_claim:
            level = "insufficient"
        else:
            level = "external_only"
        top = sorted(items, key=lambda x: x["evidence_score"], reverse=True)[:12]
        skill_row = skills[skill_id]
        results.append({
            "skill_id": skill_id,
            "skill_name": skill_row.get("name", ""),
            "category": skill_row.get("category", ""),
            "validation_level": level,
            "confidence": overall,
            "independent_external_groups": external_groups,
            "group_scores": group_scores,
            "group_counts": group_counts,
            "independent_evidence_count": len(items),
            "raw_evidence_count": sum(1 for x in evidence if x["skill_id"] == skill_id),
            "duplicate_evidence_count": sum(1 for x in evidence if x["skill_id"] == skill_id and not x["is_independent_representative"]),
            "representative_evidence": [{k: x.get(k) for k in ("evidence_id","source_group","source_platform","source_domain","source_url","evidence_text","observed_at","time_window","batch_id","evidence_score","independent_group_id","is_independent_representative","graph_relation_file","graph_relation_row")} for x in top],
            "algorithm_version": rules["version"],
            "calculated_at": observed_at.replace(microsecond=0).isoformat(),
        })

    results.sort(key=lambda x: (-x["group_counts"]["job"], -x["confidence"], x["skill_name"]))

    # Job cluster summary is calculated from job evidence and the same formal validation result.
    result_map = {x["skill_id"]: x for x in results}
    cluster_jobs: dict[str, set[str]] = defaultdict(set)
    cluster_skills: dict[str, set[str]] = defaultdict(set)
    for item in representatives.values():
        if item["source_group"] != "job" or not item["job_cluster"]:
            continue
        cluster_jobs[item["job_cluster"]].add(item["source_entity_id"])
        cluster_skills[item["job_cluster"]].add(item["skill_id"])
    clusters = []
    for name, skill_ids in cluster_skills.items():
        strong = [sid for sid in skill_ids if result_map.get(sid, {}).get("validation_level") == "strong"]
        insufficient = [sid for sid in skill_ids if result_map.get(sid, {}).get("validation_level") == "insufficient"]
        clusters.append({
            "name": name,
            "jobCount": len(cluster_jobs[name]),
            "totalSkills": len(skill_ids),
            "verifiedCount": len(strong),
            "verificationRate": round(100 * len(strong) / max(len(skill_ids), 1), 1),
            "insufficientCount": len(insufficient),
            "topInsufficient": [result_map[sid]["skill_name"] for sid in insufficient[:5]],
        })
    clusters.sort(key=lambda x: (-x["jobCount"], x["name"]))

    counts = {level: sum(1 for x in results if x["validation_level"] == level) for level in ("strong", "moderate", "insufficient", "external_only")}
    payload = {
        "schema_version": "1.0.0",
        "algorithm_version": rules["version"],
        "calculated_at": observed_at.replace(microsecond=0).isoformat(),
        "scope": "evidence_constrained_cross_source_validation",
        "counts": counts,
        "source_breakdown": {group: len({item["skill_id"] for item in representatives.values() if item["source_group"] == group}) for group in RELATIONS},
        "skills": results,
        "clusters": clusters,
    }
    EVIDENCE_OUT.parent.mkdir(parents=True, exist_ok=True)
    with EVIDENCE_OUT.open("w", encoding="utf-8", newline="\n") as handle:
        for item in evidence:
            handle.write(json.dumps(item, ensure_ascii=False) + "\n")
    RESULT_OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "algorithm_version": rules["version"],
        "raw_relationships": len(evidence) + sum(rejected.values()),
        "accepted_evidence": len(evidence),
        "independent_evidence": len(representatives),
        "duplicate_evidence": len(evidence) - len(representatives),
        "skills_with_job_claim": sum(1 for x in results if x["group_counts"]["job"] > 0),
        "validation_counts": counts,
        "rejected_reasons": dict(rejected),
        "all_evidence_has_text": all(x["evidence_text"] for x in evidence),
        "all_evidence_has_url": all(x["source_url"] for x in evidence),
        "all_results_versioned": all(x["algorithm_version"] == rules["version"] for x in results),
        "passed": bool(evidence) and all(x["evidence_text"] and x["source_url"] for x in evidence),
    }
    REPORT_OUT.parent.mkdir(parents=True, exist_ok=True)
    REPORT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
