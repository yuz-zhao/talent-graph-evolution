#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from crawler.utils.encoding_quality import mojibake_matches

sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCAN_ROOTS = (ROOT / "crawler/config", ROOT / "crawler/data/gold", ROOT / "knowledge_graph/import")
EXTENSIONS = {".json", ".jsonl", ".csv", ".md", ".yml", ".yaml"}


def main() -> int:
    files = sorted(path for base in SCAN_ROOTS for path in base.rglob("*") if path.is_file() and path.suffix.lower() in EXTENSIONS)
    failures = []
    for path in files:
        raw = path.read_bytes()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError as error:
            failures.append({"file": path.relative_to(ROOT).as_posix(), "type": "invalid_utf8", "reason": str(error)})
            continue
        matches = mojibake_matches(text)
        if matches:
            failures.append({"file": path.relative_to(ROOT).as_posix(), "type": "mojibake", "matches": matches})
        if path.suffix.lower() == ".jsonl":
            for line_number, line in enumerate(text.splitlines(), 1):
                if not line.strip():
                    continue
                try:
                    json.loads(line)
                except json.JSONDecodeError as error:
                    failures.append({"file": path.relative_to(ROOT).as_posix(), "type": "malformed_jsonl", "line": line_number, "reason": str(error)})
    report = {"audit_version": "utf8_integrity_v1", "passed": not failures, "files_scanned": len(files), "failures": failures}
    out = ROOT / "crawler/data/reports/utf8_integrity_report.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
