"""采集中国信息通信研究院公开招聘列表中的新一代信息技术岗位。"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path
from urllib.parse import urljoin

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

BASE_URL = "https://www.hotjob.cn"
LIST_URL = BASE_URL + "/wt/caict/web/index/webPosition210!getPostListByConditionShowPic"
MOBILE_LIST_URL = BASE_URL + "/wt/caict/mobweb/v8/position/list"
TECH = re.compile(
    r"通信|5G|6G|无线|网络|互联网|物联网|工业智能|数字化|数智|软件|数据|安全|"
    r"人工智能|AI|算法|云计算|芯片|集成电路|测试工程师|研发|技术研究|标准研究|运维",
    re.I,
)


def parse_page(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    rows = []
    for tr in soup.select("table tr"):
        link = tr.select_one("a[href*='getOnePosition'][title]")
        cells = tr.find_all("td")
        if not link or len(cells) < 5:
            continue
        title = link.get("title", "").strip()
        organization = cells[1].get("title", "").strip() or cells[1].get_text(" ", strip=True)
        location_node = cells[3].select_one("font[title]")
        location = location_node.get("title", "").strip() if location_node else cells[3].get_text(" ", strip=True)
        publish_time = cells[4].get_text(" ", strip=True)
        text = f"{title} {organization}"
        if not TECH.search(text):
            continue
        raw_skills, standard_skills = identify_skills(text)
        rows.append({
            "job_title": title,
            "standard_job_name": standardize_job_name(title),
            "company": "中国信息通信研究院",
            "industry": "信息通信技术研究（科研事业单位）",
            "location": location,
            "salary": "",
            "education": "以招聘详情页为准",
            "experience": "校园/社会/实习招聘（以原页面为准）",
            "description": f"所属机构：{organization}。岗位职责与任职条件见中国信通院官方招聘详情页。",
            "requirements": "",
            "publish_time": publish_time,
            "source_url": urljoin(BASE_URL, link.get("href", "")),
            "source_name": "中国信通院招聘官网",
            "source_language": "zh",
            "source_priority": "1",
            "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "skill_raw": ";".join(raw_skills),
            "skill_standard": ";".join(standard_skills),
            "time_slice": get_time_slice(),
            "evidence_score": "0.90",
            "duplicate_score": "0.0",
        })
    return rows


def _clean(value: str) -> str:
    return re.sub(r"\s+", " ", value or "").strip(" ：:，,。")


def _title_key(value: str) -> str:
    text = re.sub(r"(?:20\d{2})?[A-Z]{2,6}\d{2,}$", "", _clean(value), flags=re.I)
    return re.sub(r"[^a-z0-9一-龥]+", "", text.casefold())


def _relative_date(value: str, now: datetime | None = None) -> str:
    moment = now or datetime.now()
    text = _clean(value)
    if re.search(r"今天|今日|刚刚|小时|分钟", text):
        return moment.strftime("%Y-%m-%d")
    match = re.search(r"(\d+)\s*天前", text)
    return (moment - timedelta(days=int(match.group(1)))).strftime("%Y-%m-%d") if match else ""


def _mobile_field(block, label: str) -> str:
    nodes = block.select(".detailedInformation")
    for index, node in enumerate(nodes):
        text = _clean(node.get_text(" ", strip=True))
        if text.startswith(label):
            return _clean(text[len(label):])
        # 某些页面将标签渲染成独立文本节点，按出现顺序回退。
        if label == "工作描述" and index == 0:
            return re.sub(r"^工作描述\s*", "", text)
        if label == "职位要求" and index == 1:
            return re.sub(r"^职位要求\s*", "", text)
    return ""


def parse_mobile_page(html: str) -> tuple[list[dict], bool]:
    """移动端列表直接公开职责和要求，用于补全桌面列表中的岗位。"""
    soup = BeautifulSoup(html, "html.parser")
    output = []
    for item in soup.select("li.position_list-list-demo"):
        onclick = " ".join(node.get("onclick", "") for node in item.select("[onclick]"))
        id_match = re.search(r"toDetailPostUrl\((\d+)", onclick)
        title_node = item.select_one(".position_list-list-demo-title")
        first_row = item.select_one(".position_list-first-row")
        if not id_match or not title_node:
            continue
        post_id = id_match.group(1)
        title = _clean(title_node.get_text(" ", strip=True))
        spans = [_clean(node.get_text(" ", strip=True)) for node in first_row.select("span")] if first_row else []
        hidden = item.select_one(f"#hidden{post_id}") or item
        description = _mobile_field(hidden, "工作描述")
        requirements = _mobile_field(hidden, "职位要求")
        update_node = item.select_one(".position_list-list-demo-info")
        update_text = _clean(update_node.get_text(" ", strip=True)) if update_node else ""
        output.append({
            "mobile_post_id": post_id,
            "job_title": title,
            "title_key": _title_key(title),
            "organization": spans[0] if spans else "",
            "location": spans[-1] if len(spans) > 1 else "",
            "description": description,
            "requirements": requirements,
            "publish_time": _relative_date(update_text),
        })
    last = soup.select_one("input[name='lastPage']")
    return output, bool(last and last.get("value", "").lower() == "true")


def fetch_mobile_details(max_pages: int = 50, delay: float = 0.15) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": MOBILE_LIST_URL})
    output, seen, stagnant = [], set(), 0
    for page in range(1, max_pages + 1):
        params = {"brandCode": "1", "recruitType": "2"}
        if page > 1:
            params.update({"ajaxMini": "true", "pc.currentPage": page})
        response = session.get(MOBILE_LIST_URL, params=params, timeout=60)
        response.raise_for_status()
        rows, last_page = parse_mobile_page(response.text)
        before = len(output)
        for row in rows:
            if row["mobile_post_id"] not in seen:
                seen.add(row["mobile_post_id"])
                output.append(row)
        stagnant = stagnant + 1 if len(output) == before else 0
        print(f"移动端第 {page} 页：新增 {len(output)-before}，累计详情 {len(output)}")
        if last_page or stagnant >= 3:
            break
        time.sleep(delay)
    return output


def merge_mobile_details(rows: list[dict], details: list[dict]) -> tuple[list[dict], int]:
    by_key = {}
    for detail in details:
        key = detail.get("title_key") or _title_key(detail.get("job_title", ""))
        if key and key not in by_key:
            by_key[key] = detail
    changed = 0
    checked_at = datetime.now().replace(microsecond=0).isoformat()
    for row in rows:
        detail = by_key.get(_title_key(row.get("job_title", "")))
        if not detail:
            continue
        if detail.get("description"):
            row["description"] = detail["description"]
        if detail.get("requirements"):
            row["requirements"] = detail["requirements"]
            row["requirements_source"] = "source_list"
        if detail.get("publish_time"):
            row["publish_time"] = detail["publish_time"]
            row["publish_time_source"] = "relative_display"
        row["raw_description"] = "\n".join(x for x in (row.get("description", ""), row.get("requirements", "")) if x)
        row["source_url_status"] = "verified_live"
        row["source_url_checked_at"] = checked_at
        changed += 1
    return rows, changed


def fetch(max_pages: int, delay: float) -> list[dict]:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT, "Referer": LIST_URL})
    result, seen, stagnant = [], set(), 0
    for page in range(1, max_pages + 1):
        response = session.get(LIST_URL, params={"pc.currentPage": page, "pc.rowSize": 10}, timeout=40)
        response.raise_for_status()
        rows = parse_page(response.text)
        before = len(result)
        for row in rows:
            if row["source_url"] not in seen:
                seen.add(row["source_url"]); result.append(row)
        stagnant = stagnant + 1 if len(result) == before else 0
        print(f"第 {page} 页：新增 {len(result) - before}，累计 {len(result)}")
        if stagnant >= 3:
            break
        time.sleep(delay)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-pages", type=int, default=45)
    parser.add_argument("--delay", type=float, default=0.15)
    parser.add_argument("--output", default=JD_CLEAN_CSV)
    args = parser.parse_args()
    jobs = fetch(args.max_pages, args.delay)
    if not jobs:
        return 2
    try:
        mobile = fetch_mobile_details(max_pages=args.max_pages, delay=args.delay)
        jobs, enriched = merge_mobile_details(jobs, mobile)
        print(f"移动端详情成功补全 {enriched} 条")
    except requests.RequestException as exc:
        print(f"移动端详情补全失败，保留桌面列表字段: {exc}")
    old = load_existing_csv(args.output)
    merged = merge_and_deduplicate_jobs(old, jobs)
    save_jobs_to_csv(args.output, merged, JD_FIELDS, overwrite=True)
    report = CollectionStore(BASE / "data").ingest("caict-careers", "job", jobs, "official_career_page")
    print(f"采集 {len(jobs)} 条，去重后新增 {len(merged)-len(old)} 条；批次：{report.batch_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
