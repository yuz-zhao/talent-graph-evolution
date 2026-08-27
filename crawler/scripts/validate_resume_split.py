import csv, json, re
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PUBLIC = BASE / "data/silver/profiles/profiles_github_public.csv"
SYNTHETIC = BASE / "data/clean/resumes_synthetic_demo.csv"
EVALUATION = BASE / "data/clean/resumes_anonymized_evaluation.jsonl"
REPORT = BASE / "data/reports/resume_split_quality_report.json"
with PUBLIC.open("r", encoding="utf-8-sig") as f: public = list(csv.DictReader(f))
with SYNTHETIC.open("r", encoding="utf-8-sig") as f: synthetic = list(csv.DictReader(f))
evaluation = [json.loads(line) for line in EVALUATION.read_text(encoding="utf-8").splitlines() if line.strip()]

evidence_ok = True
for row in public:
    skills, evidence = json.loads(row["skills"]), json.loads(row["skill_evidence"])
    supported = {item.get("skill") for item in evidence if item.get("repository_url") and item.get("repo_id")}
    if not set(skills).issubset(supported): evidence_ok = False
evaluation_ok = bool(evaluation) and all(
    row.get("authorization_status") == "granted" and row.get("anonymization_status") == "completed"
    and row.get("manual_gold_label") and row.get("human_reviewer")
    and re.fullmatch(r"[\u4e00-\u9fff]{2,4}", row.get("display_name", ""))
    and not row.get("is_synthetic") for row in evaluation
)
checks = {
    "public_random_supplemented_fields_zero": all(row.get("random_supplemented_fields") == "0" for row in public),
    "public_profile_skills_trace_to_repository": evidence_ok,
    "synthetic_demo_excluded_from_statistics": all(row.get("statistics_scope") == "excluded" for row in synthetic),
    "synthetic_demo_excluded_from_accuracy": all(row.get("accuracy_evaluation_scope") == "excluded" for row in synthetic),
    "synthetic_names_are_chinese_pseudonyms": all(re.fullmatch(r"[\u4e00-\u9fff]{2,4}", row.get("display_name", "")) for row in synthetic),
    "evaluation_resumes_authorized_anonymized_and_human_labeled": evaluation_ok,
}
report = {"public_profiles": len(public), "synthetic_demo": len(synthetic), "evaluation_resumes": len(evaluation),
          "checks": checks, "passed": all(checks.values()),
          "blocking_reason": "尚未导入已授权并具人工金标的真实评测简历" if not evaluation else ""}
REPORT.parent.mkdir(parents=True, exist_ok=True); REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
print(json.dumps(report, ensure_ascii=False, indent=2)); raise SystemExit(0 if report["passed"] else 2)
