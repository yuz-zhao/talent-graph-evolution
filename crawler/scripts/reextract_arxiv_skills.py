"""使用 v2 标准技能本体重算现有官方 arXiv 元数据的技能和证据。"""
import importlib.util
import json
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SPIDER = BASE / "spiders/tech/arxiv_spider.py"
SPEC = importlib.util.spec_from_file_location("arxiv_v2", SPIDER)
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)

for path in [BASE / "data/bronze/papers_trend.jsonl", BASE / "data/quarantine/arxiv_irrelevant.jsonl"]:
    rows = MODULE.load_jsonl(path)
    for row in rows:
        skills, evidence = MODULE.skill_evidence(row.get("title", ""), row.get("abstract", ""))
        row["inferred_skills"] = skills
        row["relationship_skills"] = [item["skill"] for item in evidence if item["source_field"] == "abstract"]
        row["skill_evidence"] = evidence
    MODULE.write_jsonl(path, rows)
    print(json.dumps({"path": str(path), "rows": len(rows)}, ensure_ascii=False))
