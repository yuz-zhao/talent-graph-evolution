"""导入已授权评测简历：只输出脱敏文本、中文化名和人工金标。"""
from __future__ import annotations
import argparse, json, re
from datetime import datetime, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
OUTPUT = BASE / "data/clean/resumes_anonymized_evaluation.jsonl"
ALIASES = ["张三", "李四", "王五", "赵六", "陈晨", "刘洋", "杨帆", "周宁", "吴桐", "徐静", "孙悦", "胡明", "朱琳", "高远", "林涛", "何雨", "郭凯", "马欣", "罗杰", "梁雪"]
PII_PATTERNS = [
    (re.compile(r"1[3-9]\d{9}"), "[手机号已脱敏]"),
    (re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"), "[邮箱已脱敏]"),
    (re.compile(r"\b\d{17}[\dXx]\b"), "[身份证号已脱敏]"),
]

def redact(text: str) -> str:
    value = str(text or "")
    for pattern, replacement in PII_PATTERNS: value = pattern.sub(replacement, value)
    return value

def main():
    parser = argparse.ArgumentParser(); parser.add_argument("input", type=Path); args = parser.parse_args()
    incoming = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    existing = [json.loads(line) for line in OUTPUT.read_text(encoding="utf-8").splitlines() if line.strip()] if OUTPUT.exists() else []
    for index, item in enumerate(incoming, start=len(existing)):
        required = ["authorization_record_id", "authorization_granted_at", "retention_until", "resume_text", "manual_gold_label", "human_reviewer"]
        missing = [field for field in required if not item.get(field)]
        if missing: raise ValueError(f"第 {index+1} 条缺少必填字段: {missing}")
        if item.get("authorization_status") != "granted": raise ValueError("authorization_status 必须为 granted")
        gold = item["manual_gold_label"]
        if not isinstance(gold, dict) or not gold.get("skills") or not gold.get("target_job_ids"):
            raise ValueError("manual_gold_label 必须包含人工确认的 skills 和 target_job_ids")
        existing.append({
            "evaluation_id": f"eval_{index+1:04d}", "display_name": ALIASES[index % len(ALIASES)], "is_pseudonym": True,
            "anonymized_resume_text": redact(item["resume_text"]), "manual_gold_label": gold,
            "human_reviewer": item["human_reviewer"], "gold_reviewed_at": item.get("gold_reviewed_at") or "",
            "authorization_status": "granted", "authorization_record_id": item["authorization_record_id"],
            "authorization_granted_at": item["authorization_granted_at"], "anonymization_status": "completed",
            "anonymization_method": "direct_identifier_redaction_and_chinese_pseudonym",
            "anonymized_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "data_usage": "matching_accuracy_evaluation_only", "retention_until": item["retention_until"],
            "statistics_scope": "excluded", "is_synthetic": False,
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        for row in existing: handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    print(json.dumps({"evaluation_records": len(existing), "new": len(incoming)}, ensure_ascii=False))

if __name__ == "__main__": main()
