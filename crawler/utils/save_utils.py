"""
数据保存工具 — CSV 读写 & 合并去重 & 规范化 & 排序
"""

import csv
import json
import os
from typing import List, Dict
from config.settings import JD_FIELDS, ensure_dirs
from utils.clean_utils import sort_jobs_by_language_and_priority, normalize_job_record


def init_csv(file_path: str, fields: list):
    """创建 CSV 并写入表头（如果不存在）"""
    ensure_dirs()
    if not os.path.exists(file_path):
        with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()


def load_existing_csv(file_path: str) -> list:
    """读取已有 CSV 数据"""
    if not os.path.exists(file_path):
        return []
    with open(file_path, "r", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def _dedup_key(record: dict) -> str:
    """去重主键: source_url > company+job_title+location"""
    url = (record.get("source_url") or "").strip()
    if url:
        return f"url:{url}"
    company = (record.get("company") or "").strip()
    title = (record.get("job_title") or "").strip()
    location = (record.get("location") or "").strip()
    return f"triple:{company}|{title}|{location}"


def merge_and_deduplicate_jobs(old_jobs: list, new_jobs: list) -> list:
    """
    合并新旧数据，按 source_url (优先) 或 company+job_title+location 去重。
    新数据优先 (相同 key 时覆盖旧数据)。
    """
    merged = {}
    for j in old_jobs:
        key = _dedup_key(j)
        if key and key not in merged:
            merged[key] = j
    for j in new_jobs:
        key = _dedup_key(j)
        if key:
            merged[key] = j
    return list(merged.values())


def save_jobs_to_csv(file_path: str, jobs: list, fields: list = None,
                     sort: bool = True, overwrite: bool = False):
    """
    保存岗位数据到 CSV。

    Args:
        file_path:  输出路径
        jobs:       岗位列表
        fields:     字段定义 (默认 JD_FIELDS)
        sort:       是否中文优先排序
        overwrite:  True=覆盖写入, False=追加写入(合并去重)
    """
    if fields is None:
        fields = JD_FIELDS
    if not jobs:
        return
    ensure_dirs()

    # 规范化
    normalized = [normalize_job_record(j, fields) for j in jobs]

    if overwrite:
        # 覆盖: 直接写入
        all_jobs = normalized
    else:
        # 追加: 读取旧数据 → 合并去重 → 写入
        old = load_existing_csv(file_path)
        all_jobs = merge_and_deduplicate_jobs(old, normalized)

    # 排序 (中文优先)
    if sort:
        all_jobs = sort_jobs_by_language_and_priority(all_jobs)

    # 写入
    with open(file_path, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(all_jobs)

    zh = sum(1 for r in all_jobs if r.get("source_language") == "zh")
    en = sum(1 for r in all_jobs if r.get("source_language") == "en")
    print(f"[save] {len(all_jobs)} 条 (zh:{zh} en:{en}) → {file_path}")


def save_jsonl(rows: list, filepath: str, dedup_key: str = "source_url"):
    """JSONL 去重追加写入"""
    os.makedirs(os.path.dirname(filepath), exist_ok=True)
    seen = set()
    if os.path.exists(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    obj = json.loads(line.strip())
                    if dedup_key in obj:
                        seen.add(obj[dedup_key])
                except json.JSONDecodeError:
                    continue
    written = 0
    with open(filepath, "a", encoding="utf-8") as f:
        for row in rows:
            key = row.get(dedup_key, "")
            if key and key in seen:
                continue
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if key:
                seen.add(key)
            written += 1
    print(f"[save] JSONL: {written} 行 → {filepath}")
