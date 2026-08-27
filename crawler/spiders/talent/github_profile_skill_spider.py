"""
GitHub 人才技能抽取 — 从已采集的 github_detail.jsonl 中提取技能
映射到 skill_ontology.json，更新 resume_clean.csv 中 github_public 记录
"""

import csv, json, os
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


def load_ontology():
    path = os.path.join(BASE, "crawler", "data", "meta", "skill_ontology.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def build_owner_skill_map():
    """从 github_detail.jsonl 构建 owner → tech_stack 映射"""
    detail_path = os.path.join(BASE, "crawler", "data", "raw", "github_detail.jsonl")
    if not os.path.exists(detail_path):
        print(f"文件不存在: {detail_path}")
        return {}

    owner_skills = {}  # owner → set(skills)
    with open(detail_path, encoding="utf-8") as f:
        for line in f:
            try:
                d = json.loads(line.strip())
                owner = d.get("owner", "")
                tech = d.get("tech_stack", "")
                if owner and tech:
                    if owner not in owner_skills:
                        owner_skills[owner] = set()
                    for s in tech.split(";"):
                        s = s.strip()
                        if s:
                            owner_skills[owner].add(s)
            except:
                pass

    print(f"Owner skill map: {len(owner_skills)} owners")
    return owner_skills


def standardize_skill(raw_skill, ontology):
    """将原始技能名映射到 ontology 标准名"""
    # 精确匹配
    if raw_skill in ontology:
        return ontology[raw_skill]["standard_name"]
    # 大小写不敏感
    for name, info in ontology.items():
        if raw_skill.lower() == name.lower():
            return info["standard_name"]
    # 包含匹配
    for name, info in ontology.items():
        if raw_skill.lower() in name.lower() or name.lower() in raw_skill.lower():
            return info["standard_name"]
    return raw_skill


def run():
    ontology = load_ontology()
    print(f"技能本体: {len(ontology)} 个标准技能")

    # 构建 owner → skills
    owner_skills = build_owner_skill_map()

    # 读取 resume_clean.csv
    csv_path = os.path.join(BASE, "crawler", "data", "clean", "resume_clean.csv")
    if not os.path.exists(csv_path):
        print(f"文件不存在: {csv_path}")
        return

    with open(csv_path, encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    fields = list(rows[0].keys())

    updated = 0
    skill_count = Counter()
    for r in rows:
        if r.get("talent_type") != "github_user":
            continue
        # 已有技能则跳过
        if r.get("skill_standard", "").strip() and r.get("skill_standard", "") != "未注明":
            continue

        username = r.get("username", "")
        skills_raw = owner_skills.get(username, set())
        if not skills_raw:
            continue

        # 标准化
        std_skills = []
        for s in sorted(skills_raw):
            std = standardize_skill(s, ontology)
            std_skills.append(std)
            skill_count[std] += 1

        r["skill_raw"] = ";".join(sorted(skills_raw))
        r["skill_standard"] = ";".join(std_skills)
        updated += 1

    # 写回
    with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    # 统计
    gh_total = sum(1 for r in rows if r["talent_type"] == "github_user")
    gh_with_skills = sum(1 for r in rows if r["talent_type"] == "github_user" and r.get("skill_standard", "").strip())
    coverage = round(gh_with_skills / max(1, gh_total) * 100, 1)

    print(f"\nGitHub 人才数量: {gh_total}")
    print(f"README 成功解析: {gh_with_skills}")
    print(f"技能覆盖率: {coverage}%")
    print(f"Top 技能:")
    for skill, cnt in skill_count.most_common(20):
        print(f"  {skill}: {cnt}")


if __name__ == "__main__":
    run()
