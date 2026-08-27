"""Audit the live gold layer and prove every record links to its bronze batch."""
from __future__ import annotations

import json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE / "data"


def read_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                rows.append(json.loads(line))
    return rows


def main() -> int:
    bronze_cache: dict[str, set[str]] = {}
    errors: list[dict] = []
    source_results = []
    total = 0
    for gold_path in sorted((ROOT / "gold" / "records").glob("*.jsonl")):
        rows = read_jsonl(gold_path)
        total += len(rows)
        source_errors = 0
        for row in rows:
            batch_id = row.get("bronze_batch_id")
            bronze_id = row.get("bronze_record_id")
            if not batch_id or not bronze_id or not row.get("crawl_batch_id"):
                errors.append({"gold": gold_path.name, "record_id": row.get("record_id"), "error": "missing_lineage"})
                source_errors += 1
                continue
            if batch_id not in bronze_cache:
                bronze_path = ROOT / "bronze" / "collection" / f"{batch_id}.jsonl"
                bronze_cache[batch_id] = ({r.get("bronze_record_id") for r in read_jsonl(bronze_path)}
                                           if bronze_path.exists() else set())
            if bronze_id not in bronze_cache[batch_id]:
                errors.append({"gold": gold_path.name, "record_id": row.get("record_id"), "error": "bronze_not_found"})
                source_errors += 1
        source_results.append({"gold_file": gold_path.name, "records": len(rows), "lineage_errors": source_errors})
    invalid_live_names = [str(p.relative_to(ROOT)) for folder in ("gold/records", "bronze/collection", ".ops/collection/state", ".ops/collection/batches", "reports/collection")
                          for p in (ROOT / folder).glob("-_*" )]
    report = {
        "schema_version": "2.0.0",
        "gold_records": total,
        "gold_files": len(source_results),
        "traceable_records": total - len(errors),
        "traceability_rate": round((total - len(errors)) / total, 6) if total else 1.0,
        "invalid_live_names": invalid_live_names,
        "passed": not errors and not invalid_live_names,
        "sources": source_results,
        "errors": errors[:100],
    }
    output = ROOT / "reports" / "collection_v2_lineage_report.json"
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
