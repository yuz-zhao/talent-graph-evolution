"""采集 Arbeitnow 与 Remotive 官方公开 API 的技术岗位。"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import datetime
from html import unescape
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


TECH_TITLE = re.compile(
    r"\b(?:software|data|machine learning|ml|ai|artificial intelligence|devops|cloud|cybersecurity|security|"
    r"network|backend|front[- ]?end|full[- ]?stack|platform|sre|qa|test automation|database|embedded|firmware|"
    r"systems?|solutions?)\b.{0,24}\b(?:engineer|developer|architect|scientist|analyst|specialist|consultant)\b|"
    r"\b(?:engineer|developer|architect|scientist)\b.{0,35}\b(?:software|data|ml|ai|cloud|security|platform|backend|frontend|systems?)\b|"
    r"\b(?:software engineer|data engineer|data scientist|machine learning engineer|devops engineer|site reliability engineer|"
    r"security engineer|cloud engineer|platform engineer|systems engineer|solution architect|technical lead)\b|"
    r"(?:算法|开发|数据|人工智能|大模型|云计算|云原生|安全|网络|测试|嵌入式|物联网|芯片|通信).{0,12}(?:工程师|架构师|科学家|开发|专家)",
    re.I,
)


def clean_html(value: str) -> str:
    return BeautifulSoup(unescape(value or ""), "html.parser").get_text(" ", strip=True)


def make_record(source: str, title: str, company: str, description: str, url: str,
                location: str = "", publish_time: str = "", salary: str = "",
                job_type: str = "", tags=None) -> dict:
    tag_text = " ".join(tags or [])
    text = f"{title} {description} {tag_text}"
    skills, standard_skills = identify_skills(text)
    return {
        "job_title": title, "standard_job_name": standardize_job_name(title),
        "company": company, "industry": "Technology", "location": location,
        "salary": salary, "education": "", "experience": job_type,
        "description": description[:5000], "requirements": description[:2500],
        "raw_description": description,
        "publish_time": publish_time[:10], "source_url": url, "source_name": source,
        "source_language": "en", "source_priority": "3",
        "crawl_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "skill_raw": ";".join(skills), "skill_standard": ";".join(standard_skills),
        "time_slice": get_time_slice(), "evidence_score": "0.80", "duplicate_score": "0.0",
    }


def collect_arbeitnow(target: int) -> list[dict]:
    session = requests.Session(); session.headers.update({"User-Agent": USER_AGENT})
    output, seen = [], set()
    for page in range(1, 11):
        response = session.get("https://www.arbeitnow.com/api/job-board-api", params={"page": page}, timeout=40)
        response.raise_for_status()
        items = response.json().get("data", [])
        if not items: break
        for item in items:
            title = item.get("title") or ""
            desc = clean_html(item.get("description") or "")
            if not TECH_TITLE.search(f"{title} {' '.join(item.get('tags') or [])}"): continue
            url = item.get("url") or ""
            if not url or url in seen: continue
            seen.add(url)
            created = item.get("created_at")
            published = datetime.fromtimestamp(created).strftime("%Y-%m-%d") if isinstance(created, (int, float)) else ""
            output.append(make_record("Arbeitnow", title, item.get("company_name") or "", desc, url,
                                      item.get("location") or "", published, "",
                                      ";".join(item.get("job_types") or []), item.get("tags") or []))
            if len(output) >= target: return output
        print(f"[Arbeitnow] 第{page}页，累计 {len(output)} 条")
        time.sleep(0.5)
    return output


def collect_remotive() -> list[dict]:
    response = requests.get("https://remotive.com/api/remote-jobs", timeout=40,
                            headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    output = []
    for item in response.json().get("jobs", []):
        title = item.get("title") or ""; desc = clean_html(item.get("description") or "")
        if not TECH_TITLE.search(f"{title} {' '.join(item.get('tags') or [])}"): continue
        output.append(make_record("Remotive", title, item.get("company_name") or "", desc,
                                  item.get("url") or "", item.get("candidate_required_location") or "Remote",
                                  item.get("publication_date") or "", item.get("salary") or "",
                                  item.get("job_type") or "", item.get("tags") or []))
    print(f"[Remotive] {len(output)} 条")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(description="公开远程技术招聘平台采集")
    parser.add_argument("--arbeitnow-target", type=int, default=500)
    parser.add_argument("--output", default=JD_CLEAN_CSV)
    args = parser.parse_args()
    groups = [("arbeitnow", collect_arbeitnow(args.arbeitnow_target)), ("remotive", collect_remotive())]
    old = load_existing_csv(args.output); merged = old
    for source, jobs in groups:
        merged = merge_and_deduplicate_jobs(merged, jobs)
        CollectionStore(BASE / "data").ingest(source, "job", jobs, "public_api")
    save_jobs_to_csv(args.output, merged, JD_FIELDS, overwrite=True)
    print(f"主 CSV: {len(old)} -> {len(merged)}，新增 {len(merged)-len(old)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
