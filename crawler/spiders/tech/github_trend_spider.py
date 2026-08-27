"""GitHub 仓库趋势 v2 采集器。

数据分层：
- raw/github/api/<batch_id>/：GitHub API 原始响应；
- collection/github/search_batches/<batch_id>/：按查询词保存的批次结果；
- raw/github_trend.jsonl：按 repo_id 合并的仓库主表；
- snapshots/github/<ISO周>.jsonl：可复算的周度指标快照；
- raw/github_activity.jsonl：release、tag、提交和贡献者补充信息。

缺失值保持为空。未配置 GITHUB_TOKEN 时严格遵守公开 API 限额。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests


BASE = Path(__file__).resolve().parents[2]
API = "https://api.github.com"
SEARCH_API = f"{API}/search/repositories"
TARGET_FIELDS = [
    "repo_id", "full_name", "owner", "name", "description", "html_url", "homepage",
    "created_at", "updated_at", "pushed_at", "primary_language", "topics", "license",
    "archived", "fork", "stars", "forks", "open_issues", "watchers", "default_branch",
    "observed_at", "raw_hash",
]

SEARCH_QUERIES = [
    ("llm", "large language model in:name,description stars:>500"),
    ("rag", "retrieval augmented generation in:name,description stars:>100"),
    ("agent", "AI agent framework in:name,description stars:>100"),
    ("vector_database", "vector database in:name,description stars:>100"),
    ("mlops", "MLOps in:name,description stars:>50"),
    ("cloud_native", "cloud native kubernetes in:name,description stars:>100"),
    ("data_engineering", "data engineering pipeline in:name,description stars:>100"),
    ("5g", "5G in:name,description stars:>20"),
    ("telecom", "telecom in:name,description stars:>20"),
    ("iot", "internet of things in:name,description stars:>50"),
    ("industrial_internet", "industrial internet in:name,description stars:>10"),
    ("embedded", "embedded systems in:name,description stars:>100"),
    ("smart_manufacturing", "smart manufacturing in:name,description stars:>10"),
    ("digital_twin", "digital twin in:name,description stars:>50"),
    ("edge_computing", "edge computing in:name,description stars:>50"),
    ("openharmony", "OpenHarmony in:name,description"),
    ("openeuler", "openEuler in:name,description"),
    ("mindspore", "MindSpore in:name,description"),
    ("rt_thread", "RT-Thread in:name,description"),
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def raw_hash(payload: dict) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temp.replace(path)


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    output = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            try:
                output.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return output


def repo_record(item: dict, observed_at: str) -> dict:
    license_data = item.get("license") or {}
    owner_data = item.get("owner") or {}
    values = {
        "repo_id": str(item.get("id") or ""),
        "full_name": item.get("full_name") or "",
        "owner": owner_data.get("login") or "",
        "name": item.get("name") or "",
        "description": item.get("description") or "",
        "html_url": item.get("html_url") or "",
        "homepage": item.get("homepage") or "",
        "created_at": item.get("created_at") or "",
        "updated_at": item.get("updated_at") or "",
        "pushed_at": item.get("pushed_at") or "",
        "primary_language": item.get("language") or "",
        "topics": item.get("topics") or [],
        "license": license_data.get("spdx_id") or license_data.get("name") or "",
        "archived": item.get("archived") if isinstance(item.get("archived"), bool) else "",
        "fork": item.get("fork") if isinstance(item.get("fork"), bool) else "",
        "stars": item.get("stargazers_count") if item.get("stargazers_count") is not None else "",
        "forks": item.get("forks_count") if item.get("forks_count") is not None else "",
        "open_issues": item.get("open_issues_count") if item.get("open_issues_count") is not None else "",
        "watchers": item.get("subscribers_count") if item.get("subscribers_count") is not None else item.get("watchers_count", ""),
        "default_branch": item.get("default_branch") or "",
        "observed_at": observed_at,
        "raw_hash": raw_hash(item),
    }
    return {field: values.get(field, "") for field in TARGET_FIELDS}


def legacy_record(item: dict) -> dict:
    url = str(item.get("source_url") or item.get("html_url") or "").rstrip("/")
    parts = url.replace("https://github.com/", "").split("/")
    owner = parts[0] if len(parts) >= 2 else ""
    name = parts[1] if len(parts) >= 2 else str(item.get("tech_name") or "")
    observed = str(item.get("crawl_time") or "")
    if observed and "T" not in observed:
        observed += "T00:00:00Z"
    values = {field: "" for field in TARGET_FIELDS}
    values.update({
        "full_name": f"{owner}/{name}" if owner and name else name,
        "owner": owner, "name": name,
        "description": item.get("summary") or "", "html_url": url,
        "topics": item.get("tags") or [], "observed_at": observed,
        "raw_hash": raw_hash(item),
    })
    return values


class GitHubCollector:
    def __init__(self, token: str = "") -> None:
        self.token = token or os.getenv("GITHUB_TOKEN", "")
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "TalentGraph-Evolution-Research",
        })
        if self.token:
            self.session.headers["Authorization"] = f"Bearer {self.token}"

    def get(self, url: str, params: dict | None = None, search: bool = False) -> requests.Response:
        while True:
            response = self.session.get(url, params=params, timeout=40)
            if response.status_code not in {403, 429}:
                return response
            remaining = int(response.headers.get("X-RateLimit-Remaining") or 0)
            reset = int(response.headers.get("X-RateLimit-Reset") or 0)
            if remaining > 0 or not reset:
                return response
            wait = max(1, reset - int(time.time()) + 2)
            print(f"GitHub API 限额等待 {wait} 秒")
            time.sleep(min(wait, 70 if search else wait))

    @staticmethod
    def pace(response: requests.Response, search: bool) -> None:
        if not search:
            return
        remaining = int(response.headers.get("X-RateLimit-Remaining") or 0)
        reset = int(response.headers.get("X-RateLimit-Reset") or 0)
        if remaining <= 1 and reset:
            time.sleep(max(1, reset - int(time.time()) + 2))
        elif not os.getenv("GITHUB_TOKEN"):
            time.sleep(6.2)

    def activity(self, full_name: str, raw_dir: Path, observed_at: str) -> dict:
        safe = re.sub(r"[^A-Za-z0-9_.-]+", "__", full_name)
        endpoints = {
            "release": f"{API}/repos/{full_name}/releases/latest",
            "tag": f"{API}/repos/{full_name}/tags",
            "commit": f"{API}/repos/{full_name}/commits",
            "contributors": f"{API}/repos/{full_name}/contributors",
        }
        payloads, responses = {}, {}
        for key, url in endpoints.items():
            params = {"per_page": 1}
            if key == "contributors":
                params["anon"] = "true"
            response = self.get(url, params=params)
            responses[key] = response
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            payloads[key] = payload
            (raw_dir / f"activity_{safe}_{key}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        release = payloads["release"] if isinstance(payloads["release"], dict) else {}
        tags = payloads["tag"] if isinstance(payloads["tag"], list) else []
        commits = payloads["commit"] if isinstance(payloads["commit"], list) else []
        commit = commits[0] if commits else {}
        commit_meta = (commit.get("commit") or {}) if isinstance(commit, dict) else {}
        author_meta = commit_meta.get("author") or commit_meta.get("committer") or {}
        contributors = payloads["contributors"] if isinstance(payloads["contributors"], list) else []
        contributor_count = len(contributors)
        link = responses["contributors"].headers.get("Link", "")
        last_match = re.search(r"[?&]page=(\d+)>; rel=\"last\"", link)
        if last_match:
            contributor_count = int(last_match.group(1))
        return {
            "full_name": full_name,
            "latest_release_tag": release.get("tag_name") or "",
            "latest_release_published_at": release.get("published_at") or "",
            "latest_tag": (tags[0].get("name") if tags else "") or "",
            "latest_commit_sha": (commit.get("sha") if isinstance(commit, dict) else "") or "",
            "latest_commit_at": author_meta.get("date") or "",
            "contributors": contributor_count if responses["contributors"].status_code == 200 else "",
            "observed_at": observed_at,
            "api_status": {key: response.status_code for key, response in responses.items()},
        }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="GitHub 仓库趋势 v2 采集")
    parser.add_argument("--pages", type=int, default=1)
    parser.add_argument("--per-page", type=int, default=30)
    parser.add_argument("--activity-limit", type=int, default=-1,
                        help="-1表示无Token采10个、有Token采100个；0表示跳过")
    parser.add_argument("--query-limit", type=int, default=0, help="0表示全部查询词")
    return parser.parse_args()


def run(pages: int = 1, per_page: int = 30, activity_limit: int = -1,
        query_limit: int = 0) -> list[dict]:
    collector = GitHubCollector()
    observed_at = now_iso()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = BASE / "data/bronze/github/api" / batch_id
    batch_dir = BASE / "data/.ops/collection/github/search_batches" / batch_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    batch_dir.mkdir(parents=True, exist_ok=True)
    queries = SEARCH_QUERIES[:query_limit or None]
    collected_by_id: dict[str, dict] = {}
    query_manifest = []

    for query_name, query in queries:
        query_rows = []
        for page in range(1, pages + 1):
            params = {"q": query, "sort": "stars", "order": "desc", "per_page": per_page, "page": page}
            response = collector.get(SEARCH_API, params=params, search=True)
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            raw_file = raw_dir / f"search_{query_name}_p{page}.json"
            raw_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
            items = payload.get("items") or [] if isinstance(payload, dict) else []
            if response.status_code != 200:
                print(f"[{query_name}] HTTP {response.status_code}: {payload.get('message', '') if isinstance(payload, dict) else ''}")
                break
            for rank, item in enumerate(items, 1):
                record = repo_record(item, observed_at)
                if not record["repo_id"]:
                    continue
                collected_by_id[record["repo_id"]] = record
                query_rows.append({
                    "batch_id": batch_id, "query_name": query_name, "query": query,
                    "page": page, "rank": rank, "repo_id": record["repo_id"],
                    "full_name": record["full_name"], "html_url": record["html_url"],
                    "raw_hash": record["raw_hash"], "observed_at": observed_at,
                })
            collector.pace(response, search=True)
            if len(items) < per_page:
                break
        write_jsonl(batch_dir / f"{query_name}.jsonl", query_rows)
        query_manifest.append({"query_name": query_name, "query": query, "records": len(query_rows)})
        print(f"[{query_name}] {len(query_rows)} 条，累计唯一仓库 {len(collected_by_id)}")

    output = BASE / "data/bronze/github_trend.jsonl"
    legacy_rows = load_jsonl(output)
    legacy_by_url = {
        str(row.get("source_url") or row.get("html_url") or "").rstrip("/"): row
        for row in legacy_rows
        if row.get("source_url") or row.get("html_url")
    }
    collected_urls = {row["html_url"].rstrip("/") for row in collected_by_id.values()}
    unresolved = [legacy_record(row) for url, row in legacy_by_url.items() if url not in collected_urls]
    final_rows = sorted([*collected_by_id.values(), *unresolved], key=lambda row: (not bool(row["repo_id"]), row["full_name"].casefold()))
    write_jsonl(output, final_rows)

    # 周快照只写 API 原值完整的记录，不把 legacy 空值当成0。
    iso_year, iso_week, _ = datetime.now(timezone.utc).isocalendar()
    week = f"{iso_year}-W{iso_week:02d}"
    snapshot_path = BASE / "data/snapshots/github" / f"{week}.jsonl"
    snapshot_rows = [{
        "repo_id": row["repo_id"], "full_name": row["full_name"],
        "stars": row["stars"], "forks": row["forks"], "open_issues": row["open_issues"],
        "watchers": row["watchers"], "contributors": "", "pushed_at": row["pushed_at"],
        "observed_at": observed_at, "source": "github_api",
    } for row in collected_by_id.values()]

    actual_activity_limit = activity_limit
    if actual_activity_limit < 0:
        actual_activity_limit = 100 if collector.token else 10
    activity_rows = []
    ranked = sorted(collected_by_id.values(), key=lambda row: int(row["stars"] or 0), reverse=True)
    for row in ranked[:actual_activity_limit]:
        activity = collector.activity(row["full_name"], raw_dir, observed_at)
        activity["repo_id"] = row["repo_id"]
        activity_rows.append(activity)
    activity_by_id = {row["repo_id"]: row for row in activity_rows}
    for snapshot in snapshot_rows:
        if snapshot["repo_id"] in activity_by_id:
            snapshot["contributors"] = activity_by_id[snapshot["repo_id"]]["contributors"]
    write_jsonl(snapshot_path, sorted(snapshot_rows, key=lambda row: row["repo_id"]))
    write_jsonl(BASE / "data/bronze/github_activity.jsonl", activity_rows)

    manifest = {
        "batch_id": batch_id, "observed_at": observed_at, "authenticated": bool(collector.token),
        "queries": query_manifest, "unique_api_repositories": len(collected_by_id),
        "legacy_urls_retained_unresolved": len(unresolved), "final_master_rows": len(final_rows),
        "activity_enriched": len(activity_rows), "snapshot_file": str(snapshot_path),
        "target_fields": TARGET_FIELDS,
    }
    (batch_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return final_rows


def main() -> int:
    args = parse_args()
    run(args.pages, args.per_page, args.activity_limit, args.query_limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
