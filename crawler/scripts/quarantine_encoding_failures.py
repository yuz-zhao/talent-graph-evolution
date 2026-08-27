#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from crawler.utils.encoding_quality import mojibake_matches

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

GOLD = ROOT / "crawler/data/gold/records"
QUARANTINE = ROOT / "crawler/data/quarantine/encoding"


def main() -> int:
    QUARANTINE.mkdir(parents=True, exist_ok=True)
    summary = {}
    for path in sorted(GOLD.glob("*.jsonl")):
        kept, rejected = [], []
        for line_number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError as error:
                rejected.append({
                    "quarantined_at": datetime.now(timezone.utc).isoformat(),
                    "quarantine_reason": "malformed_jsonl",
                    "source_file": path.relative_to(ROOT).as_posix(),
                    "source_line": line_number,
                    "matches": [{"pattern": "malformed_jsonl", "sample": str(error)}],
                    "raw_line": line,
                })
                continue
            matches = mojibake_matches(json.dumps(record, ensure_ascii=False))
            if matches:
                rejected.append({
                    "quarantined_at": datetime.now(timezone.utc).isoformat(),
                    "quarantine_reason": "mojibake_detected",
                    "source_file": path.relative_to(ROOT).as_posix(),
                    "source_line": line_number,
                    "matches": matches,
                    "record": record,
                })
            else:
                kept.append(record)
        if not rejected:
            continue
        destination = QUARANTINE / path.name
        existing = []
        if destination.exists():
            existing = [json.loads(line) for line in destination.read_text(encoding="utf-8").splitlines() if line.strip()]
        known = {item.get("record", {}).get("record_id") for item in existing if item.get("record")}
        additions = [item for item in rejected if item.get("record", {}).get("record_id") not in known or item.get("quarantine_reason") == "malformed_jsonl"]
        destination.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in [*existing, *additions]), encoding="utf-8")
        path.write_text("".join(json.dumps(item, ensure_ascii=False) + "\n" for item in kept), encoding="utf-8")
        summary[path.name] = {"kept": len(kept), "quarantined": len(rejected), "new_quarantine_records": len(additions)}
    print(json.dumps({"quarantine_version": "encoding_quarantine_v1", "files": summary, "quarantined_total": sum(x["quarantined"] for x in summary.values())}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
