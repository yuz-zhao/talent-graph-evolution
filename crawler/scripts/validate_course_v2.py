"""Validate the formal, real-course recommendation dataset."""
from __future__ import annotations
import csv, json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
COURSES = BASE / "data/silver/learning/course_data.csv"
REPORT = BASE / "data/reports/course_v2_quality_report.json"
CORE_SKILLS = [
    "Python", "Java", "机器学习", "深度学习", "自然语言处理", "计算机视觉",
    "大语言模型", "多模态学习", "物联网", "信息安全", "数据挖掘", "Hive",
    "Docker", "Kubernetes",
]

def validate():
    with COURSES.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    skills = set()
    evidence_ok = True
    for row in rows:
        row_skills = json.loads(row.get("skills") or "[]")
        evidence = json.loads(row.get("skill_evidence") or "[]")
        skills.update(row_skills)
        evidence_skills = {item.get("skill") for item in evidence if item.get("evidence")}
        evidence_ok &= set(row_skills).issubset(evidence_skills)
    total = len(rows)
    checks = {
        "formal_course_count_positive": total > 0,
        "url_valid_rate_gte_95_percent": total > 0 and sum(r.get("url_status") == "verified_200" for r in rows) / total >= .95,
        "title_match_rate_100_percent": total > 0 and all(r.get("title_match") == "true" for r in rows),
        "active_only": all(r.get("availability_status") == "active" for r in rows),
        "no_template_generated_rows": all(r.get("source_type") != "template_generated" for r in rows),
        "all_skill_relations_have_evidence": evidence_ok,
        "core_skill_coverage_100_percent": all(skill in skills for skill in CORE_SKILLS),
        "stable_ids_present": all(r.get("course_id") and r.get("canonical_course_id") and r.get("version_id") for r in rows),
    }
    report = {
        "dataset": str(COURSES.relative_to(BASE.parent)).replace("\\", "/"),
        "formal_courses": total,
        "providers": len({r.get("provider") for r in rows}),
        "url_valid_rate": round(sum(r.get("url_status") == "verified_200" for r in rows) / max(1,total), 4),
        "title_match_rate": round(sum(r.get("title_match") == "true" for r in rows) / max(1,total), 4),
        "standard_skills_covered": len(skills),
        "core_skill_policy": "新一代信息技术岗位中可迁移、可教学的核心技术技能；不含项目管理、需求分析、企业品牌等通用或厂商标签",
        "core_skills": CORE_SKILLS,
        "missing_core_skills": [skill for skill in CORE_SKILLS if skill not in skills],
        "checks": checks,
        "passed": all(checks.values()),
    }
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return report

if __name__ == "__main__":
    raise SystemExit(0 if validate()["passed"] else 1)
