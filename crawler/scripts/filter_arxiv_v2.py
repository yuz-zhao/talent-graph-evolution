"""按 v2 最终规则重新分流已由官方 API 获取的论文。"""
import importlib.util
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
PATH = BASE / "spiders/tech/arxiv_spider.py"
SPEC = importlib.util.spec_from_file_location("arxiv_v2", PATH)
M = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = M
SPEC.loader.exec_module(M)

all_rows = {row["arxiv_id"]: row for path in [M.OUTPUT, M.QUARANTINE] for row in M.load_jsonl(path)}
formal, isolated = [], []
for row in all_rows.values():
    relevant = row.get("primary_category") in M.ALLOWED_CATEGORIES
    keywords = bool(M.DOMAIN_TERMS.search(f"{row.get('title', '')} {row.get('abstract', '')}"))
    (formal if relevant and keywords else isolated).append(row)
formal.sort(key=lambda row: (row.get("published_at", ""), row["arxiv_id"]), reverse=True)
isolated.sort(key=lambda row: row["arxiv_id"])
M.write_jsonl(M.OUTPUT, formal)
M.write_jsonl(M.QUARANTINE, isolated)
print({"formal": len(formal), "isolated": len(isolated)})
