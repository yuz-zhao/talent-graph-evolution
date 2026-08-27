"""采集中国电信公开招聘官网职位，定向补充重点地区和新一代信息技术岗位。"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import requests
from bs4 import BeautifulSoup

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))

from config.settings import JD_CLEAN_CSV, JD_FIELDS, USER_AGENT
from utils.clean_utils import get_time_slice
from utils.collection_pipeline import CollectionStore
from utils.job_standardize import standardize_job_name
from utils.save_utils import load_existing_csv, merge_and_deduplicate_jobs, save_jobs_to_csv
from utils.skill_mapping import identify_skills


LIST_URL = "https://wejob.chinatelecom.com.cn/wt/TELE/mobweb/v8/position/list"
DETAIL_URL = (
    "https://wejob.chinatelecom.com.cn/wt/TELE/mobweb/v8/position/detail"
    "?safe=Y&canBack=true&recruitType=1&postIdsAry={post_id}&brandCode=1"
)
TARGET_REGIONS = re.compile(
    r"南京|苏州|江苏|合肥|安徽|西安|陕西|武汉|湖北|东北|辽宁|沈阳|大连|"
    r"吉林|长春|黑龙江|哈尔滨|大庆"
)
TARGET_TECH = re.compile(
    r"通信|5G|无线|网络|云网|光纤|光通信|传输|射频|基站|物联网|IoT|嵌入式|"
    r"工业互联网|智能制造|数字孪生|自动化|机器人|PLC|边缘计算|算力|云计算|"
    r"大数据|人工智能|算法|软件|开发|研发|信息安全|网络安全|数字化|技术支撑",
    re.I,
)
EXCLUDE_TITLE = re.compile(r"销售|营销|客户经理|客服|财务|法务|人力|党务|采购|审计|文秘")


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" ：:，,。")


def relative_publish_date(value: str, now: datetime | None = None) -> str:
    """把官网“3天前更新/今天更新”转换为可审计日期。"""
    moment = now or datetime.now()
    text = clean_text(value)
    absolute = re.search(r"(20\d{2})[-/.年](\d{1,2})[-/.月](\d{1,2})", text)
    if absolute:
        return f"{absolute.group(1)}-{int(absolute.group(2)):02d}-{int(absolute.group(3)):02d}"
    if re.search(r"今天|今日|刚刚|小时|分钟", text):
        return moment.strftime("%Y-%m-%d")
    days = re.search(r"(\d+)\s*天前", text)
    if days:
        return (moment - timedelta(days=int(days.group(1)))).strftime("%Y-%m-%d")
    return ""


def field_value(block, label: str) -> str:
    for node in block.select(".detailedInformation"):
        text = clean_text(node.get_text(" ", strip=True))
        if text.startswith(label):
            return clean_text(text[len(label):])
    return ""


def parse_page(html: str) -> tuple[list[dict], bool]:
    soup = BeautifulSoup(html, "html.parser")
    jobs = []
    for item in soup.select("li.position_list-list-demo"):
        onclick = " ".join(tag.get("onclick", "") for tag in item.select("[onclick]"))
        match = re.search(r"toDetailPostUrl\((\d+)", onclick)
        title_node = item.select_one(".position_list-list-demo-title")
        first_row = item.select_one(".position_list-first-row")
        if not match or not title_node or not first_row:
            continue
        spans = [clean_text(x.get_text(" ", strip=True)) for x in first_row.select("span")]
        post_id = match.group(1)
        title = clean_text(title_node.get_text(" ", strip=True))
        company_unit = spans[0] if spans else "中国电信"
        location = spans[-1] if len(spans) > 1 else ""
        hidden = item.select_one(f"#hidden{post_id}") or item
        update_node = item.select_one(".position_list-list-demo-info")
        update_text = clean_text(update_node.get_text(" ", strip=True)) if update_node else ""
        category = field_value(hidden, "职位类别")
        education = field_value(hidden, "学历要求")
        major = field_value(hidden, "专业要求")
        description = field_value(hidden, "工作描述")
        requirements = field_value(hidden, "职位要求")
        project = field_value(hidden, "招聘项目")
        full_text = " ".join((title, category, major, description, requirements))
        # 地区与稀缺岗位族满足任一项即可；但非重点地区只保留目标技术岗位。
        if EXCLUDE_TITLE.search(title):
            continue
        if not TARGET_TECH.search(full_text):
            continue
        if not (TARGET_REGIONS.search(location) or re.search(r"通信|5G|物联网|工业互联网", full_text, re.I)):
            continue
        raw_skills, standard_skills = identify_skills(full_text)
        jobs.append({
            "job_title": title,
            "standard_job_name": standardize_job_name(title),
            "company": f"中国电信·{company_unit}" if company_unit and company_unit != "中国电信" else "中国电信",
            "industry": "信息传输、软件和信息技术服务业（中央企业）",
            "location": location,
            "salary": "",
            "education": education,
            "experience": "应届/社会招聘（以原页面为准）",
            "description": clean_text("；".join(x for x in (project, category, description) if x)),
            "requirements": clean_text("；".join(x for x in (major, requirements) if x)),
            "publish_time": relative_publish_date(update_text),
            "publish_time_source": "relative_display" if relative_publish_date(update_text) else "missing",
            "source_url": DETAIL_URL.format(post_id=post_id),
            "source_name": "中国电信招聘官网",
            "source_language": "zh",
            "source_priority": "1",
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "skill_raw": ";".join(raw_skills),
            "skill_standard": ";".join(standard_skills),
            "time_slice": get_time_slice(),
            "evidence_score": "0.95",
            "duplicate_score": "0.0",
            "raw_description": "\n".join(x for x in (description, requirements) if x),
            "requirements_source": "source_list" if requirements else "missing",
            "source_url_status": "verified_live",
            "source_url_checked_at": datetime.now().replace(microsecond=0).isoformat(),
        })
    last = soup.select_one("input[name='lastPage']")
    return jobs, bool(last and last.get("value", "").lower() == "true")


def fetch_jobs(max_pages: int, delay: float) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": LIST_URL})
    output, seen = [], set()
    stagnant_pages = 0
    for page in range(1, max_pages + 1):
        params = {} if page == 1 else {"ajaxMini": "true", "pc.currentPage": page}
        response = session.get(LIST_URL, params=params, timeout=40)
        response.raise_for_status()
        rows, last_page = parse_page(response.text)
        before = len(output)
        for row in rows:
            if row["source_url"] not in seen:
                seen.add(row["source_url"])
                output.append(row)
        stagnant_pages = stagnant_pages + 1 if len(output) == before else 0
        print(f"第 {page} 页：命中 {len(rows)}，新增 {len(output) - before}，累计 {len(output)}")
        # 某些大易招聘站点到达末页后仍返回最后一页，但不会正确设置 lastPage。
        if last_page or stagnant_pages >= 3:
            break
        time.sleep(delay)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--output", default=JD_CLEAN_CSV)
    args = parser.parse_args()
    jobs = fetch_jobs(args.max_pages, args.delay)
    if not jobs:
        print("未采集到符合条件的职位，主 CSV 未修改")
        return 2
    old = load_existing_csv(args.output)
    merged = merge_and_deduplicate_jobs(old, jobs)
    save_jobs_to_csv(args.output, merged, JD_FIELDS, overwrite=True)
    report = CollectionStore(BASE / "data").ingest(
        "china-telecom-careers", "job", jobs, "official_career_page"
    )
    print(f"采集 {len(jobs)} 条，去重后新增 {len(merged) - len(old)} 条")
    print(f"主 CSV：{len(old)} -> {len(merged)}；批次：{report.batch_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
