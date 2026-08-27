"""Reconstruct SCD2-like job versions from immutable collection batches."""
from __future__ import annotations
import json
from collections import defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
BATCHES = BASE / "data/.ops/collection/batches"
OUT = BASE / "data/gold/temporal/job_versions.jsonl"
REPORT = BASE / "data/reports/job_version_report.json"


def parse_list(value):
    if isinstance(value, list):
        return value
    if not value:
        return []
    try:
        parsed = json.loads(value)
        if isinstance(parsed, list):
            return parsed
    except (json.JSONDecodeError, TypeError):
        pass
    return [part.strip() for part in str(value).replace(",", ";").split(";") if part.strip()]


def skill_snapshot(payload):
    skills = []
    for item in parse_list(payload.get("skill_standard")):
        name = item.get("skill") if isinstance(item, dict) else item
        name = str(name or "").strip()
        if name and name not in skills:
            skills.append(name)
    relations = {name: "mentioned" for name in skills}
    evidence = {}
    for item in parse_list(payload.get("skill_evidence")):
        if not isinstance(item, dict):
            continue
        name = str(item.get("skill") or item.get("standard_skill") or "").strip()
        if not name:
            continue
        if name not in skills:
            skills.append(name)
        relations[name] = item.get("relation") or "mentioned"
        evidence[name] = {
            "snippet": item.get("snippet") or item.get("evidence_text") or "",
            "confidence": item.get("confidence"),
        }
    return sorted(skills), relations, evidence


def main() -> int:
    history = defaultdict(list)
    for path in sorted(BATCHES.glob("*.jsonl")):
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip(): continue
            try: item = json.loads(line)
            except json.JSONDecodeError: continue
            if item.get("data_type") != "job" or not item.get("record_id"): continue
            history[item["record_id"]].append(item)
    versions = []
    for record_id, items in history.items():
        items.sort(key=lambda x: x.get("crawled_at") or x.get("last_seen_at") or "")
        unique = []
        for item in items:
            if unique and unique[-1].get("content_hash") == item.get("content_hash"): continue
            unique.append(item)
        canonical_job_id = next(
            (
                (item.get("payload") or {}).get("canonical_job_id")
                for item in reversed(unique)
                if (item.get("payload") or {}).get("canonical_job_id")
            ),
            record_id,
        )
        previous_skills = []
        previous_relations = {}
        previous_payload = {}
        for index, item in enumerate(unique):
            payload = item.get("payload") or {}
            skills, relations, evidence = skill_snapshot(payload)
            valid_from = item.get("crawled_at") or item.get("last_seen_at") or ""
            valid_to = ""
            if index + 1 < len(unique): valid_to = unique[index + 1].get("crawled_at") or unique[index + 1].get("last_seen_at") or ""
            added = sorted(set(skills) - set(previous_skills)) if index else skills
            removed = sorted(set(previous_skills) - set(skills)) if index else []
            relation_changed = [
                {"skill": name, "from": previous_relations[name], "to": relations[name]}
                for name in sorted(set(previous_relations) & set(relations))
                if previous_relations[name] != relations[name]
            ]
            tracked_fields = ("job_title", "standard_job_name", "company", "location", "description", "requirements", "skill_standard")
            changed_fields = item.get("changed_fields") or [
                field for field in tracked_fields if index and previous_payload.get(field) != payload.get(field)
            ]
            versions.append({
                "version_id": f"{record_id}_v{index + 1}", "record_id": record_id,
                "canonical_job_id": canonical_job_id,
                "version_number": index + 1, "content_hash": item.get("content_hash") or "",
                "valid_from": valid_from, "valid_to": valid_to, "is_current": index == len(unique) - 1,
                "change_type": "created" if index == 0 else "updated",
                "changed_fields": changed_fields, "previous_version_id": f"{record_id}_v{index}" if index else "",
                "crawl_batch_id": item.get("crawl_batch_id") or "", "source_url": item.get("source_url") or "",
                "source": item.get("source_platform") or "", "source_type": item.get("source_type") or "",
                "source_published_at": item.get("source_published_at") or payload.get("publish_time") or "",
                "job_title": payload.get("job_title") or "", "standard_job_name": payload.get("standard_job_name") or "",
                "company": payload.get("company") or "", "location": payload.get("location") or "",
                "description": payload.get("description") or "", "requirements": payload.get("requirements") or "",
                "duplicate_score": payload.get("duplicate_score"), "evidence_score": payload.get("evidence_score"),
                "skill_snapshot": skills,
                "skill_relation_snapshot": relations, "skill_evidence_snapshot": evidence,
                "observed_skill_changes": {"added": added, "removed": removed, "relation_changed": relation_changed},
            })
            previous_skills, previous_relations, previous_payload = skills, relations, payload
    versions.sort(key=lambda x: (x["record_id"], x["version_number"]))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8", newline="\n") as handle:
        for row in versions: handle.write(json.dumps(row, ensure_ascii=False) + "\n")
    report = {"records_with_history": len(history), "total_versions": len(versions), "updated_records": sum(1 for x in history.values() if len({i.get('content_hash') for i in x}) > 1), "versions_with_skills": sum(bool(x["skill_snapshot"]) for x in versions), "versions_with_observed_skill_changes": sum(bool(x["observed_skill_changes"]["added"] or x["observed_skill_changes"]["removed"] or x["observed_skill_changes"]["relation_changed"]) for x in versions if x["version_number"] > 1), "all_versions_have_batch_id": all(x["crawl_batch_id"] for x in versions), "algorithm_version": "job_version_skill_snapshot_v1"}
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2)); return 0


if __name__ == "__main__": raise SystemExit(main())
