"""
GitHub 技术趋势爬虫 (模板)
============================
从 GitHub Search API 采集开源项目数据。

API: GET https://api.github.com/search/repositories?q={query}&sort=stars
"""

import time
from config.settings import ensure_dirs
from config.urls import GITHUB_SEARCH_API
from utils.request_utils import build_headers, safe_get
from utils.save_utils import save_jsonl


class GitHubSpider:
    """GitHub 仓库爬虫"""

    def __init__(self):
        ensure_dirs()

    def search_repos(self, query: str, per_page: int = 30, max_pages: int = 5) -> list:
        """
        搜索 GitHub 仓库。

        Args:
            query:     搜索关键词 (如 "LLM+agent+framework")
            per_page:  每页条数
            max_pages: 最大页数

        Returns:
            仓库数据列表
        """
        results = []
        for page in range(1, max_pages + 1):
            params = {
                "q": query,
                "sort": "stars",
                "order": "desc",
                "per_page": per_page,
                "page": page,
            }
            # GitHub API 建议带 Accept 头
            headers = {"Accept": "application/vnd.github.v3+json"}
            resp = safe_get(GITHUB_SEARCH_API, params=params, headers=headers)
            if resp is None:
                break

            data = resp.json()
            items = data.get("items", [])
            if not items:
                break

            for item in items:
                results.append({
                    "tech_name": item.get("name", ""),
                    "summary": (item.get("description") or "").strip(),
                    "tags": item.get("topics", []),
                    "source_url": item.get("html_url", ""),
                    "stars": item.get("stargazers_count", 0),
                    "language": item.get("language", ""),
                    "publish_time": (item.get("updated_at") or "")[:10],
                    "crawl_time": time.strftime("%Y-%m-%d"),
                })

            print(f"  page {page}: +{len(items)} (累计 {len(results)})")
            time.sleep(3)

        return results

    def run(self):
        """运行 GitHub 采集 (示例查询)"""
        queries = [
            "LLM+agent+framework",
            "RAG+retrieval+augmented",
            "deep+learning+framework",
        ]
        all_results = []
        for q in queries:
            print(f"\n搜索: {q}")
            repos = self.search_repos(q, per_page=20, max_pages=2)
            all_results.extend(repos)

        if all_results:
            from config.settings import GITHUB_RAW_JSONL
            save_jsonl(all_results, GITHUB_RAW_JSONL)

        print(f"\n总计: {len(all_results)} 个仓库")
        return len(all_results)
