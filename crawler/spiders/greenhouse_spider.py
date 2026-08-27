"""
Greenhouse 企业招聘爬虫 — 英文补充数据源
============================================
从 Greenhouse ATS 公开 API 采集技术岗位数据。
source_language=en, source_priority=4
"""

import re
import time
from datetime import datetime
from config.settings import JD_FIELDS
from config.urls import GREENHOUSE_BOARDS
from utils.request_utils import safe_get
from utils.clean_utils import clean_text, get_time_slice
from utils.skill_mapping import identify_skills
from utils.job_standardize import standardize_job_name


class GreenhouseSpider:
    """Greenhouse 招聘爬虫 — 英文补充"""

    def __init__(self):
        pass

    def fetch_company_jobs(self, company: str, api_url: str) -> list:
        """从 Greenhouse API 获取单个企业技术岗位"""
        print(f"\n[{company}] {api_url[:80]}")
        resp = safe_get(api_url)
        if resp is None:
            return []

        try:
            data = resp.json()
        except Exception as e:
            print(f"  JSON 解析失败: {e}")
            return []

        jobs_raw = data.get("jobs", [])
        print(f"  API 返回 {len(jobs_raw)} 个岗位")

        tech_kw = [
            "engineer", "developer", "architect", "scientist",
            "analyst", "sre", "devops", "security", "data",
            "ml", "ai", "cloud", "platform", "backend", "frontend",
        ]
        results = []
        for j in jobs_raw:
            title = (j.get("title") or "").lower()
            if not any(kw in title for kw in tech_kw):
                continue

            desc_raw = j.get("content", "")
            desc_clean = clean_text(desc_raw)

            loc = j.get("location", {})
            if isinstance(loc, dict):
                loc = loc.get("name", "")

            skills, standard_skills = identify_skills(f"{title} {desc_clean}")
            skill_raw = ";".join(skills)
            skill_std = ";".join(standard_skills)

            record = {
                "job_title": j.get("title", ""),
                "standard_job_name": standardize_job_name(j.get("title", "")),
                "company": company.title(),
                "industry": "Technology",
                "location": str(loc),
                "salary": "",
                "education": "",
                "experience": "",
                "description": desc_clean[:2000],
                "raw_description": desc_clean,
                "requirements": ";".join(skills[:10]),
                "publish_time": (j.get("updated_at") or "")[:10],
                "source_url": j.get("absolute_url", ""),
                "source_name": "Greenhouse",
                "source_language": "en",
                "source_priority": "4",
                "crawl_time": datetime.now().strftime("%Y-%m-%d"),
                "skill_raw": skill_raw,
                "skill_standard": skill_std,
                "time_slice": get_time_slice(),
                "evidence_score": "0.75",
                "duplicate_score": "0.0",
            }
            results.append(record)

        print(f"  技术岗位: {len(results)}")
        return results

    def run(self, companies: list = None) -> list:
        if companies is None:
            companies = list(GREENHOUSE_BOARDS.keys())
        all_jobs = []
        for company in companies:
            url = GREENHOUSE_BOARDS.get(company)
            if not url:
                continue
            jobs = self.fetch_company_jobs(company, url)
            all_jobs.extend(jobs)
            time.sleep(3)
        print(f"\nGreenhouse 总计: {len(all_jobs)}")
        return all_jobs
