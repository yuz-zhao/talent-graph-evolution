"""按来源配额对岗位主 CSV 做可恢复的分层精简。"""

from __future__ import annotations

import argparse
import csv
import os
import sys
import zipfile
from collections import defaultdict, deque
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from config.settings import JD_CLEAN_CSV, JD_FIELDS
from utils.save_utils import save_jobs_to_csv


def score(row: dict) -> tuple:
    filled = sum(bool((row.get(k) or "").strip()) for k in (
        "job_title", "company", "location", "description", "requirements",
        "publish_time", "source_url", "skill_standard",
    ))
    skill_count = len([x for x in (row.get("skill_standard") or "").split(";") if x])
    return filled, min(skill_count, 12), row.get("publish_time") or ""


def stratified_keep(rows: list[dict], quota: int) -> list[dict]:
    """按标准岗位轮询，再限制相同公司+岗位，保留字段较完整记录。"""
    groups = defaultdict(list)
    for row in rows:
        key = (row.get("standard_job_name") or row.get("job_title") or "其他").strip()
        groups[key].append(row)
    queues = []
    for key, values in groups.items():
        values.sort(key=score, reverse=True)
        queues.append((key, deque(values)))
    queues.sort(key=lambda item: len(item[1]), reverse=True)

    selected, pair_counts = [], defaultdict(int)
    while len(selected) < quota and queues:
        next_round = []
        for key, queue in queues:
            chosen = None
            while queue:
                candidate = queue.popleft()
                pair = ((candidate.get("company") or "").strip(), key)
                if pair_counts[pair] < 3:
                    chosen = candidate
                    pair_counts[pair] += 1
                    break
            if chosen:
                selected.append(chosen)
                if len(selected) >= quota:
                    break
            if queue:
                next_round.append((key, queue))
        if not next_round and len(selected) < quota:
            remaining = [r for _, q in queues for r in q]
            remaining.sort(key=score, reverse=True)
            selected.extend(remaining[:quota-len(selected)])
            break
        queues = next_round
    return selected[:quota]


def main() -> int:
    parser = argparse.ArgumentParser(description="岗位来源分层精简")
    parser.add_argument("--source", required=True)
    parser.add_argument("--quota", type=int, required=True)
    parser.add_argument("--file", default=JD_CLEAN_CSV)
    args = parser.parse_args()
    path = Path(args.file).resolve()

    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    target = [r for r in rows if (r.get("source_name") or "").strip() == args.source]
    others = [r for r in rows if (r.get("source_name") or "").strip() != args.source]
    if len(target) <= args.quota:
        print(f"{args.source} 当前仅 {len(target)} 条，无需精简")
        return 0

    backup_dir = BASE / "data/backup"
    backup_dir.mkdir(parents=True, exist_ok=True)
    backup = backup_dir / f"jd_clean_before_rebalance_{datetime.now():%Y%m%d_%H%M%S}.zip"
    with zipfile.ZipFile(backup, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.write(path, arcname=path.name)

    kept = stratified_keep(target, args.quota)
    save_jobs_to_csv(str(path), others + kept, JD_FIELDS, overwrite=True)
    print(f"来源: {args.source}")
    print(f"精简前: {len(target)}")
    print(f"保留: {len(kept)}")
    print(f"移除: {len(target)-len(kept)}")
    print(f"全表: {len(rows)} -> {len(others)+len(kept)}")
    print(f"恢复备份: {backup}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

