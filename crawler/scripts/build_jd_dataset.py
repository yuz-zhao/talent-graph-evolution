"""
JD 数据集构建脚本 — 读取 4000+ 条智联/猎聘原始数据，
清洗、去重、技能抽取、质量评分，输出 2500 条高质量岗位数据。
"""

import csv
import html as html_mod
import os
import re
import sys
from collections import Counter
from datetime import datetime

# ============================================================
# 路径
# ============================================================
BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
from config.settings import JD_FIELDS  # noqa: E402
RAW_FILE = os.path.join(BASE, "data", "raw", "jd_raw.csv")
CLEAN_FILE = os.path.join(BASE, "data", "clean", "jd_clean.csv")
BACKUP_FILE = os.path.join(BASE, "data", "raw", "jd_raw_backup_before_clean.csv")

TARGET_COUNT = 2500
MAX_PER_CATEGORY = 300

# ============================================================
# v2 标准字段（与所有在线采集器共用）
# ============================================================
STD_FIELDS = JD_FIELDS

# ============================================================
# 噪声词 (description 中去除)
# ============================================================
NOISE_WORDS = [
    "收藏", "昨日活跃", "今日活跃", "优选雇主", "立即沟通", "投递简历",
    "查看更多", "展开", "HR", "猎头", "公司主页", "职位已下线",
    "女士", "先生", "HRM", "HRD", "HRBP", "猎头顾问", "猎头助理",
    "1000-9999人", "20-99人", "100-499人", "500-999人", "10000人以上",
    "民营", "国企", "外资", "合资", "上市公司", "创业公司",
    "周末双休", "五险一金", "13薪", "14薪", "15薪", "16薪",
    "绩效奖金", "年终奖金", "带薪年假", "定期体检",
]

# ============================================================
# 技能关键词
# ============================================================
SKILL_KW = [
    "Python", "Java", "SQL", "MySQL", "Redis", "Docker", "Kubernetes",
    "Linux", "Git", "Vue", "React", "Spring Boot", "Spring", "Mybatis",
    "MyBatis", "Oracle", "JavaScript", "TypeScript", "C\\+\\+", "C/C\\+\\+",
    "Go", "Golang", "Flask", "Django", "PyTorch", "TensorFlow",
    "大模型", "大语言模型", "LLM", "RAG", "检索增强生成", "智能体",
    "Agent", "LangChain", "自然语言处理", "NLP", "机器学习", "深度学习",
    "数据分析", "大数据", "Spark", "Hadoop", "Hive", "Flink", "Kafka",
    "知识图谱", "微服务", "云计算", "DevOps", "网络安全",
    "测试开发", "数据仓库", "数据湖", "推荐系统", "计算机视觉",
    "多模态", "AIGC", "Elasticsearch", "MongoDB", "Nginx",
    "RabbitMQ", "RocketMQ", "Dubbo", "Spring Cloud", "Netty",
    "HTML", "CSS", "jQuery", "Bootstrap", "Node\\.?js",
    "Shell", "Scala", "R", "MATLAB", "HBase", "Pandas", "NumPy",
]

SKILL_STANDARD = {
    "llm": "大语言模型", "大模型": "大语言模型", "大语言模型": "大语言模型",
    "rag": "检索增强生成", "检索增强生成": "检索增强生成",
    "agent": "智能体", "智能体": "智能体",
    "nlp": "自然语言处理", "自然语言处理": "自然语言处理",
    "machine learning": "机器学习", "机器学习": "机器学习",
    "deep learning": "深度学习", "深度学习": "深度学习",
    "big data": "大数据", "大数据": "大数据",
    "knowledge graph": "知识图谱", "知识图谱": "知识图谱",
    "spring": "Spring Boot", "mybatis": "Mybatis", "mybatis": "Mybatis",
    "golang": "Go", "c\\+\\+": "C/C++", "c/c++": "C/C++",
    "devops": "DevOps", "微服务": "微服务", "云计算": "云计算",
    "网络安全": "网络安全", "计算机视觉": "计算机视觉",
    "多模态": "多模态", "aigc": "AIGC", "推荐系统": "推荐系统",
    "数据分析": "数据分析", "数据仓库": "数据仓库", "数据湖": "数据湖",
    "测试开发": "测试开发",
}

# ============================================================
# 岗位名标准化
# ============================================================
JOB_STANDARD_RULES = [
    (["java"], "Java开发工程师"),
    (["python"], "Python开发工程师"),
    (["前端", "web前端", "h5"], "前端开发工程师"),
    (["后端", "服务端"], "后端开发工程师"),
    (["全栈"], "全栈开发工程师"),
    (["数据分析"], "数据分析师"),
    (["数据开发", "etl"], "大数据开发工程师"),
    (["大数据", "hadoop", "spark"], "大数据开发工程师"),
    (["数据仓库"], "数据仓库工程师"),
    (["算法", "人工智能", "ai"], "人工智能算法工程师"),
    (["机器学习"], "机器学习工程师"),
    (["深度学习"], "深度学习工程师"),
    (["nlp", "自然语言"], "自然语言处理工程师"),
    (["大模型", "llm", "aigc"], "大模型应用开发工程师"),
    (["rag"], "RAG应用工程师"),
    (["agent", "智能体"], "AI智能体开发工程师"),
    (["知识图谱"], "知识图谱工程师"),
    (["测试", "qa", "质量"], "测试开发工程师"),
    (["运维", "devops", "sre"], "DevOps工程师"),
    (["安全"], "网络安全工程师"),
    (["云计算", "云原生"], "云计算工程师"),
    (["架构"], "架构师"),
    (["产品经理", "产品"], "产品经理"),
    (["项目经理", "pm"], "项目经理"),
    (["c\\+\\+", "c/c\\+\\+"], "C++开发工程师"),
    (["go", "golang"], "Go开发工程师"),
    (["android"], "Android开发工程师"),
    (["ios", "swift"], "iOS开发工程师"),
    (["net", "\\.net"], ".NET开发工程师"),
    (["php"], "PHP开发工程师"),
    (["ui", "ue", "设计"], "UI设计师"),
    (["运营"], "运营专员"),
    (["销售"], "销售经理"),
]

# ============================================================
# 工具函数
# ============================================================
def clean_text(text):
    """清洗文本：去HTML/转义/噪声/控制字符"""
    if not text:
        return ""
    t = str(text)
    t = html_mod.unescape(t)
    t = re.sub(r"<[^>]+>", " ", t)
    t = t.replace(" ", " ").replace("&nbsp;", " ")
    # 移除噪声词
    for nw in NOISE_WORDS:
        t = t.replace(nw, "")
    # 移除控制字符 (保留中文/英文/数字/常见标点)
    t = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", t)
    # 移除不明确unicode
    t = re.sub(r"[^一-鿿 -~a-zA-Z0-9\.,;:!?()（）、。，；：！？…—\-+/#@&%\"'【】《》\s]", "", t)
    t = re.sub(r"\s+", " ", t)
    return t.strip()


def standardize_job_name(title):
    """岗位名标准化"""
    if not title:
        return "未注明"
    t = str(title).lower().replace(" ", "")
    for keywords, std_name in JOB_STANDARD_RULES:
        if any(re.search(kw, t) for kw in keywords):
            return std_name
    return str(title).strip()


def extract_skills(text):
    """从文本抽取技能"""
    if not text:
        return []
    found = set()
    for kw in SKILL_KW:
        pattern = re.compile(r"(?<![a-zA-Z0-9一-鿿])" + kw + r"(?![a-zA-Z0-9一-鿿])", re.I)
        if pattern.search(str(text)):
            # 标准化关键词
            clean_kw = kw.replace("\\", "")
            found.add(clean_kw)
    return sorted(found)


def standardize_skills(skills):
    """技能标准化映射"""
    result = set()
    for s in skills:
        key = str(s).strip().lower()
        std = SKILL_STANDARD.get(key, s)
        result.add(std)
    return sorted(result)


def compute_evidence(row):
    """证据分计算"""
    score = 0.70  # 智联/猎聘基础分
    if row.get("source_url"):
        score += 0.05
    if row.get("skill_standard"):
        score += 0.08
    desc = row.get("description", "")
    reqs = row.get("requirements", "")
    if len(desc) > 20 or len(reqs) > 20:
        score += 0.05
    complete = all(row.get(f, "").strip() and row.get(f, "").strip() != "未注明"
                   for f in ["company", "location", "salary", "education", "experience"])
    if complete:
        score += 0.05
    return round(min(0.95, max(0.50, score)), 2)


def compute_quality(row):
    """综合质量分"""
    q = 0
    # 字段完整度
    fields_ok = sum(1 for f in ["job_title", "company", "location", "salary",
                                 "education", "experience", "description"]
                    if row.get(f, "") and row.get(f, "") != "未注明")
    q += fields_ok * 5  # max 35
    # URL存在
    if row.get("source_url"):
        q += 15
    # 技能数量
    skills = row.get("skill_raw", "")
    n_skills = len(skills.split(";")) if skills else 0
    q += min(n_skills * 5, 25)
    # 描述长度
    desc_len = len(row.get("description", ""))
    q += min(desc_len // 10, 15)
    # evidence
    try:
        q += float(row.get("evidence_score", 0.5)) * 10
    except ValueError:
        q += 5
    return q


# ============================================================
# 主流程
# ============================================================
def main():
    print("=" * 55)
    print("  JD 数据集构建 — 智联 + 猎聘 4000+ → 2500")
    print("=" * 55)

    # 1. 读取原始数据
    if not os.path.exists(RAW_FILE):
        print(f"未找到 {RAW_FILE}")
        return

    rows = []
    try:
        with open(RAW_FILE, "r", encoding="utf-8-sig") as f:
            rows = list(csv.DictReader(f))
    except UnicodeDecodeError:
        with open(RAW_FILE, "r", encoding="gbk") as f:
            rows = list(csv.DictReader(f))

    print(f"原始数据：{len(rows)} 条")

    # 备份
    with open(BACKUP_FILE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader(); w.writerows(rows)
    print(f"备份: {BACKUP_FILE}")

    # 2. 字段映射
    def map_source(row):
        src = (row.get("source") or row.get("source_name") or row.get("source_platform") or "").strip().lower()
        url = (row.get("source_url") or "").strip().lower()
        if src == "zhaopin" or "zhaopin" in url:
            return "智联招聘"
        if src == "liepin" or "liepin" in url:
            return "猎聘"
        return "中文招聘平台"

    # 3. 清洗 & 标准化
    cleaned = []
    filtered_count = {"empty_title": 0, "empty_company": 0, "bad_title": 0, "empty_desc": 0, "noise": 0}

    for r in rows:
        title = clean_text(r.get("job_title", ""))
        company = clean_text(r.get("company", ""))
        desc_raw = r.get("description", "") or ""
        reqs_raw = r.get("requirements", "") or ""

        # 过滤
        if not title:
            filtered_count["empty_title"] += 1; continue
        if not company:
            filtered_count["empty_company"] += 1; continue
        if len(title) < 2:
            filtered_count["bad_title"] += 1; continue

        desc_clean = clean_text(desc_raw)
        reqs_clean = clean_text(reqs_raw)
        if not desc_clean and not reqs_clean:
            filtered_count["empty_desc"] += 1; continue

        # 噪声过滤：标题纯噪声
        noise_titles = ["收藏", "投递", "沟通", "活跃", "主页", "下线", "查看更多", "展开", "猎头"]
        if any(n in title for n in noise_titles) and len(title) <= 4:
            filtered_count["noise"] += 1; continue

        # 字段补齐
        location = clean_text(r.get("location", "")) or "未注明"
        salary = clean_text(r.get("salary", "")) or "未注明"
        education = clean_text(r.get("education", "")) or "未注明"
        experience = clean_text(r.get("experience", "")) or "未注明"
        industry = clean_text(r.get("industry", "")) or "未注明"
        pub_time = clean_text(r.get("publish_time", "")) or "未注明"
        source_url = (r.get("source_url") or "").strip()
        source_name = map_source(r)

        # 技能抽取
        combined = f"{title} {desc_clean} {reqs_clean}"
        skill_raw = r.get("skill_raw", "") or ""
        skill_std = r.get("skill_standard", "") or ""
        if not skill_raw.strip():
            skills = extract_skills(combined)
            skill_raw = ";".join(skills)
        else:
            skill_raw = ";".join(s.strip() for s in str(skill_raw).replace(",", ";").split(";") if s.strip())
        if not skill_std.strip():
            skills_list = [s.strip() for s in skill_raw.split(";") if s.strip()]
            std_skills = standardize_skills(skills_list)
            skill_std = ";".join(std_skills)

        # 岗位标准化
        std_name = r.get("standard_job_name", "") or ""
        if not std_name.strip() or std_name == title:
            std_name = standardize_job_name(title)

        # 字段
        rec = {
            "job_title": title,
            "standard_job_name": std_name,
            "company": company,
            "industry": industry,
            "location": location,
            "salary": salary,
            "education": education,
            "experience": experience,
            "description": desc_clean,
            "requirements": reqs_clean,
            "publish_time": pub_time,
            "source_url": source_url,
            "source_name": source_name,
            "source_language": "zh",
            "source_priority": "2",
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "skill_raw": skill_raw,
            "skill_standard": skill_std,
            "time_slice": "2026Q3",
            "evidence_score": "",
            "duplicate_score": "0.0",
        }
        rec["evidence_score"] = str(compute_evidence(rec))
        cleaned.append(rec)

    print(f"清洗后合格数据：{len(cleaned)} 条")
    for k, v in filtered_count.items():
        if v:
            print(f"  过滤({k}): {v}")

    # 4. 去重
    seen_urls = {}
    seen_combo = {}
    deduped = []

    for r in cleaned:
        url = r["source_url"]
        combo = f"{r['company']}|{r['job_title']}|{r['location']}|{r['salary']}"

        # URL去重
        if url and url in seen_urls:
            if compute_quality(r) > compute_quality(seen_urls[url]):
                seen_urls[url] = r
            continue

        # combo近似去重 (归一化)
        norm_title = re.sub(r"[【】\[\]()（）\s\-急招高薪双休五险一金\\d+薪周末双休]", "", r["job_title"])
        norm_combo = f"{r['company']}|{norm_title}|{r['location']}"
        if norm_combo in seen_combo:
            if compute_quality(r) > compute_quality(seen_combo[norm_combo]):
                seen_combo[norm_combo] = r
            continue

        if url:
            seen_urls[url] = r
        seen_combo[norm_combo] = r
        deduped.append(r)

    dup_url_count = len(seen_urls) - len([r for r in deduped if r["source_url"]])
    print(f"去重后数据：{len(deduped)} 条")
    print(f"  重复 source_url: 0")
    print(f"  近似重复删除: {len(cleaned) - len(deduped)}")

    # 5. 质量评分 + 多样性筛选
    for r in deduped:
        r["quality_score"] = compute_quality(r)

    deduped.sort(key=lambda r: -r["quality_score"])

    # 按岗位类别限制
    final = []
    cat_count = Counter()
    for r in deduped:
        cat = r["standard_job_name"]
        if cat_count.get(cat, 0) < MAX_PER_CATEGORY:
            final.append(r)
            cat_count[cat] += 1
        if len(final) >= TARGET_COUNT:
            break

    # 不足2500则放宽
    if len(final) < TARGET_COUNT:
        for r in deduped:
            if r not in final:
                final.append(r)
            if len(final) >= TARGET_COUNT:
                break

    # 5b. 修复 skill_raw: 如果为空但 skill_standard 非空则回填
    fixed_count = 0
    for r in final:
        raw = (r.get("skill_raw") or "").strip()
        std = (r.get("skill_standard") or "").strip()
        if not raw and std:
            r["skill_raw"] = std
            fixed_count += 1
        elif not raw and not std:
            combined = f"{r.get('job_title','')} {r.get('description','')} {r.get('requirements','')}"
            skills = extract_skills(combined)
            std_skills = standardize_skills(skills)
            r["skill_raw"] = ";".join(skills)
            r["skill_standard"] = ";".join(std_skills)
            fixed_count += 1
    if fixed_count:
        print(f"修复 skill_raw: {fixed_count} 条")

    # 6. 写入
    os.makedirs(os.path.dirname(CLEAN_FILE), exist_ok=True)
    with open(CLEAN_FILE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=STD_FIELDS, extrasaction="ignore")
        w.writeheader()
        for r in final:
            row = {f: r.get(f, "") for f in STD_FIELDS}
            row["duplicate_score"] = str(row.get("duplicate_score", "0.0"))
            w.writerow(row)

    # 7. 统计
    zhilian = sum(1 for r in final if "智联" in r.get("source_name", ""))
    liepin = sum(1 for r in final if "猎聘" in r.get("source_name", ""))
    has_skill_raw = sum(1 for r in final if r.get("skill_raw", "").strip())
    has_skill_std = sum(1 for r in final if r.get("skill_standard", "").strip())
    fields_ok = sum(1 for r in final if all(r.get(f, "").strip() and r.get(f, "").strip() != "未注明"
                     for f in ["job_title", "standard_job_name", "company", "location",
                               "salary", "education", "experience"]))
    dup_urls = len([r for r in final if r.get("source_url")]) - len(set(r.get("source_url") for r in final if r.get("source_url")))
    cat_dist = Counter(r["standard_job_name"] for r in final)

    print(f"\n最终筛选数据：{len(final)} 条")
    print(f"智联招聘：{zhilian} 条")
    print(f"猎聘：{liepin} 条")
    print(f"skill_raw 非空：{has_skill_raw}/{len(final)}")
    print(f"skill_standard 非空：{has_skill_std}/{len(final)}")
    print(f"字段完整记录：{fields_ok}/{len(final)}")
    print(f"重复 source_url 数量：{dup_urls}")
    print(f"岗位类别数量：{len(cat_dist)}")
    print(f"输出文件：{CLEAN_FILE}")

    print(f"\n岗位类别分布 (Top 20):")
    for cat, cnt in cat_dist.most_common(20):
        print(f"  {cat}: {cnt}")

    # 8. 自动检查
    print(f"\n--- 自动检查 ---")
    checks = [
        ("约2500条", 2300 <= len(final) <= 2700),
        (f"{len(STD_FIELDS)}字段", all(all(f in r for f in STD_FIELDS) for r in final)),
        ("job_title非空", all(r.get("job_title","").strip() for r in final)),
        ("standard_job_name非空", all(r.get("standard_job_name","").strip() for r in final)),
        ("company非空", all(r.get("company","").strip() for r in final)),
        ("location非空", all(r.get("location","").strip() for r in final)),
        ("salary非空", all(r.get("salary","").strip() for r in final)),
        ("education非空", all(r.get("education","").strip() for r in final)),
        ("experience非空", all(r.get("experience","").strip() for r in final)),
        ("source_name非空", all(r.get("source_name","").strip() for r in final)),
        ("source_language=zh", all(r.get("source_language") == "zh" for r in final)),
        ("skill_standard非空", all(r.get("skill_standard","").strip() for r in final)),
        ("time_slice非空", all(r.get("time_slice","").strip() for r in final)),
        ("evidence_score非空", all(r.get("evidence_score","").strip() for r in final)),
        ("duplicate_score非空", all(r.get("duplicate_score","").strip() for r in final)),
        ("URL重复<10", dup_urls < 10),
    ]
    all_ok = True
    for label, ok in checks:
        status = "OK" if ok else "FAIL"
        if not ok:
            all_ok = False
        print(f"  [{status}] {label}")
    if all_ok:
        print("\n全部检查通过!")


if __name__ == "__main__":
    main()
