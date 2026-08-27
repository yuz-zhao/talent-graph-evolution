"""将受控技能词表同步到本体 JSON 和 Neo4j 技能节点 CSV。"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "crawler"))

from utils.skill_mapping import SKILL_ALIASES  # noqa: E402


CATEGORY_MEMBERS = {
    "Frontend": {"HTML/CSS", "React", "Vue.js", "Angular", "Next.js", "Nuxt.js", "Svelte", "Redux", "Webpack", "Vite", "Android", "iOS", "Flutter", "React Native", "Electron", "前端开发"},
    "AI": {"人工智能", "机器学习", "深度学习", "自然语言处理", "计算机视觉", "大语言模型", "检索增强生成", "AI智能体", "知识图谱", "推荐系统", "强化学习", "迁移学习", "联邦学习", "多模态学习", "提示词工程", "模型微调", "模型部署", "MLOps", "RLHF", "OCR", "目标检测", "语音识别", "PyTorch", "TensorFlow", "Keras", "Scikit-learn", "Transformers", "LangChain", "LlamaIndex", "OpenCV", "YOLO", "数据标注"},
    "Data": {"SQL", "R语言", "MATLAB", "数据分析", "统计分析", "实时计算", "数据挖掘", "数据建模", "数据治理", "数据质量", "数据架构", "数据仓库", "数据湖", "ETL", "商业智能", "Hadoop", "Spark", "Flink", "Hive", "Airflow", "dbt", "Pandas", "NumPy", "Excel"},
    "Database": {"MySQL", "PostgreSQL", "MongoDB", "Redis", "Elasticsearch", "Oracle", "SQL Server", "SQLite", "ClickHouse", "Doris", "Neo4j", "向量数据库", "Milvus", "FAISS", "Pinecone"},
    "Cloud": {"云计算", "AWS", "Azure", "GCP", "阿里云", "腾讯云", "华为云", "Microsoft 365", "Serverless"},
    "DevOps": {"Docker", "Kubernetes", "Linux", "Git", "GitHub Actions", "GitLab CI", "Jenkins", "CI/CD", "Terraform", "Ansible", "Nginx", "Prometheus", "Grafana", "Helm", "Argo CD", "DevOps", "SRE"},
    "Security": {"网络安全", "信息安全", "渗透测试", "漏洞评估", "安全审计", "身份与访问管理", "零信任", "SIEM"},
    "IoT": {"嵌入式开发", "物联网", "PLC", "单片机", "STM32", "ARM", "FPGA", "PCB设计", "RTOS", "ROS", "CAN总线", "Modbus", "MQTT", "自动化控制", "机器人技术", "工业机器人", "CNC", "SMT", "硬件开发", "电路设计", "电气控制", "设备验证", "系统调试", "工艺设计", "试验验证", "模具设计", "制冷技术", "自动驾驶"},
}


def category_for(skill: str) -> str:
    for category, members in CATEGORY_MEMBERS.items():
        if skill in members:
            return category
    return "Backend"


def main() -> None:
    ontology_path = ROOT / "crawler/data/gold/reference/skill_ontology.json"
    nodes_path = ROOT / "knowledge_graph/import/nodes_skill.csv"
    ontology = json.loads(ontology_path.read_text(encoding="utf-8"))

    added_ontology = 0
    for standard, aliases in SKILL_ALIASES.items():
        entry = ontology.get(standard)
        if entry is None:
            entry = {
                "standard_name": standard,
                "aliases": list(dict.fromkeys(a for a in aliases if a.casefold() != standard.casefold())),
                "category": category_for(standard), "parent_skill": "", "lifecycle_stage": "mature",
                "_source": "curated_multilingual",
            }
            ontology[standard] = entry
            added_ontology += 1
        else:
            merged = list(dict.fromkeys([*entry.get("aliases", []), *aliases]))
            entry["aliases"] = merged
    ontology_path.write_text(json.dumps(ontology, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    with nodes_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    known = {row["name"] for row in rows}
    last_id = max((int(re.search(r"(\d+)$", row["skill_id:ID"]).group(1)) for row in rows), default=0)
    added_nodes = 0
    for standard, aliases in SKILL_ALIASES.items():
        if standard in known:
            continue
        last_id += 1
        rows.append({
            "skill_id:ID": f"SKILL_{last_id:05d}", "name": standard,
            "aliases": ";".join(dict.fromkeys(aliases)), "category": category_for(standard),
            "parent_skill": "", "lifecycle": "mature", "source_type": "curated_multilingual",
        })
        known.add(standard)
        added_nodes += 1
    with nodes_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    print(f"ontology_added={added_ontology} nodes_added={added_nodes} total_standard_skills={len(SKILL_ALIASES)}")


if __name__ == "__main__":
    main()
