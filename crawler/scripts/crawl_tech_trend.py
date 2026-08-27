"""
技术趋势完整采集 — GitHub + arXiv + Blog → 技能映射 → 清洗输出
用法: python scripts/crawl_tech_trend.py
"""

import csv
import json
import os
import sys
import re
from collections import Counter
from datetime import datetime

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)

# ============================================================
# 技能映射 (来自 skill_ontology.json)
# ============================================================
SKILL_MAP = {
    # AI/LLM
    "llm": ("大语言模型", "AI", "人工智能", "growth", 0.95),
    "large language model": ("大语言模型", "AI", "人工智能", "growth", 0.95),
    "langchain": ("大模型应用开发", "AI", "大语言模型", "growth", 0.95),
    "llamaindex": ("大模型应用开发", "AI", "大语言模型", "growth", 0.90),
    "rag": ("检索增强生成", "AI", "大语言模型", "growth", 0.95),
    "retrieval augmented generation": ("检索增强生成", "AI", "大语言模型", "growth", 0.95),
    "agent": ("AI智能体开发", "AI Agent", "大语言模型", "emerging", 0.90),
    "ai agent": ("AI智能体开发", "AI Agent", "大语言模型", "emerging", 0.90),
    "autonomous": ("AI智能体开发", "AI Agent", "大语言模型", "emerging", 0.85),
    "prompt engineering": ("Prompt Engineering", "AI", "大语言模型", "growth", 0.90),
    "prompt": ("Prompt Engineering", "AI", "大语言模型", "growth", 0.85),
    "copilot": ("AI智能体开发", "AI Agent", "大语言模型", "growth", 0.85),
    # NLP/CV
    "nlp": ("自然语言处理", "AI", "人工智能", "mature", 0.95),
    "natural language processing": ("自然语言处理", "AI", "人工智能", "mature", 0.95),
    "computer vision": ("计算机视觉", "AI", "深度学习", "mature", 0.95),
    "cv": ("计算机视觉", "AI", "深度学习", "mature", 0.95),
    "multimodal": ("多模态AI", "AI", "深度学习", "emerging", 0.90),
    "image recognition": ("计算机视觉", "AI", "深度学习", "mature", 0.90),
    "object detection": ("计算机视觉", "AI", "深度学习", "mature", 0.90),
    "ocr": ("计算机视觉", "AI", "深度学习", "mature", 0.85),
    # ML/DL
    "machine learning": ("机器学习", "AI", "人工智能", "mature", 0.95),
    "deep learning": ("深度学习", "AI", "机器学习", "mature", 0.95),
    "neural network": ("深度学习", "AI", "机器学习", "mature", 0.90),
    "pytorch": ("PyTorch", "AI", "深度学习", "mature", 0.95),
    "tensorflow": ("TensorFlow", "AI", "深度学习", "mature", 0.95),
    "jax": ("JAX", "AI", "深度学习", "growth", 0.85),
    "transformer": ("Transformer", "AI", "深度学习", "mature", 0.90),
    "cnn": ("深度学习", "AI", "机器学习", "mature", 0.85),
    "rnn": ("深度学习", "AI", "机器学习", "mature", 0.80),
    "lstm": ("深度学习", "AI", "机器学习", "mature", 0.80),
    "transfer learning": ("迁移学习", "AI", "深度学习", "growth", 0.85),
    "fine-tun": ("模型微调", "AI", "大语言模型", "growth", 0.90),
    # Data
    "data engineering": ("数据工程", "Data", "大数据", "growth", 0.90),
    "data pipeline": ("数据工程", "Data", "大数据", "growth", 0.85),
    "big data": ("大数据", "Data", None, "mature", 0.95),
    "spark": ("Spark", "Data", "大数据", "mature", 0.95),
    "hadoop": ("Hadoop", "Data", "大数据", "mature", 0.90),
    "kafka": ("Kafka", "Data", "大数据", "growth", 0.90),
    "flink": ("Flink", "Data", "大数据", "growth", 0.85),
    "sql": ("SQL", "Data", "大数据", "mature", 0.95),
    "etl": ("数据工程", "Data", "大数据", "growth", 0.85),
    "airflow": ("Airflow", "Data", "数据工程", "growth", 0.90),
    "data warehouse": ("数据仓库", "Data", "大数据", "mature", 0.90),
    "data lake": ("数据湖", "Data", "大数据", "growth", 0.85),
    "data quality": ("数据质量", "Data", "数据工程", "growth", 0.85),
    # Cloud/Infra
    "cloud": ("云计算", "Cloud", None, "mature", 0.90),
    "cloud computing": ("云计算", "Cloud", None, "mature", 0.95),
    "docker": ("Docker", "Cloud", "云计算", "mature", 0.95),
    "kubernetes": ("Kubernetes", "Cloud", "Docker", "mature", 0.95),
    "k8s": ("Kubernetes", "Cloud", "Docker", "mature", 0.95),
    "aws": ("云计算", "Cloud", None, "mature", 0.90),
    "gcp": ("云计算", "Cloud", None, "mature", 0.85),
    "azure": ("云计算", "Cloud", None, "mature", 0.85),
    "devops": ("DevOps", "Cloud", "云计算", "mature", 0.90),
    "ci/cd": ("DevOps", "Cloud", "云计算", "mature", 0.90),
    "terraform": ("Terraform", "Cloud", "DevOps", "growth", 0.90),
    "serverless": ("Serverless", "Cloud", "云计算", "growth", 0.85),
    "microservice": ("微服务", "Cloud", "云计算", "mature", 0.90),
    "container": ("容器技术", "Cloud", "云计算", "mature", 0.90),
    # Vector/Graph
    "embedding": ("Embedding", "AI", "大语言模型", "growth", 0.90),
    "vector database": ("向量数据库", "AI", "Embedding", "growth", 0.95),
    "vector search": ("向量检索", "AI", "向量数据库", "growth", 0.90),
    "milvus": ("Milvus", "AI", "向量数据库", "growth", 0.95),
    "pinecone": ("Pinecone", "AI", "向量数据库", "growth", 0.90),
    "faiss": ("FAISS", "AI", "向量数据库", "growth", 0.90),
    "weaviate": ("Weaviate", "AI", "向量数据库", "emerging", 0.85),
    "qdrant": ("Qdrant", "AI", "向量数据库", "emerging", 0.85),
    "chroma": ("Chroma", "AI", "向量数据库", "emerging", 0.80),
    "knowledge graph": ("知识图谱", "AI", "人工智能", "growth", 0.95),
    "graph database": ("图数据库", "AI", "知识图谱", "growth", 0.90),
    "neo4j": ("Neo4j", "AI", "图数据库", "mature", 0.95),
    "graph neural": ("图神经网络", "AI", "知识图谱", "emerging", 0.90),
    "gnn": ("图神经网络", "AI", "知识图谱", "emerging", 0.90),
    "graphrag": ("GraphRAG", "AI", "知识图谱", "emerging", 0.90),
    # General
    "python": ("Python", "Programming", None, "mature", 0.95),
    "java": ("Java", "Programming", None, "mature", 0.95),
    "javascript": ("JavaScript", "Programming", None, "mature", 0.95),
    "typescript": ("TypeScript", "Programming", None, "mature", 0.90),
    "go": ("Go", "Programming", None, "growth", 0.90),
    "rust": ("Rust", "Programming", None, "growth", 0.90),
    "c++": ("C++", "Programming", None, "mature", 0.95),
    "react": ("React", "Frontend", None, "mature", 0.95),
    "vue": ("Vue", "Frontend", None, "mature", 0.90),
    "node": ("Node.js", "Backend", None, "mature", 0.90),
    "api": ("API Development", "Backend", None, "mature", 0.85),
    "rest": ("REST API", "Backend", None, "mature", 0.85),
    "graphql": ("GraphQL", "Backend", None, "growth", 0.85),
    "linux": ("Linux", "Infrastructure", None, "mature", 0.95),
    "git": ("Git", "DevTools", None, "mature", 0.95),
    "redis": ("Redis", "Data", None, "mature", 0.90),
    "mysql": ("MySQL", "Data", None, "mature", 0.95),
    "postgresql": ("PostgreSQL", "Data", None, "mature", 0.90),
    "mongodb": ("MongoDB", "Data", None, "mature", 0.90),
    "elasticsearch": ("Elasticsearch", "Data", None, "mature", 0.90),
    "mlops": ("MLOps", "Cloud", "DevOps", "growth", 0.90),
    "model serving": ("Model Serving", "Cloud", "MLOps", "growth", 0.85),
    "security": ("安全技术", "Security", None, "mature", 0.85),
    "opensource": ("开源", "General", None, "mature", 0.80),
}


def map_skill(text):
    """将技术文本映射到标准技能"""
    found = {}
    text_lower = str(text).lower()
    for kw, (std, cat, parent, lifecycle, conf) in SKILL_MAP.items():
        if kw in text_lower:
            if std not in found or conf > found[std][4]:
                found[std] = (std, cat, parent, lifecycle, conf)
    return list(found.values())


def load_jsonl(path):
    if not os.path.exists(path):
        return []
    records = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                records.append(json.loads(line.strip()))
            except:
                pass
    return records


def main():
    print("=" * 55)
    print("  技术趋势采集 + 技能映射")
    print("=" * 55)

    # 1. GitHub
    print("\n>>> GitHub")
    from spiders.tech.github_trend_spider import run as run_github
    github_records = run_github()

    # 2. arXiv
    print("\n>>> arXiv")
    from spiders.tech.arxiv_spider import run as run_arxiv
    arxiv_records = run_arxiv()

    # 3. Blog
    print("\n>>> Blog")
    from spiders.tech.blog_spider import run as run_blog
    blog_records = run_blog()

    # 4. 合并去重
    all_tech = github_records + arxiv_records + [a for a in blog_records if a.get("source_url")]
    seen = set()
    merged = []
    for r in all_tech:
        url = r.get("source_url", "")
        if url and url in seen:
            continue
        seen.add(url)
        merged.append(r)
    print(f"\n技术数据总量: {len(merged)} (GitHub:{len(github_records)} arXiv:{len(arxiv_records)} Blog:{len(blog_records)})")
    print(f"去重后: {len(merged)} (重复: {len(all_tech) - len(merged)})")

    # 5. 技能映射
    all_skills = {}  # skill_name → {frequency, source_count, category, standard, confidence}
    raw_keyword_counts = Counter()
    for r in merged:
        combined = f"{r.get('tech_name','')} {r.get('summary','')} {' '.join(r.get('tags',[]))}"
        # Count raw keyword hits
        text_lower = combined.lower()
        for kw in SKILL_MAP:
            if kw in text_lower:
                raw_keyword_counts[kw] += 1
        # Map to standards
        skills = map_skill(combined)
        for std, cat, parent, lifecycle, conf in skills:
            if std not in all_skills:
                all_skills[std] = {"skill_name": std, "frequency": 0, "source_count": 0, "category": cat, "skill_standard": std, "confidence": conf, "parent": parent, "lifecycle": lifecycle}
            all_skills[std]["frequency"] += 1
            all_skills[std]["source_count"] = all_skills[std].get("source_count", 0) + 1

    # 6. 生成 skill_candidates.csv
    candidates = sorted(all_skills.values(), key=lambda x: -x["frequency"])
    OUT_SKILL = os.path.join(BASE, "data", "clean", "skill_candidates.csv")
    os.makedirs(os.path.dirname(OUT_SKILL), exist_ok=True)
    with open(OUT_SKILL, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["skill_name", "frequency", "source_count", "category", "skill_standard", "confidence", "parent", "lifecycle"])
        w.writeheader()
        w.writerows(candidates)
    print(f"\n技能词数量: {len(candidates)} (>=500: {'OK' if len(candidates) >= 500 else '需补充'})")

    # 7. 生成 skill_ontology.json
    ontology = {}
    for s in candidates:
        ontology[s["skill_name"]] = {
            "standard_name": s["skill_standard"],
            "category": s["category"],
            "parent_skill": s.get("parent"),
            "lifecycle_stage": s.get("lifecycle", "growth"),
        }
    OUT_ONT = os.path.join(BASE, "data", "meta", "skill_ontology.json")
    os.makedirs(os.path.dirname(OUT_ONT), exist_ok=True)
    with open(OUT_ONT, "w", encoding="utf-8") as f:
        json.dump(ontology, f, ensure_ascii=False, indent=2)

    # 8. 统计
    total_keywords = len(raw_keyword_counts)
    skill_coverage = sum(1 for r in merged if map_skill(f"{r.get('tech_name','')} {r.get('summary','')}"))
    dup_rate = round((len(all_tech) - len(merged)) / max(1, len(all_tech)) * 100, 1)
    print(f"\n最终统计:")
    print(f"  技术数据数量: {len(merged)}")
    print(f"  GitHub 项目: {len(github_records)}")
    print(f"  技能词数量(标准): {len(candidates)}")
    print(f"  技能词数量(原始关键词): {total_keywords}")
    print(f"  技能映射覆盖率: {skill_coverage}/{len(merged)}")
    print(f"  重复率: {dup_rate}%")
    print(f"  输出: {OUT_SKILL}")
    print(f"  输出: {OUT_ONT}")


if __name__ == "__main__":
    raise SystemExit("Retired: this script overwrites evidence-based ontology lifecycle data.")
