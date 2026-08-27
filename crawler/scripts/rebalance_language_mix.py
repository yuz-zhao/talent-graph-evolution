"""将英文岗位分层压缩为国际参考集，完整保留中文岗位。"""

from __future__ import annotations

import argparse
import csv
import shutil
from collections import defaultdict
from datetime import datetime
from itertools import zip_longest
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]

from analyze_job_coverage import family_for


def quality_key(row: dict) -> tuple:
    completeness = sum(bool(str(row.get(k, "") or "").strip()) for k in (
        "source_url", "publish_time", "description", "requirements", "company",
        "location", "skill_standard",
    ))
    try:
        evidence = float(row.get("evidence_score") or 0)
    except ValueError:
        evidence = 0
    return completeness, evidence, row.get("publish_time", "")


def select_reference(rows: list[dict], target: int) -> list[dict]:
    groups: dict[tuple[str, str, str], list[dict]] = defaultdict(list)
    for row in rows:
        text = " ".join(row.get(k, "") for k in ("job_title", "standard_job_name", "description", "skill_standard"))
        key = (row.get("source_name") or "未知来源", row.get("company") or "未知企业", family_for(text))
        groups[key].append(row)
    for items in groups.values():
        items.sort(key=quality_key, reverse=True)
    selected = []
    ordered_groups = [groups[key] for key in sorted(groups)]
    for round_items in zip_longest(*ordered_groups):
        for item in round_items:
            if item is not None:
                selected.append(item)
                if len(selected) >= target:
                    return selected
    return selected


def main() -> None:
    parser = argparse.ArgumentParser(description="中文为主、英文参考集分层压缩")
    parser.add_argument("--english-target", type=int, default=500)
    parser.add_argument("--input", type=Path, default=ROOT / "crawler/data/silver/jobs/jd_clean.csv")
    args = parser.parse_args()
    path = args.input.resolve()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)
    zh = [r for r in rows if r.get("source_language") == "zh"]
    en = [r for r in rows if r.get("source_language") == "en"]
    other = [r for r in rows if r.get("source_language") not in {"zh", "en"}]
    selected_en = select_reference(en, args.english_target)
    output_rows = [*zh, *other, *selected_en]

    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = ROOT / f"crawler/data/backup/jd_clean_before_language_rebalance_{stamp}.zip"
    backup.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(backup, "w", ZIP_DEFLATED) as archive:
        archive.write(path, path.name)
    temp = path.with_suffix(".tmp.csv")
    with temp.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader(); writer.writerows(output_rows)
    shutil.move(str(temp), str(path))
    print(f"中文岗位保留 {len(zh)} 条；英文岗位 {len(en)} -> {len(selected_en)} 条；合计 {len(output_rows)} 条")
    print(f"备份: {backup}")


if __name__ == "__main__":
    main()
