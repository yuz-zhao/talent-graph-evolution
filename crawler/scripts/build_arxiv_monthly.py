"""按月汇总论文数量和技能占比；不使用摘要长度作为热度。"""
import json
from collections import Counter, defaultdict
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
SOURCE = BASE / "data/bronze/papers_trend.jsonl"
OUTPUT = BASE / "data/processed/arxiv_monthly_trend.jsonl"

papers = []
if SOURCE.exists():
    for line in SOURCE.read_text(encoding="utf-8-sig").splitlines():
        try:
            papers.append(json.loads(line))
        except json.JSONDecodeError:
            pass
months = defaultdict(list)
for paper in papers:
    month = str(paper.get("published_at") or "")[:7]
    if len(month) == 7:
        months[month].append(paper)
rows = []
for month, items in sorted(months.items()):
    counts = Counter(skill for item in items for skill in (item.get("inferred_skills") or []))
    total = len(items)
    rows.append({
        "month": month, "paper_count": total,
        "skill_counts": dict(counts.most_common()),
        "skill_paper_share": {skill: round(count / total, 6) for skill, count in counts.most_common()},
        "metric_definition": "paper_count_and_share_of_papers_mentioning_skill",
    })
OUTPUT.parent.mkdir(parents=True, exist_ok=True)
with OUTPUT.open("w", encoding="utf-8") as handle:
    for row in rows:
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
print(json.dumps({"months": len(rows), "papers": len(papers)}, ensure_ascii=False))
