"""采集国家大学生就业服务平台公开技术职位并合并到岗位主 CSV。"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from datetime import datetime
from pathlib import Path

import requests

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from config.settings import JD_CLEAN_CSV, JD_FIELDS, USER_AGENT
from utils.clean_utils import get_time_slice
from utils.collection_pipeline import CollectionStore
from utils.job_standardize import standardize_job_name
from utils.save_utils import load_existing_csv, merge_and_deduplicate_jobs, save_jobs_to_csv
from utils.skill_mapping import identify_skills


API = "https://yapt.ncss.cn/student/jobs/jobslist/ajax/"
DETAIL = "https://yapt.ncss.cn/student/jobs/{job_id}/detail.html"
CATEGORIES = {
    "01": "计算机/网络/技术类",
    "02": "电子/电器/通信技术类",
}
TARGET_AREAS = {
    "南京": "320100",
    "苏州": "320500",
    "合肥": "340100",
    "武汉": "420100",
    "西安": "610100",
    "沈阳": "210100",
    "大连": "210200",
    "长春": "220100",
    "哈尔滨": "230100",
    "大庆": "230600",
}
TARGETED_RESULTS: dict[str, dict] = {}
NEW_IT_TITLE = re.compile(
    r"人工智能|AI|AIGC|大模型|算法|机器学习|深度学习|数据|软件|程序|开发|前端|后端|全栈|"
    r"云计算|云原生|运维|DevOps|SRE|测试开发|自动化测试|网络安全|信息安全|网络工程|"
    r"嵌入式|物联网|边缘计算|电子信息|通信|5G|芯片|集成电路|FPGA|硬件|单片机|"
    r"工业互联网|数字孪生|PLC|CNC|SMT|机器人|计算机视觉|图像识别|信息系统|数字化",
    re.I,
)


def date_from_ms(value) -> str:
    try:
        return datetime.fromtimestamp(int(value) / 1000).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def job_from_item(item: dict, location_override: str = "") -> dict | None:
    """把公开列表记录转换为岗位 v2 输入，不生成网页未公开的信息。"""
    job_id = str(item.get("jobId") or "").strip()
    title = str(item.get("jobName") or "").strip()
    if not job_id or not title or not NEW_IT_TITLE.search(title):
        return None
    company = str(item.get("recName") or "").strip()
    major = str(item.get("major") or "").strip()
    tags = str(item.get("recTags") or "").strip()
    text = " ".join(x for x in (title, major, tags) if x)
    raw_skills, std_skills = identify_skills(text)
    low, high = item.get("lowMonthPay"), item.get("highMonthPay")
    salary = f"{low:g}K-{high:g}K" if isinstance(low, (int, float)) and isinstance(high, (int, float)) else ""
    description = f"岗位：{title}。招聘单位：{company}。专业要求：{major or '不限'}。福利标签：{tags or '未注明'}。"
    publish_time = date_from_ms(item.get("publishDate"))
    return {
        "job_title": title,
        "standard_job_name": standardize_job_name(title),
        "company": company,
        "industry": "新一代信息技术",
        # 接口在按城市查询时有时仍只返回省名；此时保留查询城市作为可审计的筛选口径。
        "location": location_override or str(item.get("areaCodeName") or ""),
        "salary": salary,
        "education": str(item.get("degreeName") or ""),
        "experience": "应届生/实习",
        "description": description,
        "requirements": major,
        "publish_time": publish_time,
        "publish_time_source": "source_list" if publish_time else "missing",
        "source_url": DETAIL.format(job_id=job_id),
        "source_name": "国家大学生就业服务平台",
        "source_language": "zh",
        "source_priority": "2",
        "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "skill_raw": ";".join(raw_skills),
        "skill_standard": ";".join(std_skills),
        "time_slice": get_time_slice(),
        "evidence_score": "0.85",
        "duplicate_score": "0.0",
        "raw_description": description,
        "requirements_source": "source_list" if major else "missing",
        "company_type": str(item.get("recProperty") or "未知"),
        "company_type_source": "source_list" if item.get("recProperty") else "unverified",
        "data_provenance": "observed",
        "is_synthetic": "false",
    }


def fetch_jobs(target: int, delay: float = 0.35) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": "https://yapt.ncss.cn/student/jobs/index.html"})
    seen, output = set(), []

    for category_code, category_name in CATEGORIES.items():
        if len(output) >= target:
            break
        offset = 1
        while len(output) < target:
            params = {"categoryCode": category_code, "offset": offset, "limit": 20}
            response = session.get(API, params=params, timeout=30)
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data") or {}
            items = data.get("list") or []
            if not items:
                break
            for item in items:
                job_id = str(item.get("jobId") or "").strip()
                if not job_id or job_id in seen:
                    continue
                seen.add(job_id)
                row = job_from_item(item)
                if not row:
                    continue
                output.append(row)
                if len(output) >= target:
                    break
            pagination = data.get("pagenation") or {}
            limit = int(pagination.get("limit") or 20)
            total_pages = int(pagination.get("total") or 0)
            current_page = ((offset - 1) // max(limit, 1)) + 1
            print(f"[{category_name}] 第{current_page}页，累计 {len(output)} 条")
            if len(output) >= target:
                break
            if total_pages and current_page >= total_pages:
                break
            # 该公开接口的 offset 实际按页号处理；部分分类仅开放第一页。
            offset += 1
            time.sleep(delay)
    return output


def fetch_targeted_jobs(per_city: int = 30, max_pages: int = 10, delay: float = 0.2) -> list[dict]:
    """按重点城市执行真实岗位配额采集；公开结果不足时不虚构补齐。"""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": "https://yapt.ncss.cn/student/jobs/index.html"})
    output, seen = [], set()
    TARGETED_RESULTS.clear()
    for city, area_code in TARGET_AREAS.items():
        city_rows = []
        for category_code, category_name in CATEGORIES.items():
            for page in range(1, max_pages + 1):
                params = {
                    "jobType": "", "areaCode": area_code, "jobName": "", "monthPay": "",
                    "industrySectors": "", "property": "", "categoryCode": category_code,
                    "memberLevel": "", "recruitType": "", "offset": page, "limit": 20,
                    "keyUnits": "", "degreeCode": "", "sourcesName": "", "sourcesType": "",
                }
                response = session.get(API, params=params, timeout=30)
                response.raise_for_status()
                data = (response.json().get("data") or {})
                items = data.get("list") or []
                for item in items:
                    job_id = str(item.get("jobId") or "").strip()
                    if not job_id or job_id in seen:
                        continue
                    row = job_from_item(item, location_override=city)
                    if not row:
                        continue
                    seen.add(job_id)
                    city_rows.append(row)
                    if len(city_rows) >= per_city:
                        break
                if len(city_rows) >= per_city or not items:
                    break
                pagination = data.get("pagenation") or {}
                if int(pagination.get("total") or 0) <= page:
                    break
                time.sleep(delay)
            print(f"[{city}/{category_name}] 当前命中 {len(city_rows)} 条")
            if len(city_rows) >= per_city:
                break
        output.extend(city_rows)
        TARGETED_RESULTS[city] = {
            "found": len(city_rows),
            "quota": per_city,
            "gap": max(0, per_city - len(city_rows)),
        }
        print(f"[{city}] 配额 {per_city}，公开结果 {len(city_rows)} 条")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="采集国家大学生就业服务平台技术岗位")
    parser.add_argument("--target", type=int, default=1000)
    parser.add_argument("--targeted", action="store_true", help="按重点城市执行配额采集")
    parser.add_argument("--per-city", type=int, default=30)
    parser.add_argument("--max-pages", type=int, default=10)
    parser.add_argument("--delay", type=float, default=0.2)
    parser.add_argument(
        "--targeted-report",
        default=str(BASE / "data/reports/jd_targeted_collection_report.json"),
    )
    parser.add_argument("--output", default=JD_CLEAN_CSV)
    args = parser.parse_args()
    jobs = (
        fetch_targeted_jobs(args.per_city, args.max_pages, args.delay)
        if args.targeted else fetch_jobs(args.target, args.delay)
    )
    if not jobs:
        print("未采集到岗位，主 CSV 未修改")
        return 2
    old = load_existing_csv(args.output)
    merged = merge_and_deduplicate_jobs(old, jobs)
    save_jobs_to_csv(args.output, merged, JD_FIELDS, overwrite=True)
    if args.targeted:
        added = len(merged) - len(old)
        report_path = Path(args.targeted_report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps({
            "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
            "source": "国家大学生就业服务平台",
            "mode": "city_quota",
            "scope": "china_main",
            "quota_per_city": args.per_city,
            "city_results": TARGETED_RESULTS,
            "summary": {
                "found": len(jobs), "added": added,
                "main_csv_before": len(old), "main_csv_after": len(merged),
                "synthetic_added": 0,
            },
            "conclusion": "公开结果不足时保留配额缺口，不使用无关岗位或合成数据补齐。",
        }, ensure_ascii=False, indent=2), encoding="utf-8")
    report = CollectionStore(BASE / "data").ingest(
        "ncss", "job", jobs, "public_platform"
    )
    print(f"采集 {len(jobs)} 条，去重后新增 {len(merged)-len(old)} 条")
    print(f"主 CSV: {len(old)} -> {len(merged)}")
    print(f"批次: {report.batch_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
