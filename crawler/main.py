"""
TalentGraph 爬虫模块 — 统一入口 (中文优先)
==============================================
用法:
    cd crawler
    python main.py                         # 默认: 中文优先 → 英文补充 → 合并保存
    python main.py --spider chinese        # 仅中文 (合并旧数据)
    python main.py --spider domestic       # 同 --spider chinese
    python main.py --spider greenhouse      # 仅 Greenhouse 英文
    python main.py --clean                 # 仅清洗 raw → clean
"""

import sys
import os
import csv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config.settings import JD_FIELDS, JD_RAW_CSV, JD_CLEAN_CSV, ensure_dirs
from config.urls import (
    CHINESE_COMPANY_LIST_URLS, CHINESE_COMPANY_JOB_URLS,
    CHINESE_PUBLIC_JOB_URLS,
)


def run_chinese_all() -> list:
    """运行全部中文爬虫: 列表页 + 企业详情页 + 公开详情页"""
    from spiders.chinese_job_spider import ChineseJobSpider
    spider = ChineseJobSpider()
    all_jobs = []

    has_urls = bool(CHINESE_COMPANY_LIST_URLS or CHINESE_COMPANY_JOB_URLS or CHINESE_PUBLIC_JOB_URLS)
    if not has_urls:
        print("中文 URL 为空，跳过中文爬虫。")
        return all_jobs

    # 1. 企业列表页 (priority=1)
    if CHINESE_COMPANY_LIST_URLS:
        print("\n>>> 中文企业官网列表页")
        jobs = spider.run_list_urls(CHINESE_COMPANY_LIST_URLS, "中文企业官网列表页", 1)
        all_jobs.extend(jobs)

    # 2. 企业详情页 (priority=1)
    if CHINESE_COMPANY_JOB_URLS:
        print("\n>>> 中文企业官网岗位详情页")
        jobs = spider.run_detail_urls(CHINESE_COMPANY_JOB_URLS, "中文企业官网", 1)
        all_jobs.extend(jobs)

    # 3. 公开详情页 (priority=2)
    if CHINESE_PUBLIC_JOB_URLS:
        print("\n>>> 中文公开招聘页面")
        jobs = spider.run_detail_urls(CHINESE_PUBLIC_JOB_URLS, "中文公开招聘页面", 2)
        all_jobs.extend(jobs)

    print(f"\n本次新增中文岗位: {len(all_jobs)} 条")
    return all_jobs


def run_greenhouse() -> list:
    """Greenhouse 英文补充"""
    from spiders.greenhouse_spider import GreenhouseSpider
    spider = GreenhouseSpider()
    return spider.run()


def run_company():
    from spiders.company_spider import CompanySpider
    CompanySpider().run()


def run_github():
    from spiders.github_spider import GitHubSpider
    GitHubSpider().run()


def run_tech():
    from spiders.tech_spider import TechSpider
    TechSpider().run()


def clean_existing():
    """--clean: 读取 jd_raw.csv, 清洗输出 jd_clean.csv"""
    from utils.clean_utils import normalize_job_record, sort_jobs_by_language_and_priority
    from utils.save_utils import init_csv

    if not os.path.exists(JD_RAW_CSV):
        print(f"[clean] 未找到 {JD_RAW_CSV}")
        return

    raw_rows = []
    with open(JD_RAW_CSV, "r", encoding="utf-8-sig") as f:
        raw_rows = list(csv.DictReader(f))
    print(f"读取原始数据：{len(raw_rows)} 条")

    cleaned = [normalize_job_record(r, JD_FIELDS) for r in raw_rows]
    cleaned = sort_jobs_by_language_and_priority(cleaned)

    init_csv(JD_CLEAN_CSV, JD_FIELDS)
    with open(JD_CLEAN_CSV, "w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=JD_FIELDS)
        writer.writeheader()
        writer.writerows(cleaned)

    zh = sum(1 for r in cleaned if r.get("source_language") == "zh")
    en = sum(1 for r in cleaned if r.get("source_language") == "en")
    has_skill = sum(1 for r in cleaned if r.get("skill_standard") and r["skill_standard"].strip())
    print(f"输出清洗数据：{len(cleaned)} 条")
    print(f"中文：{zh}，英文：{en}")
    print(f"技能标注：{has_skill}/{len(cleaned)}")
    print("排序：中文优先 OK")


def main():
    ensure_dirs()

    args = sys.argv

    # --update-talent-skills 模式
    if "--update-talent-skills" in args:
        from spiders.talent.github_profile_skill_spider import run as update_talent
        update_talent()
        return

    # --expand-skills 模式
    if "--expand-skills" in args:
        from scripts.expand_skill_ontology import main as expand_skills
        expand_skills()
        return

    # --prepare-review 模式
    if "--prepare-review" in args:
        from scripts.prepare_review_data import main as prepare_review
        prepare_review()
        return

    # --expand-gold-jd-review 模式
    if "--expand-gold-jd-review" in args:
        from scripts.expand_gold_jd_review import main as expand_gold_jd
        expand_gold_jd()
        return

    # --simulate-review 模式（已停用）
    if "--simulate-review" in args:
        raise SystemExit("--simulate-review 已停用；请使用透明的 AI辅助专家规则评测集。")

    # --fix-review-quality 模式：二次质量修正
    if "--fix-review-quality" in args:
        from scripts.fix_review_quality import main as fix_quality
        fix_quality()
        return

    # --refine-reasons 模式：规范化审核理由
    if "--refine-reasons" in args:
        from scripts.refine_review_reasons import main as refine_reasons
        refine_reasons()
        return

    # --check-review 模式
    if "--check-review" in args:
        from scripts.check_review_data import main as check_review
        check_review()
        return

    # --export-reviewed-assessment 模式
    if "--export-reviewed-assessment" in args:
        from scripts.export_reviewed_assessment import main as export_reviewed
        export_reviewed()
        return

    # --clean 模式
    if "--clean" in args:
        clean_existing()
        return

    # --prepare-platform-jd 模式
    if "--prepare-platform-jd" in args:
        from scripts.build_jd_dataset import main as build_dataset
        build_dataset()
        return

    # --crawl-tech 模式
    if "--crawl-tech" in args:
        from scripts.crawl_tech_trend import main as crawl_tech
        crawl_tech()
        return

    from utils.save_utils import load_existing_csv, merge_and_deduplicate_jobs, save_jobs_to_csv

    # --spider 模式
    if "--spider" in args:
        idx = args.index("--spider")
        name = args[idx + 1] if idx + 1 < len(args) else ""

        if name in ("chinese", "domestic"):
            new_jobs = run_chinese_all()
            if new_jobs:
                # 合并旧数据
                old = load_existing_csv(JD_RAW_CSV)
                print(f"已有数据: {len(old)} 条")
                merged = merge_and_deduplicate_jobs(old, new_jobs)
                zh = sum(1 for r in merged if r.get("source_language") == "zh")
                en = sum(1 for r in merged if r.get("source_language") == "en")
                save_jobs_to_csv(JD_RAW_CSV, merged, JD_FIELDS, overwrite=True)
                save_jobs_to_csv(JD_CLEAN_CSV, merged, JD_FIELDS, overwrite=True)
                print(f"合并后岗位总数：{len(merged)} 条")
                print(f"中文岗位数：{zh} 条")
                print(f"英文岗位数：{en} 条")
                print(f"输出位置：{JD_RAW_CSV}")

        elif name == "greenhouse":
            jobs = run_greenhouse()
            if jobs:
                old = load_existing_csv(JD_RAW_CSV)
                merged = merge_and_deduplicate_jobs(old, jobs)
                save_jobs_to_csv(JD_RAW_CSV, merged, JD_FIELDS, overwrite=True)
                save_jobs_to_csv(JD_CLEAN_CSV, merged, JD_FIELDS, overwrite=True)
        elif name == "company":
            run_company()
        elif name == "github":
            run_github()
        elif name == "tech":
            run_tech()
        else:
            print(f"未知爬虫: {name}。可选: chinese/domestic, greenhouse, company, github, tech")
        return

    # ============================================================
    # 默认流程: 中文优先 → 英文补充 → 合并保存
    # ============================================================
    all_new = []

    # 1. 中文岗位
    print("=" * 55)
    print("  阶段 1/3: 国内中文岗位采集")
    print("=" * 55)
    all_new.extend(run_chinese_all())

    # 2. 企业官网补充
    print("\n" + "=" * 55)
    print("  阶段 2/3: 企业官网补充")
    print("=" * 55)
    run_company()

    # 3. 英文 Greenhouse 补充
    print("\n" + "=" * 55)
    print("  阶段 3/3: 英文 Greenhouse 补充")
    print("=" * 55)
    all_new.extend(run_greenhouse())

    # 合并保存
    if all_new:
        old = load_existing_csv(JD_RAW_CSV)
        print(f"\n已有数据: {len(old)} 条")
        merged = merge_and_deduplicate_jobs(old, all_new)
        zh = sum(1 for r in merged if r.get("source_language") == "zh")
        en = sum(1 for r in merged if r.get("source_language") == "en")
        save_jobs_to_csv(JD_RAW_CSV, merged, JD_FIELDS, overwrite=True)
        save_jobs_to_csv(JD_CLEAN_CSV, merged, JD_FIELDS, overwrite=True)
        print(f"\n合并后岗位总数：{len(merged)} 条")
        print(f"中文岗位数：{zh} 条")
        print(f"英文岗位数：{en} 条")
        print(f"输出位置：{JD_RAW_CSV}")
    else:
        print("\n未采集到新岗位。")


if __name__ == "__main__":
    main()
