"""
企业官网招聘爬虫 (模板)
=========================
采集国内企业招聘官网的岗位数据。

当前为框架模板 — 各企业招聘页面结构不同，需按实际情况定制解析逻辑。
"""

from config.settings import ensure_dirs
from config.urls import COMPANY_CAREER_URLS


class CompanySpider:
    """企业官网招聘爬虫基类"""

    def __init__(self):
        ensure_dirs()

    def fetch_jobs(self, company: str) -> list:
        """
        从企业官网采集岗位 (占位，待实现)。

        不同企业的页面结构差异较大，需分别实现解析逻辑。
        """
        url = COMPANY_CAREER_URLS.get(company, "")
        if not url:
            print(f"[{company}] 未配置 URL")
            return []
        print(f"[{company}] URL: {url} (解析逻辑待实现)")
        return []

    def run(self):
        """遍历已配置企业"""
        print("企业官网招聘爬虫 — 框架已就绪，待实现具体解析逻辑")
        for company in COMPANY_CAREER_URLS:
            jobs = self.fetch_jobs(company)
            if jobs:
                print(f"[{company}] 获取 {len(jobs)} 个岗位")
