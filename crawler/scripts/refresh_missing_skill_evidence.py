"""只重算缺少标准技能的岗位，适用于技能词典增量更新后的快速修复。"""

from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from config.settings import JD_CLEAN_CSV, JD_FIELDS
from utils.clean_utils import normalize_job_record
from utils.save_utils import load_existing_csv


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", default=JD_CLEAN_CSV)
    args = parser.parse_args()
    rows = load_existing_csv(args.csv)
    updated = 0
    for index, row in enumerate(rows):
        if row.get("statistics_scope") != "china_main" or row.get("skill_standard"):
            continue
        refreshed = normalize_job_record(row, JD_FIELDS)
        if refreshed.get("skill_standard"):
            rows[index] = refreshed
            updated += 1
    target = Path(args.csv)
    temp = target.with_suffix(target.suffix + ".tmp")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=JD_FIELDS)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in JD_FIELDS} for row in rows)
    temp.replace(target)
    print(f"补齐标准技能及原文证据：{updated} 条")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
