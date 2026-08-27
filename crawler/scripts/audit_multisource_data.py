"""Audit job sources, collection lag, noise and repost clusters.

Raw evidence is preserved. The audit output tells downstream algorithms which
record represents a repost cluster, so copied vacancies count once.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "crawler"))
from utils.collection_pipeline import CollectionStore  # noqa: E402

VERSION = "multisource_audit_v2"
DATA = ROOT / "crawler/data"
INPUT = DATA / "silver/jobs/jd_clean.csv"
AUDIT_OUT = DATA / "gold/quality/job_source_audit.jsonl"
CLUSTER_OUT = DATA / "gold/quality/job_repost_clusters.json"
REPORT_OUT = DATA / "reports/multisource_audit_report.json"

SOURCE_TYPES = {
    "智联招聘": "real_crawled", "猎聘": "real_crawled", "国家大学生就业服务平台": "public_platform",
    "Greenhouse": "official_ats", "Arbeitnow": "public_api", "Remotive": "public_api",
    "腾讯招聘官网": "official_career_api", "中国电信招聘官网": "official_career_page",
    "中国信通院招聘官网": "official_career_page",
}
SOURCE_KEYS = {
    "智联招聘": "zhaopin", "猎聘": "liepin", "国家大学生就业服务平台": "ncss",
    "Greenhouse": "enterprise-greenhouse", "Arbeitnow": "arbeitnow", "Remotive": "remotive",
    "腾讯招聘官网": "tencent-careers", "中国电信招聘官网": "china-telecom-careers",
    "中国信通院招聘官网": "caict-careers",
}
BASE_RELIABILITY = {
    "official_career_api": .95, "official_career_page": .93, "official_ats": .92,
    "public_platform": .84, "public_api": .80, "real_crawled": .76, "processed_backfill": .65,
}


def normalize_text(value: str) -> str:
    return re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "", str(value or "").casefold())


def canonical_url(value: str) -> str:
    try:
        parts = urlsplit(str(value or "").strip())
        query = urlencode(sorted((k, v) for k, v in parse_qsl(parts.query) if not k.lower().startswith("utm_")))
        return urlunsplit((parts.scheme.lower(), parts.netloc.lower().removeprefix("www."), parts.path.rstrip("/"), query, ""))
    except ValueError:
        return str(value or "").strip()


def parse_time(value: str) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        stamp = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return stamp.replace(tzinfo=stamp.tzinfo or timezone.utc).astimezone(timezone.utc)
    except ValueError:
        return None


def shingles(value: str, size: int = 5) -> set[str]:
    text = normalize_text(value)
    return {text[i:i + size] for i in range(max(0, len(text) - size + 1))} or ({text} if text else set())


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / max(1, len(left | right))


def record_key(row: dict) -> str:
    raw = row.get("source_job_id") or canonical_url(row.get("source_url")) or "|".join(
        str(row.get(k) or "") for k in ("source_name", "company", "job_title", "publish_time")
    )
    return str(raw)


def content(row: dict) -> str:
    return " ".join(str(row.get(k) or "") for k in ("job_title", "description", "requirements"))


def similarity(left: dict, right: dict) -> tuple[float, str]:
    a, b = content(left), content(right)
    na, nb = normalize_text(a), normalize_text(b)
    if canonical_url(left.get("source_url")) and canonical_url(left.get("source_url")) == canonical_url(right.get("source_url")):
        return 1.0, "exact_url"
    if na and hashlib.sha256(na.encode()).digest() == hashlib.sha256(nb.encode()).digest():
        return 1.0, "exact_content"
    five_gram = jaccard(shingles(a), shingles(b))
    sequence = SequenceMatcher(None, na[:5000], nb[:5000], autojunk=False).ratio()
    score = round(.72 * five_gram + .28 * sequence, 4)
    return score, "near_duplicate_5gram" if score >= .82 else "rewritten_candidate"


def find_clusters(rows: list[dict]) -> tuple[list[list[int]], list[dict]]:
    parent = list(range(len(rows)))
    def root(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]; i = parent[i]
        return i
    def union(a, b):
        ra, rb = root(a), root(b)
        if ra != rb: parent[rb] = ra
    blocks = defaultdict(list)
    for index, row in enumerate(rows):
        company = normalize_text(row.get("company"))
        title = normalize_text(row.get("standard_job_name") or row.get("job_title"))[:12]
        blocks[(company, title)].append(index)
    pairs = []
    for indexes in blocks.values():
        if not indexes or len(indexes) > 120: continue
        for offset, left_index in enumerate(indexes):
            for right_index in indexes[offset + 1:]:
                left, right = rows[left_index], rows[right_index]
                score, method = similarity(left, right)
                same_source_id = bool(left.get("source_job_id") and left.get("source_job_id") == right.get("source_job_id"))
                if same_source_id or score >= .82:
                    union(left_index, right_index)
                    pairs.append({"left": record_key(left), "right": record_key(right), "score": score, "method": "exact_source_id" if same_source_id else method})
    groups = defaultdict(list)
    for index in range(len(rows)): groups[root(index)].append(index)
    return list(groups.values()), sorted(pairs, key=lambda x: -x["score"])


def completeness(row: dict) -> float:
    fields = ("source_url", "job_title", "company", "description", "requirements", "skill_standard")
    return sum(bool(str(row.get(k) or "").strip()) for k in fields) / len(fields)


def noise_reasons(row: dict) -> list[str]:
    reasons = []
    title, body = str(row.get("job_title") or "").strip(), content(row)
    if len(title) < 2: reasons.append("missing_or_short_title")
    if len(normalize_text(body)) < 80: reasons.append("insufficient_job_text")
    if not canonical_url(row.get("source_url")).startswith(("http://", "https://")): reasons.append("invalid_source_url")
    if any(token == title for token in ("收藏", "投递", "沟通", "查看更多", "职位详情")): reasons.append("ui_noise_title")
    return reasons


def choose_representative(indexes: list[int], rows: list[dict]) -> int:
    return max(indexes, key=lambda i: (BASE_RELIABILITY.get(SOURCE_TYPES.get(rows[i].get("source_name"), "processed_backfill"), .65), completeness(rows[i]), bool(parse_time(rows[i].get("publish_time")))))


def main() -> int:
    with INPUT.open("r", encoding="utf-8-sig", newline="") as handle: rows = list(csv.DictReader(handle))
    grouped = defaultdict(list)
    for row in rows: grouped[row.get("source_name") or "未知来源"].append(row)
    store = CollectionStore(DATA)
    batch_reports = [store.ingest(SOURCE_KEYS.get(source, source), "job", items, SOURCE_TYPES.get(source, "processed_backfill"), complete_snapshot=False).to_dict() for source, items in sorted(grouped.items())]
    clusters, pairs = find_clusters(rows)
    cluster_by_index, representative_by_index = {}, {}
    cluster_payload = []
    for indexes in clusters:
        representative = choose_representative(indexes, rows)
        cluster_id = "RCL_" + hashlib.sha256("|".join(sorted(record_key(rows[i]) for i in indexes)).encode()).hexdigest()[:20]
        for index in indexes: cluster_by_index[index], representative_by_index[index] = cluster_id, representative
        if len(indexes) > 1:
            cluster_payload.append({"cluster_id": cluster_id, "size": len(indexes), "representative_record_id": record_key(rows[representative]), "members": [record_key(rows[i]) for i in indexes]})
    source_duplicate = Counter()
    for index in range(len(rows)):
        if representative_by_index[index] != index: source_duplicate[rows[index].get("source_name") or "未知来源"] += 1
    audited, source_quality = [], {}
    for source, items in sorted(grouped.items()):
        duplicate_rate = source_duplicate[source] / max(1, len(items))
        publish_rate = sum(bool(parse_time(x.get("publish_time"))) for x in items) / max(1, len(items))
        complete = sum(completeness(x) for x in items) / max(1, len(items))
        source_type = SOURCE_TYPES.get(source, "processed_backfill")
        weight = round(BASE_RELIABILITY.get(source_type, .65) * (.45 + .25 * complete + .15 * publish_rate + .15 * (1 - duplicate_rate)), 4)
        source_quality[source] = {"count": len(items), "source_type": source_type, "field_completeness": round(complete, 4), "published_at_coverage": round(publish_rate, 4), "duplicate_rate": round(duplicate_rate, 4), "source_weight": weight, "weight_version": VERSION}
    now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    for index, row in enumerate(rows):
        published, first_seen = parse_time(row.get("publish_time")), parse_time(row.get("crawl_time"))
        time_basis = "source_published_at" if published else "first_seen"
        effective = published or first_seen
        lag = max(0, (first_seen - published).days) if published and first_seen else None
        reasons = noise_reasons(row)
        representative = representative_by_index[index] == index
        audited.append({
            "record_id": record_key(row), "canonical_job_id": row.get("canonical_job_id") or "", "source_name": row.get("source_name") or "",
            "canonical_source_url": canonical_url(row.get("source_url")), "normalized_content_hash": hashlib.sha256(normalize_text(content(row)).encode()).hexdigest(),
            "repost_cluster_id": cluster_by_index[index], "is_independent_representative": representative,
            "duplicate_probability": 0.0 if representative and len(clusters) else (1.0 if not representative else 0.0),
            "source_published_at": published.isoformat() if published else "", "first_seen_at": first_seen.isoformat() if first_seen else "",
            "effective_time": effective.isoformat() if effective else "", "time_basis": time_basis if effective else "unknown", "collection_lag_days": lag,
            "noise_score": round(min(1.0, len(reasons) / 3), 4), "quarantine_reasons": reasons,
            "audit_status": "quarantine" if reasons else ("repost_suppressed" if not representative else "accepted"),
            "source_weight": source_quality[row.get("source_name") or "未知来源"]["source_weight"], "algorithm_version": VERSION, "audited_at": now,
        })
    AUDIT_OUT.parent.mkdir(parents=True, exist_ok=True)
    AUDIT_OUT.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in audited), encoding="utf-8")
    CLUSTER_OUT.write_text(json.dumps({"algorithm_version": VERSION, "clusters": cluster_payload}, ensure_ascii=False, indent=2), encoding="utf-8")
    lags = [x["collection_lag_days"] for x in audited if x["collection_lag_days"] is not None]
    report = {"schema_version": "2.0", "algorithm_version": VERSION, "total_jobs": len(rows), "source_count": len(grouped), "source_quality": source_quality,
              "repost_cluster_count": len(cluster_payload), "repost_record_count": sum(x["size"] - 1 for x in cluster_payload), "duplicate_pair_count": len(pairs),
              "duplicate_pairs": pairs[:500], "time_basis_counts": dict(Counter(x["time_basis"] for x in audited)),
              "collection_lag_days": {"observations": len(lags), "mean": round(sum(lags) / max(1, len(lags)), 2), "max": max(lags) if lags else None},
              "quarantine_count": sum(x["audit_status"] == "quarantine" for x in audited), "batch_reports": batch_reports,
              "notes": ["Raw records are preserved.", "Each repost cluster contributes one independent market observation.", "Rewritten duplicate detection currently uses deterministic 5-gram and sequence similarity; no embedding claim is made."],
              "outputs": {"record_audit": str(AUDIT_OUT.relative_to(ROOT)), "clusters": str(CLUSTER_OUT.relative_to(ROOT))}}
    REPORT_OUT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("total_jobs", "source_count", "repost_cluster_count", "repost_record_count", "quarantine_count", "time_basis_counts")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__": raise SystemExit(main())
