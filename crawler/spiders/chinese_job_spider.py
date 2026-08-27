"""
中文岗位爬虫 — 支持列表页提取 + 详情页解析
==============================================
从国内企业招聘页面采集中文 JD 数据。
"""

import re
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
from config.settings import JD_FIELDS
from utils.request_utils import safe_get
from utils.clean_utils import clean_text, get_time_slice
from utils.skill_mapping import identify_skills
from utils.job_standardize import standardize_job_name

# 岗位详情链接关键词
JOB_LINK_KEYWORDS = [
    "job", "jobs", "position", "career", "recruit",
    "zhaopin", "campus", "social", "detail", "apply",
]


class ChineseJobSpider:
    """中文岗位爬虫"""

    def __init__(self):
        self.seen_urls = set()

# 列表页 → 提取详情链接
def extract_job_links_from_list_page(self, url: str) -> list:
        """
        从招聘列表页提取岗位详情页链接。

        Args:
            url: 列表页 URL

        Returns:
            最多 30 个岗位详情页链接 (去重, 绝对路径)
        """
        resp = safe_get(url)
        if resp is None:
            return []

        soup = BeautifulSoup(resp.text, "lxml")
        links = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag.get("href", "").strip()
            if not href or href.startswith("#") or href.startswith("javascript"):
                continue

            # 转绝对路径
            full_url = urljoin(url, href)

            # 判断是否为岗位详情链接
            href_lower = full_url.lower()
            text = a_tag.get_text(strip=True).lower()

            if any(kw in href_lower for kw in JOB_LINK_KEYWORDS):
                links.add(full_url)
            elif any(kw in text for kw in ["工程师", "经理", "开发", "算法", "数据"]):
                links.add(full_url)

        # 去重 + 限 30 条
        links = [l for l in links if l not in self.seen_urls]
        for l in links:
            self.seen_urls.add(l)

        result = list(links)[:30]
        print(f"  列表页提取 {len(result)} 个岗位详情链接")
        return result

# 详情页解析
def parse_job(self, url: str, source_name: str = "中文公开招聘页面",
                  source_priority: int = 2) -> dict:
        """
        解析单个招聘详情页，提取 JD 字段。
        """
        resp = safe_get(url)
        if resp is None:
            return {}

        soup = BeautifulSoup(resp.text, "lxml")

        # 1. 岗位标题
        title = ""
        for sel in [
            "h1", "title",
            "[class*='job-title']", "[class*='jobtitle']",
            "[class*='position-name']", "[class*='pos-name']",
            "[class*='name']", "[class*='title']",
        ]:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                title = clean_text(el.get_text())
                break
        if not title and soup.title:
            title = clean_text(soup.title.string)

        # 快速判断：不是招聘页面 (标题太短/无关键内容)
        if not title or len(title) < 2:
            body_text = soup.body.get_text() if soup.body else ""
            if "招聘" not in body_text and "岗位" not in body_text and "职位" not in body_text:
                return {}

        # 2. 公司名称
        company = ""
        for sel in [
            "[class*='company-name']", "[class*='company']",
            "[class*='corp']", "[class*='enterprise']",
            "[class*='employer']", "[class*='brand']",
        ]:
            el = soup.select_one(sel)
            if el and el.get_text(strip=True):
                company = clean_text(el.get_text())
                break

        # 3-6. 地点/薪资/学历/经验
        def _find(selectors):
            for sel in selectors:
                el = soup.select_one(sel)
                if el and el.get_text(strip=True):
                    return clean_text(el.get_text())
            return ""

        location = _find(["[class*='location']", "[class*='city']",
                          "[class*='address']", "[class*='workplace']"])
        salary = _find(["[class*='salary']", "[class*='pay']", "[class*='wage']"])
        education = _find(["[class*='education']", "[class*='degree']"])
        experience = _find(["[class*='experience']", "[class*='seniority']"])
        industry = _find(["[class*='industry']", "[class*='field']"])

        # 7. 发布时间
        publish_time = ""
        for sel in ["[class*='publish']", "[class*='date']", "[class*='time']", "time"]:
            el = soup.select_one(sel)
            if el:
                txt = el.get_text(strip=True)
                if not txt and el.get("datetime"):
                    txt = el["datetime"]
                if txt:
                    publish_time = clean_text(txt)
                    break
        if not publish_time:
            m = re.search(r"\d{4}-\d{2}-\d{2}", soup.get_text())
            if m:
                publish_time = m.group(0)

        # 8. 正文
        body = ""
        for sel in [
            "[class*='description']", "[class*='content']",
            "[class*='detail']", "[class*='job-detail']",
            "[class*='job_content']", "[class*='requirement']",
            "[class*='responsibility']", "[class*='duty']",
            "#job-content", "#job-detail", "#detail",
            "[class*='job']",
        ]:
            el = soup.select_one(sel)
            if el:
                body = clean_text(el.get_text())
                break
        if not body and soup.body:
            body = clean_text(soup.body.get_text())

        # 9. 技能
        skills, standard_skills = identify_skills(f"{title} {body}")
        skill_raw = ";".join(skills)
        skill_std = ";".join(standard_skills)

        # 10. 证据分
        evidence = "0.9" if source_priority == 1 else "0.8"

        return {
            "job_title": title,
            "standard_job_name": standardize_job_name(title),
            "company": company,
            "industry": industry,
            "location": location,
            "salary": salary,
            "education": education,
            "experience": experience,
            "description": body,
            "requirements": body,
            "publish_time": publish_time,
            "source_url": url,
            "source_name": source_name,
            "source_language": "zh",
            "source_priority": str(source_priority),
            "crawl_time": datetime.now().strftime("%Y-%m-%d"),
            "skill_raw": skill_raw,
            "skill_standard": skill_std,
            "time_slice": get_time_slice(),
            "evidence_score": evidence,
            "duplicate_score": "0.0",
        }

# 批量: 详情页
def run_detail_urls(self, urls: list, source_name: str,
                        source_priority: int) -> list:
        """遍历详情页 URL 列表，逐个解析"""
        jobs = []
        for url in urls:
            if not url or not url.startswith("http"):
                continue
            print(f"  详情页: {url[:80]}")
            job = self.parse_job(url, source_name, source_priority)
            if job.get("job_title"):
                jobs.append(job)
            time.sleep(3)
        print(f"[{source_name}] 详情页获取 {len(jobs)} 条")
        return jobs

# 批量: 列表页 → 详情页
def run_list_urls(self, urls: list, source_name: str = "中文企业官网列表页",
                      source_priority: int = 1) -> list:
        """遍历列表页，先提取详情链接，再逐个解析"""
        all_detail_urls = []
        for url in urls:
            if not url or not url.startswith("http"):
                continue
            print(f"  列表页: {url[:80]}")
            links = self.extract_job_links_from_list_page(url)
            all_detail_urls.extend(links)
            time.sleep(3)

        # 去重
        all_detail_urls = list(set(all_detail_urls))
        print(f"\n总计提取 {len(all_detail_urls)} 个唯一详情链接")
        return self.run_detail_urls(all_detail_urls, source_name, source_priority)
