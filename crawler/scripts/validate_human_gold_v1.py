"""Validate the frozen TalentGraph human-gold v1.1 dataset."""
from __future__ import annotations

import hashlib
import json
from collections import Counter
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
GOLD = BASE / "data" / "gold" / "human" / "v1.1"
REPORT_JSON = BASE / "data" / "reports" / "human_gold_v1_1_quality_report.json"
REPORT_MD = BASE / "data" / "reports" / "human_gold_v1_1_quality_report.md"
ALLOWED_STATES = {"demonstrated", "claimed", "learning", "target_only"}
LEVELS = {0: "不匹配", 1: "弱匹配", 2: "基本匹配", 3: "高度匹配"}


def load_jsonl(name: str) -> list[dict]:
    path = GOLD / name
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def duplicates(values) -> list[str]:
    return sorted(key for key, count in Counter(values).items() if count > 1)


def main() -> int:
    jd = load_jsonl("gold_jd_v1.1.jsonl")
    resumes = load_jsonl("gold_resume_v1.1.jsonl")
    matches = load_jsonl("gold_match_v1.1.jsonl")
    inputs = load_jsonl("match_inputs_v1.1.jsonl")
    manifest = json.loads((GOLD / "gold_split_manifest_v1.1.json").read_text(encoding="utf-8"))
    errors: list[str] = []
    warnings: list[str] = []

    expected = {"jd": 100, "resume": 30, "match": 400, "match_input": 400}
    actual = {"jd": len(jd), "resume": len(resumes), "match": len(matches), "match_input": len(inputs)}
    for key, value in expected.items():
        if actual[key] != value:
            errors.append(f"{key} count expected {value}, got {actual[key]}")

    for label, rows, key in (("jd", jd, "sample_id"), ("resume", resumes, "resume_id"), ("match", matches, "pair_id")):
        dup = duplicates(row.get(key) for row in rows)
        if dup:
            errors.append(f"{label} duplicate IDs: {dup[:10]}")

    jd_ids = {row["sample_id"] for row in jd}
    resume_ids = {row["resume_id"] for row in resumes}
    pair_ids = {row["pair_id"] for row in matches}
    test_resume_ids = {row["resume_id"] for row in resumes if row["split"] == "test"}
    for row in matches:
        if row["jd_sample_id"] not in jd_ids:
            errors.append(f"{row['pair_id']} references unknown JD {row['jd_sample_id']}")
        if row["resume_id"] not in resume_ids:
            errors.append(f"{row['pair_id']} references unknown resume {row['resume_id']}")
        if row["resume_id"] not in test_resume_ids:
            errors.append(f"{row['pair_id']} uses non-test resume {row['resume_id']}")
        relevance = row.get("relevance")
        if relevance not in LEVELS:
            errors.append(f"{row['pair_id']} invalid relevance {relevance}")
        elif row.get("level") != LEVELS[relevance]:
            errors.append(f"{row['pair_id']} level/relevance mismatch")

    if {row["pair_id"] for row in inputs} != pair_ids:
        errors.append("match_inputs pair IDs differ from gold_match pair IDs")
    forbidden = {"relevance", "level", "matched_skills", "missing_skills", "reason", "candidate_design_stratum"}
    leaking = sorted({key for row in inputs for key in row if key in forbidden})
    if leaking:
        errors.append(f"match_inputs contains label leakage fields: {leaking}")

    for row in jd:
        if row.get("gold_version") != "gold_v1.1" or row.get("annotation", {}).get("status") not in {"已人工确认", "已复核确认", "已复核修订"}:
            errors.append(f"{row['sample_id']} is not frozen human gold")
        if not row.get("evidence_text"):
            errors.append(f"{row['sample_id']} missing JD evidence")
    for row in resumes:
        states = row.get("skill_states", {})
        invalid = sorted(set(states.values()) - ALLOWED_STATES)
        if invalid:
            errors.append(f"{row['resume_id']} invalid skill states: {invalid}")
        if set(states) != set(row.get("skills", [])):
            errors.append(f"{row['resume_id']} skill_states keys do not match skills")
        pdf = BASE.parent / row.get("pdf_path", "")
        if not pdf.is_file():
            errors.append(f"{row['resume_id']} PDF does not exist: {row.get('pdf_path')}")

    split_counts = {
        "jd": Counter(row["split"] for row in jd),
        "resume": Counter(row["split"] for row in resumes),
    }
    if split_counts["jd"] != Counter({"development": 20, "validation": 20, "test": 60}):
        errors.append(f"JD split counts invalid: {dict(split_counts['jd'])}")
    if split_counts["resume"] != Counter({"development": 5, "validation": 5, "test": 20}):
        errors.append(f"resume split counts invalid: {dict(split_counts['resume'])}")
    candidates = Counter(row["resume_id"] for row in matches)
    if set(candidates.values()) != {20} or len(candidates) != 20:
        errors.append(f"expected 20 test resumes x 20 candidates, got {dict(candidates)}")

    label_distribution = dict(sorted(Counter(row["relevance"] for row in matches).items()))
    if max(label_distribution.values()) - min(label_distribution.values()) <= 2:
        warnings.append("Matching labels remain nearly perfectly balanced; document candidate construction and arbitration to avoid design-label leakage concerns.")
    empty_required = sum(not row["required_skills"] for row in jd)
    if empty_required:
        warnings.append(f"{empty_required} JD records have no required skills; treat an empty list as intentional, not missing data.")

    evidence_files = [p for p in (GOLD / "evidence").rglob("*") if p.is_file()]
    hashes = {str(p.relative_to(GOLD)).replace("\\", "/"): hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(evidence_files)}
    report = {
        "schema_version": "1.1.0", "gold_version": "gold_v1.1", "status": "pass" if not errors else "fail",
        "formal_gold": True, "counts": actual, "split_counts": {k: dict(v) for k, v in split_counts.items()},
        "match_label_distribution": label_distribution, "candidate_count_per_resume": dict(sorted(candidates.items())),
        "leakage_check": {"match_inputs_label_fields": leaking, "passed": not leaking},
        "evidence": {"file_count": len(evidence_files), "sha256": hashes},
        "manifest_frozen": bool(manifest.get("frozen")), "errors": errors, "warnings": warnings,
    }
    REPORT_JSON.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    lines = ["# TalentGraph 人工金标 V1.0 质量报告", "", f"- 状态：**{report['status'].upper()}**", f"- 数量：JD {len(jd)}、简历 {len(resumes)}、匹配 {len(matches)}", f"- 匹配分布：{label_distribution}", f"- 证据文件：{len(evidence_files)}", f"- 泄漏字段检查：{'通过' if not leaking else '失败'}", "", "## 错误", "", *([f"- {x}" for x in errors] or ["- 无"]), "", "## 警告", "", *([f"- {x}" for x in warnings] or ["- 无"])]
    REPORT_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
