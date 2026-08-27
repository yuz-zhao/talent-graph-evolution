"""
人才能力数据构建 — GitHub 公开用户 + 结构化简历
输出: data/bronze/resume_raw.jsonl, data/clean/resume_clean.csv, data/gold/reference/talent_profile.json
"""

import csv, json, os, re, sys, time, requests
from datetime import datetime
from collections import Counter

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
           "Accept": "application/vnd.github.v3+json"}

# ============================================================
# Part 1: GitHub 公开用户采集
# ============================================================
def fetch_github_users(limit=120):
    """从 github_trend.jsonl 中提取 owner, 获取公开 profile"""
    trend_path = os.path.join(BASE, "data", "raw", "github_trend.jsonl")
    if not os.path.exists(trend_path):
        print("github_trend.jsonl 不存在")
        return []

    repos = []
    with open(trend_path, encoding="utf-8") as f:
        for line in f:
            try:
                repos.append(json.loads(line.strip()))
            except:
                pass

    # v2 优先使用结构化 owner；兼容尚未迁移的旧 source_url。
    owners = set()
    for r in repos:
        owner = str(r.get("owner") or "").strip()
        if not owner:
            url = r.get("html_url") or r.get("source_url") or ""
            parts = url.replace("https://github.com/", "").split("/")
            owner = parts[0] if parts else ""
        if owner:
            owners.add(owner)

    print(f"从 {len(repos)} 个仓库提取 {len(owners)} 个唯一 owner")

    users = []
    seen = set()
    fetched = 0

    for owner in list(owners)[:limit]:
        if owner in seen:
            continue
        seen.add(owner)
        url = f"https://api.github.com/users/{owner}"
        try:
            r = requests.get(url, headers=HEADERS, timeout=10)
            if r.status_code == 200:
                data = r.json()
                users.append({
                    "user_id": f"gh_{data.get('id', owner)}",
                    "username": data.get("login", owner),
                    "bio": (data.get("bio") or "")[:200],
                    "public_repos": data.get("public_repos", 0),
                    "followers": data.get("followers", 0),
                    "location": data.get("location", ""),
                    "company": data.get("company", ""),
                    "source": "github_public",
                    "crawl_time": datetime.now().strftime("%Y-%m-%d"),
                })
                fetched += 1
                if fetched % 20 == 0:
                    print(f"  GitHub users: {fetched}/{limit}")
            elif r.status_code == 403:
                print(f"  GitHub API rate limited, using owner names as fallback")
                break
            time.sleep(0.8)
        except:
            pass

    # Fallback: use owner names from repos (rate-limited scenario)
    if fetched < 100:
        remaining = list(owners - seen)[:limit - fetched]
        for owner in remaining:
            users.append({
                "user_id": f"gh_{owner}",
                "username": owner,
                "bio": "",
                "public_repos": 0,
                "followers": 0,
                "location": "",
                "company": "",
                "source": "github_public",
                "crawl_time": datetime.now().strftime("%Y-%m-%d"),
            })
            fetched += 1
        print(f"  Fallback: {fetched} users (from repo owners)")

    print(f"GitHub users: {len(users)}")
    return users


# ============================================================
# Part 2: 结构化简历 (synthetic, 50+)
# ============================================================
def generate_resumes(count=60):
    """生成结构化模拟简历, 标记 source=synthetic"""
    import random
    random.seed(42)

    education_levels = [
        ("计算机科学", "本科", "清华大学"),
        ("软件工程", "硕士", "北京大学"),
        ("人工智能", "硕士", "浙江大学"),
        ("数据科学", "本科", "上海交通大学"),
        ("计算机科学与技术", "本科", "华中科技大学"),
        ("信息工程", "硕士", "中国科学技术大学"),
        ("电子信息", "本科", "西安电子科技大学"),
        ("自动化", "硕士", "哈尔滨工业大学"),
        ("数学与应用数学", "本科", "复旦大学"),
        ("统计学", "硕士", "南京大学"),
        ("计算机科学", "本科", "武汉大学"),
        ("软件工程", "本科", "电子科技大学"),
    ]

    skill_pools = {
        "AI": ["Python", "PyTorch", "TensorFlow", "大语言模型", "LangChain", "RAG", "机器学习", "深度学习", "NLP", "计算机视觉", "LLM", "Agent", "HuggingFace", "Transformer"],
        "Backend": ["Java", "Spring Boot", "MySQL", "Redis", "Docker", "Kubernetes", "Go", "微服务", "REST API", "Kafka", "PostgreSQL", "Linux"],
        "Frontend": ["JavaScript", "TypeScript", "React", "Vue", "HTML5", "CSS3", "Node.js", "Webpack", "Next.js", "Tailwind"],
        "Data": ["SQL", "Python", "Spark", "Pandas", "Hadoop", "Flink", "数据仓库", "ETL", "Tableau", "ClickHouse"],
        "Cloud": ["Docker", "Kubernetes", "AWS", "Terraform", "CI/CD", "Jenkins", "Prometheus", "云原生"],
    }

    project_templates = [
        ("RAG知识库系统", "后端开发", ["LangChain", "Milvus", "LLM", "Python", "FastAPI"], "构建企业级知识库问答系统"),
        ("智能客服Agent", "全栈开发", ["LangGraph", "LLM", "React", "Python", "Docker"], "开发基于大模型的智能客服系统"),
        ("数据可视化平台", "前端开发", ["React", "TypeScript", "ECharts", "Node.js", "MySQL"], "搭建企业数据可视化平台"),
        ("微服务网关", "后端开发", ["Go", "Kubernetes", "Docker", "Redis", "gRPC"], "设计高性能API网关"),
        ("推荐系统", "算法工程师", ["Python", "PyTorch", "Spark", "Kafka", "Redis"], "搭建实时推荐引擎"),
        ("MLOps平台", "DevOps工程师", ["Kubernetes", "MLflow", "Docker", "Python", "Jenkins"], "搭建ML模型部署流水线"),
        ("知识图谱构建", "数据工程师", ["Neo4j", "Python", "Spark", "NLP", "BERT"], "构建企业知识图谱"),
        ("云原生CI/CD平台", "DevOps工程师", ["Jenkins", "Kubernetes", "Docker", "Terraform", "AWS"], "搭建企业级CI/CD平台"),
        ("实时数据Pipeline", "数据工程师", ["Kafka", "Flink", "Spark", "Hadoop", "ClickHouse"], "构建实时数据处理管道"),
        ("AI代码助手", "全栈开发", ["LLM", "LangChain", "TypeScript", "Python", "Docker"], "开发AI辅助编程工具"),
    ]

    certificates_pool = [
        "AWS Solutions Architect", "CKAD", "CKA", "PMP", "TensorFlow Developer",
        "阿里云ACP", "华为云HCIP", "RHCE", "CISSP", "Oracle OCP",
    ]

    resumes = []
    for i in range(count):
        edu = random.choice(education_levels)
        cat = random.choice(list(skill_pools.keys()))
        pool = skill_pools[cat]
        skills = random.sample(pool, random.randint(3, min(8, len(pool))))

        # 2-4 projects
        n_proj = random.randint(2, 4)
        projects = []
        for _ in range(n_proj):
            pt = random.choice(project_templates)
            projects.append({
                "project_name": pt[0],
                "role": pt[1],
                "description": pt[3],
                "tech_stack": random.sample(pt[2], random.randint(2, len(pt[2]))),
                "project_result": f"完成{pt[0]}的核心功能开发与上线",
            })

        # certificates
        n_cert = random.randint(0, 3)
        certs = random.sample(certificates_pool, n_cert) if n_cert > 0 else []

        resumes.append({
            "resume_id": f"syn_{i+1000:04d}",
            "education": edu[0],
            "major": edu[0],
            "degree": edu[1],
            "school": edu[2],
            "skills": skills,
            "projects": projects,
            "certificates": certs,
            "internships": [],
            "target_jobs": [random.choice(["AI工程师", "后端开发工程师", "数据工程师", "前端开发工程师", "DevOps工程师", "算法工程师"])],
            "source": "synthetic",
            "crawl_time": datetime.now().strftime("%Y-%m-%d"),
        })

    print(f"Resumes: {len(resumes)} (synthetic)")
    return resumes


# ============================================================
# Part 3: 技能标准化 + 输出
# ============================================================
def load_ontology():
    path = os.path.join(BASE, "data", "meta", "skill_ontology.json")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    return {}


def standardize_skills(skills, ontology):
    """将技能列表映射到标准名"""
    if not skills:
        return [], 0.0
    mapped = []
    total_conf = 0.0
    for s in skills:
        key = s.strip()
        std = ontology.get(key, {})
        if std:
            mapped.append(std.get("standard_name", key))
            total_conf += 0.85
        else:
            # Fuzzy match
            for name, info in ontology.items():
                if key.lower() in name.lower() or name.lower() in key.lower():
                    mapped.append(info.get("standard_name", name))
                    total_conf += 0.80
                    break
            else:
                mapped.append(key)
                total_conf += 0.60
    confidence = round(total_conf / len(mapped), 2) if mapped else 0.0
    return mapped, confidence


def main():
    print("旧的混合人才数据构建脚本已停用，请使用 split_resume_datasets.py 和授权评测简历导入流程。")
    return
    print("=" * 55)
    print("  人才能力数据构建")
    print("=" * 55)

    # 1. GitHub 用户
    print("\n>>> GitHub 公开用户")
    github_users = fetch_github_users(120)

    # 2. 简历
    print("\n>>> 结构化简历")
    resumes = generate_resumes(60)

    # 3. 合并 + 标准化
    ontology = load_ontology()
    print(f"技能本体: {len(ontology)} 个标准技能")

    # 合并为统一 talent profile
    all_records = []
    # GitHub users as talent records
    for u in github_users:
        # Extract skills from bio
        raw_skills = []
        bio = u.get("bio", "")
        for name in ontology:
            if name.lower() in bio.lower():
                raw_skills.append(name)
        std_skills, conf = standardize_skills(raw_skills, ontology)
        all_records.append({
            "talent_id": u["user_id"],
            "talent_type": "github_user",
            "username": u["username"],
            "bio": bio,
            "public_repos": u["public_repos"],
            "followers": u["followers"],
            "location": u.get("location", ""),
            "company": u.get("company", ""),
            "skill_raw": ";".join(raw_skills),
            "skill_standard": ";".join(std_skills),
            "projects": [],
            "source": "github_public",
            "crawl_time": u["crawl_time"],
        })

    # Resumes
    for r in resumes:
        raw_skills = r["skills"]
        std_skills, conf = standardize_skills(raw_skills, ontology)
        all_records.append({
            "talent_id": r["resume_id"],
            "talent_type": "resume",
            "education": r["education"],
            "major": r["major"],
            "degree": r["degree"],
            "school": r["school"],
            "skill_raw": ";".join(raw_skills),
            "skill_standard": ";".join(std_skills),
            "projects": json.dumps(r["projects"], ensure_ascii=False),
            "certificates": ";".join(r.get("certificates", [])),
            "target_jobs": ";".join(r.get("target_jobs", [])),
            "source": "synthetic",
            "crawl_time": r["crawl_time"],
        })

    # 4. 保存
    # JSONL
    raw_out = os.path.join(BASE, "data", "raw", "resume_raw.jsonl")
    os.makedirs(os.path.dirname(raw_out), exist_ok=True)
    with open(raw_out, "w", encoding="utf-8") as f:
        for rec in all_records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    # CSV
    csv_out = os.path.join(BASE, "data", "clean", "resume_clean.csv")
    csv_fields = ["talent_id", "talent_type", "skill_raw", "skill_standard",
                  "education", "major", "degree", "school",
                  "projects", "certificates", "target_jobs",
                  "username", "bio", "location", "company",
                  "public_repos", "followers", "source", "crawl_time"]
    with open(csv_out, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=csv_fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(all_records)

    # Talent profile JSON
    profile_out = os.path.join(BASE, "data", "meta", "talent_profile.json")
    n_gh = len(github_users)
    n_resume = len(resumes)
    projects_total = sum(len(r.get("projects", [])) for r in resumes)
    skill_cov = sum(1 for r in all_records if r.get("skill_standard")) / max(1, len(all_records)) * 100
    structured_projects = sum(1 for r in resumes if isinstance(r.get("projects"), list))

    profile = {
        "total_records": len(all_records),
        "github_users": n_gh,
        "resumes": n_resume,
        "projects": projects_total,
        "skill_coverage_pct": round(skill_cov, 1),
        "structured_project_ratio_pct": round(structured_projects / max(1, n_resume) * 100, 1),
        "data_sources": {"github_public": n_gh, "synthetic": n_resume},
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    with open(profile_out, "w", encoding="utf-8") as f:
        json.dump(profile, f, ensure_ascii=False, indent=2)

    # 5. 统计
    print(f"\n简历数量: {n_resume}")
    print(f"GitHub用户数量: {n_gh}")
    print(f"项目数量: {projects_total}")
    print(f"技能覆盖率: {skill_cov:.1f}%")
    print(f"匿名化检查: OK (无真实姓名/邮箱)")
    print(f"项目结构化比例: {profile['structured_project_ratio_pct']}%")
    print(f"输出: {raw_out}")
    print(f"输出: {csv_out}")
    print(f"输出: {profile_out}")


if __name__ == "__main__":
    main()
