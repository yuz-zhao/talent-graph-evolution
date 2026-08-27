"""
评估数据人工审核 — 导出最终审核版
=====================================
只有 check_review_data.py 全部 PASS 后才允许导出。
导出文件以 _reviewed 后缀命名，不覆盖原始 meta JSON。

用法:
    python scripts/export_reviewed_assessment.py
    python main.py --export-reviewed-assessment
"""

import csv
import json
import os
import sys
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

REVIEW_DIR = os.path.join(BASE, "data", "review")
META_DIR = os.path.join(BASE, "data", "meta")


def read_csv(filename):
    path = os.path.join(REVIEW_DIR, filename)
    if not os.path.exists(path):
        return None, f"文件不存在: {path}"
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f)), None


def check_all_passed():
    """
    快速检查是否所有记录都 reviewed 且无问题。
    不依赖 check_review_data.py 的完整输出，
    做独立校验。
    """
    issues = []

    # 检查文件存在
    required = {
        "gold_jd_review.csv": ["final_required_skills", "final_bonus_skills", "final_difficulty_level"],
        "gold_resume_review.csv": ["final_skills", "final_projects", "final_target_jobs"],
        "match_label_review.csv": ["final_match_level", "final_matched_skills", "final_missing_skills", "final_reason"],
        "negative_samples_review.csv": ["final_type", "final_reason"],
    }

    for fname, final_fields in required.items():
        rows, err = read_csv(fname)
        if err:
            return False, [err]
        if rows is None:
            return False, [f"{fname} 不可读"]

        for i, row in enumerate(rows):
            sid = row.get("sample_id", f"row_{i}")

            # 检查 review_status
            if row.get("review_status", "").strip() != "reviewed":
                issues.append(f"[{sid}] review_status = {row.get('review_status', '')}")
                continue

            # 检查必填字段
            for field in ["reviewer", "review_time", "manual_reason"]:
                if not row.get(field, "").strip():
                    issues.append(f"[{sid}] {field} 为空")

            for ff in final_fields:
                if not row.get(ff, "").strip():
                    issues.append(f"[{sid}] {ff} 为空")

            # 检查技能映射
            mapping = row.get("skill_mapping_status", "")
            if mapping and mapping != "all_mapped":
                issues.append(f"[{sid}] skill_mapping_status = {mapping}")

    if issues:
        return False, issues
    return True, []


# ================================================================
# 导出函数
# ================================================================
def export_gold_jd():
    rows, _ = read_csv("gold_jd_review.csv")
    reviewed = []
    for r in rows:
        if r.get("review_status", "").strip() != "reviewed":
            continue
        reviewed.append({
            "jd_title": r.get("final_difficulty_level", "")
                and r.get("jd_title", ""),  # preserve original title
            # Use final fields (already verified non-empty)
            "required_skills": [
                s.strip() for s in r["final_required_skills"].split(";") if s.strip()
            ],
            "bonus_skills": [
                s.strip() for s in r["final_bonus_skills"].split(";") if s.strip()
            ],
            "difficulty_level": r["final_difficulty_level"].strip(),
            # Add audit trail
            "reviewer": r["reviewer"].strip(),
            "review_time": r["review_time"].strip(),
            "manual_reason": r["manual_reason"].strip(),
            "original_required_skills": [
                s.strip() for s in r.get("required_skills", "").split(";") if s.strip()
            ],
            "original_bonus_skills": [
                s.strip() for s in r.get("bonus_skills", "").split(";") if s.strip()
            ],
        })

    # Actually, the jd_title comes from the original field. Let's fix that.
    # The jd_title is in the row as-is, it doesn't need to be in final_*
    reviewed_fixed = []
    for r in rows:
        if r.get("review_status", "").strip() != "reviewed":
            continue
        reviewed_fixed.append({
            "jd_title": r.get("jd_title", "").strip(),
            "required_skills": [
                s.strip() for s in r["final_required_skills"].split(";") if s.strip()
            ],
            "bonus_skills": [
                s.strip() for s in r["final_bonus_skills"].split(";") if s.strip()
            ],
            "difficulty_level": r["final_difficulty_level"].strip(),
            "reviewer": r["reviewer"].strip(),
            "review_time": r["review_time"].strip(),
            "manual_reason": r["manual_reason"].strip(),
            "original_required_skills": [
                s.strip() for s in r.get("required_skills", "").split(";") if s.strip()
            ],
            "original_bonus_skills": [
                s.strip() for s in r.get("bonus_skills", "").split(";") if s.strip()
            ],
        })

    path = os.path.join(META_DIR, "gold_jd_set_reviewed.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reviewed_fixed, f, ensure_ascii=False, indent=2)
    return path, len(reviewed_fixed)


def export_gold_resume():
    rows, _ = read_csv("gold_resume_review.csv")
    reviewed = []
    for r in rows:
        if r.get("review_status", "").strip() != "reviewed":
            continue
        # Parse final_projects from JSON string
        try:
            final_projects = json.loads(r["final_projects"])
        except (json.JSONDecodeError, KeyError):
            final_projects = []

        reviewed.append({
            "resume_id": r.get("resume_id", "").strip(),
            "education": r.get("education", "").strip(),
            "degree": r.get("degree", "").strip(),
            "school": r.get("school", "").strip(),
            "skills": [
                s.strip() for s in r["final_skills"].split(";") if s.strip()
            ],
            "projects": final_projects,
            "target_jobs": [
                s.strip() for s in r["final_target_jobs"].split(";") if s.strip()
            ],
            "data_type": r.get("data_type", "").strip(),
            "reviewer": r["reviewer"].strip(),
            "review_time": r["review_time"].strip(),
            "manual_reason": r["manual_reason"].strip(),
        })

    path = os.path.join(META_DIR, "gold_resume_set_reviewed.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reviewed, f, ensure_ascii=False, indent=2)
    return path, len(reviewed)


def export_match_label():
    rows, _ = read_csv("match_label_review.csv")
    reviewed = []
    for r in rows:
        if r.get("review_status", "").strip() != "reviewed":
            continue
        reviewed.append({
            "jd_title": r.get("jd", "").strip(),
            "resume_id": r.get("resume", "").strip(),
            "match_level": r["final_match_level"].strip(),
            "matched_skills": [
                s.strip() for s in r["final_matched_skills"].split(";") if s.strip()
            ],
            "missing_skills": [
                s.strip() for s in r["final_missing_skills"].split(";") if s.strip()
            ],
            "reason": r["final_reason"].strip(),
            "reviewer": r["reviewer"].strip(),
            "review_time": r["review_time"].strip(),
            "manual_reason": r["manual_reason"].strip(),
        })

    path = os.path.join(META_DIR, "match_label_set_reviewed.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reviewed, f, ensure_ascii=False, indent=2)
    return path, len(reviewed)


def export_negative_samples():
    rows, _ = read_csv("negative_samples_review.csv")
    reviewed = []
    for r in rows:
        if r.get("review_status", "").strip() != "reviewed":
            continue
        item = {
            "type": r["final_type"].strip(),
            "description": r.get("description", "").strip(),
            "reason": r["final_reason"].strip(),
            "reviewer": r["reviewer"].strip(),
            "review_time": r["review_time"].strip(),
            "manual_reason": r["manual_reason"].strip(),
        }
        # Include original skill fields for context
        if r.get("skills", "").strip():
            item["skills"] = [s.strip() for s in r["skills"].split(";") if s.strip()]
        if r.get("resume_skills", "").strip():
            item["resume_skills"] = [s.strip() for s in r["resume_skills"].split(";") if s.strip()]
        if r.get("jd_skills", "").strip():
            item["jd_required"] = [s.strip() for s in r["jd_skills"].split(";") if s.strip()]
        reviewed.append(item)

    path = os.path.join(META_DIR, "negative_samples_reviewed.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(reviewed, f, ensure_ascii=False, indent=2)
    return path, len(reviewed)


# ================================================================
# Main
# ================================================================
def main():
    print("=" * 60)
    print("  评估数据人工审核 — 导出最终审核版")
    print("=" * 60)

    # Step 1: 校验
    print("\n[1/2] 校验人工审核状态...")
    passed, issues = check_all_passed()

    if not passed:
        print(f"  审核未通过！发现 {len(issues)} 个问题:")
        for issue in issues[:20]:
            print(f"    [FAIL] {issue}")
        if len(issues) > 20:
            print(f"    ... 共 {len(issues)} 个问题")
        print(f"\n  请先完成人工审核，使 check 全部 PASS 后重试。")
        print(f"  运行: python main.py --check-review 查看详情")
        return False

    print("  审核状态: PASS")

    # Step 2: 导出
    print("\n[2/2] 导出 reviewed 文件...")

    files = []
    for name, export_fn in [
        ("gold_jd_set_reviewed.json", export_gold_jd),
        ("gold_resume_set_reviewed.json", export_gold_resume),
        ("match_label_set_reviewed.json", export_match_label),
        ("negative_samples_reviewed.json", export_negative_samples),
    ]:
        path, count = export_fn()
        files.append((path, count))
        print(f"  -> {path} ({count} 条)")

    sep_line = "=" * 60
    print(f"\n{sep_line}")
    print("  导出完成:")
    for p, c in files:
        print(f"    {p} ({c} 条, reviewed)")
    print("")
    print("  原始文件未修改，仍保留在 data/gold/reference/ 目录下。")
    print("  reviewed 文件可用于比赛评估。")
    print(sep_line)
    return True


if __name__ == "__main__":
    ok = main()
    sys.exit(0 if ok else 1)
