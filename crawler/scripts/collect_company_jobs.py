"""采集企业官方公开 ATS 技术岗位并直接合并到岗位主 CSV。

默认目标约 500 条，只写 ``data/silver/jobs/jd_clean.csv``，不创建 Excel。
来源是企业官方招聘页使用的 Greenhouse 公开 Job Board API。
"""

from __future__ import annotations

import argparse
import os
import sys
from itertools import zip_longest
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from config.settings import JD_CLEAN_CSV, JD_FIELDS
from config.urls import GREENHOUSE_BOARDS
from spiders.greenhouse_spider import GreenhouseSpider
from utils.collection_pipeline import CollectionStore
from utils.save_utils import load_existing_csv, merge_and_deduplicate_jobs, save_jobs_to_csv


def balanced_take(groups: list[list[dict]], target: int) -> list[dict]:
    """轮询各企业，避免 500 条数据被单个大企业垄断。"""
    selected = []
    for row in zip_longest(*groups):
        for item in row:
            if item is not None:
                selected.append(item)
                if len(selected) >= target:
                    return selected
    return selected


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="企业官网岗位增量采集")
    parser.add_argument("--target", type=int, default=500, help="本次最多采集的技术岗位数")
    parser.add_argument("--companies", default=",".join(GREENHOUSE_BOARDS.keys()))
    parser.add_argument("--output", default=JD_CLEAN_CSV)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    companies = [name.strip() for name in args.companies.split(",") if name.strip()]
    unknown = [name for name in companies if name not in GREENHOUSE_BOARDS]
    if unknown:
        raise SystemExit(f"未配置企业: {', '.join(unknown)}")
    if args.target <= 0:
        raise SystemExit("--target 必须大于 0")

    spider = GreenhouseSpider()
    groups = []
    for company in companies:
        jobs = spider.fetch_company_jobs(company, GREENHOUSE_BOARDS[company])
        print(f"[{company}] 可用技术岗位 {len(jobs)} 条")
        groups.append(jobs)

    selected = balanced_take(groups, args.target)
    if not selected:
        print("未采集到岗位，主 CSV 未修改")
        return 2

    output = os.path.abspath(args.output)
    old = load_existing_csv(output)
    merged = merge_and_deduplicate_jobs(old, selected)
    actual_added = len(merged) - len(old)
    save_jobs_to_csv(output, merged, JD_FIELDS, overwrite=True)

    # 同步写入 R01 批次报告，供管理员端展示。
    store = CollectionStore(BASE / "data")
    report = store.ingest("enterprise-greenhouse", "job", selected, "public_api")

    print("\n采集完成")
    print(f"  目标数量: {args.target}")
    print(f"  采集技术岗位: {len(selected)}")
    print(f"  去重后实际新增: {actual_added}")
    print(f"  主 CSV 原数量: {len(old)}")
    print(f"  主 CSV 新数量: {len(merged)}")
    print(f"  输出文件: {output}")
    print(f"  批次编号: {report.batch_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
