"""补齐现有 v2 记录的摘要来源标记，不改写真实内容。"""
import json
from pathlib import Path

PATH = Path(__file__).resolve().parents[1] / "data/bronze/blogs_trend.jsonl"
rows = [json.loads(line) for line in PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
with PATH.open("w", encoding="utf-8") as handle:
    for row in rows:
        if row.get("rss_summary"):
            row["summary_origin"] = "publisher_meta" if row.get("rss_raw", {}).get("source_mode") == "official_html_index" else "rss"
        else:
            row["summary_origin"] = ""
        row["summary_model"] = ""
        row["summary_evidence"] = ""
        handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
print(json.dumps({"rows": len(rows), "generated_summaries": 0}, ensure_ascii=False))
