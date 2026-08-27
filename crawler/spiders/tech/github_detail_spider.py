"""GitHub 项目详情 v2：只保存 GitHub API 原值和可追溯的技能证据。"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

BASE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(BASE))

from utils.skill_mapping import extract_skill_matches  # noqa: E402

API = "https://api.github.com"
INPUT = BASE / "data/bronze/github_trend.jsonl"
OUTPUT = BASE / "data/bronze/github_detail.jsonl"
RAW_ROOT = BASE / "data/bronze/github/detail_api"

DEPENDENCY_NAMES = {
    "package.json", "requirements.txt", "pyproject.toml", "poetry.lock", "pipfile",
    "pom.xml", "build.gradle", "build.gradle.kts", "go.mod", "cargo.toml",
    "composer.json", "gemfile", "dockerfile", "cmakelists.txt",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(payload: object) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(raw).hexdigest()


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temp.replace(path)


def decode_content(payload: dict) -> str:
    if payload.get("encoding") != "base64" or not payload.get("content"):
        return ""
    try:
        return base64.b64decode(payload["content"]).decode("utf-8", errors="replace")
    except (ValueError, TypeError):
        return ""


def unique_casefold(values: list[str]) -> list[str]:
    result, seen = [], set()
    for value in values:
        value = str(value or "").strip()
        key = value.casefold()
        if value and key not in seen:
            seen.add(key)
            result.append(value)
    return result


def evidence_from_text(text: str, channel: str, source_path: str) -> list[dict]:
    lines = text.splitlines() or [text]
    offsets, cursor = [], 0
    for line in lines:
        offsets.append(cursor)
        cursor += len(line) + 1
    evidence = []
    for match in extract_skill_matches(text):
        line_no = 1
        for index, offset in enumerate(offsets):
            if offset > match.start:
                break
            line_no = index + 1
        snippet = lines[line_no - 1].strip()[:300] if lines else ""
        evidence.append({
            "skill": match.standard, "raw": match.raw, "channel": channel,
            "source_path": source_path, "line": line_no, "snippet": snippet,
            "method": "alias_rule_v3",
        })
    return evidence


def build_skill_evidence(readme: str, topics: list[str], languages: dict, dependencies: list[dict]) -> tuple[list[str], list[str], list[dict]]:
    evidence = evidence_from_text(readme, "readme", "README")
    for topic in topics:
        evidence += evidence_from_text(topic, "topic", "topics")
    for language, byte_count in languages.items():
        evidence += evidence_from_text(f"{language}: {byte_count} bytes", "language", "languages_api")
    for item in dependencies:
        evidence += evidence_from_text(item.get("content", ""), "dependency", item.get("path", ""))

    deduped, seen = [], set()
    for item in evidence:
        key = (item["skill"].casefold(), item["channel"], item["source_path"], item["line"])
        if key not in seen:
            seen.add(key)
            deduped.append(item)
    inferred = unique_casefold([item["skill"] for item in deduped])
    relationship = unique_casefold([
        item["skill"] for item in deduped if item["channel"] in {"readme", "dependency"}
    ])
    return inferred, relationship, deduped


class APIClient:
    def __init__(self, token: str = "") -> None:
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "TalentGraph-Evolution-Research",
        })
        if token:
            self.session.headers["Authorization"] = f"Bearer {token}"
        self.remaining: int | None = None

    def get(self, url: str, params: dict | None = None) -> tuple[int, object]:
        response = self.session.get(url, params=params, timeout=40)
        remaining = response.headers.get("X-RateLimit-Remaining")
        if remaining is not None:
            self.remaining = int(remaining)
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        return response.status_code, payload


def save_payload(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def dependency_paths(tree_payload: object, limit: int) -> list[str]:
    if not isinstance(tree_payload, dict):
        return []
    candidates = []
    for item in tree_payload.get("tree") or []:
        path = str(item.get("path") or "")
        if item.get("type") == "blob" and Path(path).name.casefold() in DEPENDENCY_NAMES:
            candidates.append(path)
    return sorted(candidates, key=lambda p: (p.count("/"), len(p), p.casefold()))[:limit]


def collect_one(client: APIClient, source: dict, batch_dir: Path, batch_id: str, max_dependencies: int) -> dict | None:
    full_name = str(source.get("full_name") or "").strip()
    if not full_name or not source.get("repo_id"):
        return None
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "__", full_name)
    raw_dir = batch_dir / safe
    observed_at = now_iso()

    status, repo = client.get(f"{API}/repos/{full_name}")
    if status != 200 or not isinstance(repo, dict):
        print(f"跳过 {full_name}: Repo API HTTP {status}")
        return None
    save_payload(raw_dir / "repo.json", repo)
    branch = str(repo.get("default_branch") or "")

    readme_status, readme_meta = client.get(f"{API}/repos/{full_name}/readme", {"ref": branch})
    if readme_status == 200 and isinstance(readme_meta, dict):
        readme_content = decode_content(readme_meta)
        save_payload(raw_dir / "readme.json", readme_meta)
        (raw_dir / "readme.txt").write_text(readme_content, encoding="utf-8")
        readme_state = "fetched"
    else:
        readme_meta, readme_content = {}, ""
        readme_state = "not_found" if readme_status == 404 else f"http_{readme_status}"

    lang_status, languages = client.get(f"{API}/repos/{full_name}/languages")
    languages = languages if lang_status == 200 and isinstance(languages, dict) else {}
    if languages:
        save_payload(raw_dir / "languages.json", languages)

    tree_status, tree = client.get(f"{API}/repos/{full_name}/git/trees/{quote(branch, safe='')}", {"recursive": "1"})
    if tree_status == 200:
        save_payload(raw_dir / "tree.json", tree)
    dependencies = []
    for index, path in enumerate(dependency_paths(tree, max_dependencies), start=1):
        status, meta = client.get(f"{API}/repos/{full_name}/contents/{quote(path, safe='/')}", {"ref": branch})
        if status != 200 or not isinstance(meta, dict):
            continue
        content = decode_content(meta)
        save_payload(raw_dir / f"dependency_{index}.json", meta)
        (raw_dir / f"dependency_{index}.txt").write_text(content, encoding="utf-8")
        dependencies.append({
            "path": path, "sha": meta.get("sha") or "", "size": meta.get("size") if meta.get("size") is not None else "",
            "fetched_at": observed_at, "raw_hash": digest(meta), "content": content,
        })

    topics = unique_casefold(repo.get("topics") or [])
    inferred, relationship, evidence = build_skill_evidence(readme_content, topics, languages, dependencies)
    dependency_index = [{k: v for k, v in item.items() if k != "content"} for item in dependencies]
    license_data = repo.get("license") or {}
    return {
        "repo_id": str(repo.get("id") or ""), "full_name": repo.get("full_name") or "",
        "owner": (repo.get("owner") or {}).get("login") or "", "name": repo.get("name") or "",
        "html_url": repo.get("html_url") or "", "default_branch": branch,
        "description": repo.get("description") or "", "created_at": repo.get("created_at") or "",
        "updated_at": repo.get("updated_at") or "", "pushed_at": repo.get("pushed_at") or "",
        "primary_language": repo.get("language") or "", "language_bytes": languages,
        "stars": repo.get("stargazers_count") if repo.get("stargazers_count") is not None else "",
        "forks": repo.get("forks_count") if repo.get("forks_count") is not None else "",
        "open_issues": repo.get("open_issues_count") if repo.get("open_issues_count") is not None else "",
        "watchers": repo.get("subscribers_count") if repo.get("subscribers_count") is not None else "",
        "license": license_data.get("spdx_id") or license_data.get("name") or "",
        "archived": repo.get("archived") if isinstance(repo.get("archived"), bool) else "",
        "fork": repo.get("fork") if isinstance(repo.get("fork"), bool) else "",
        "observed_topics": topics, "inferred_skills": inferred, "relationship_skills": relationship,
        "skill_evidence": evidence, "readme_name": readme_meta.get("name") or "",
        "readme_path": readme_meta.get("path") or "", "readme_sha": readme_meta.get("sha") or "",
        "readme_size": readme_meta.get("size") if readme_meta.get("size") is not None else "",
        "readme_branch": branch, "readme_download_url": readme_meta.get("download_url") or "",
        "readme_content": readme_content, "readme_fetched_at": observed_at if readme_state == "fetched" else "",
        "readme_status": readme_state, "readme_generated": False, "dependency_files": dependency_index,
        "repo_raw_hash": digest(repo), "readme_raw_hash": digest(readme_meta) if readme_meta else "",
        "collection_batch_id": batch_id, "observed_at": observed_at,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="本批最多新增数；0 表示全部")
    parser.add_argument("--max-dependency-files", type=int, default=2)
    parser.add_argument("--refresh", action="store_true")
    args = parser.parse_args()
    token = os.getenv("GITHUB_TOKEN", "")
    limit = args.limit if args.limit is not None else (0 if token else 3)
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    batch_dir = RAW_ROOT / batch_id

    sources = [row for row in load_jsonl(INPUT) if row.get("repo_id") and row.get("full_name")]
    sources.sort(key=lambda row: int(row.get("stars") or 0), reverse=True)
    existing = {str(row.get("repo_id")): row for row in load_jsonl(OUTPUT)}
    client, added = APIClient(token), 0
    for source in sources:
        repo_id = str(source.get("repo_id"))
        if repo_id in existing and not args.refresh:
            continue
        # 匿名 API 配额很小；不足时立即停，不等待、不伪造。
        if not token and client.remaining is not None and client.remaining < 5:
            print(f"匿名 API 剩余 {client.remaining}，停止本批采集")
            break
        row = collect_one(client, source, batch_dir, batch_id, max(0, args.max_dependency_files))
        if row:
            existing[repo_id] = row
            added += 1
            write_jsonl(OUTPUT, sorted(existing.values(), key=lambda item: item.get("full_name", "").casefold()))
            print(f"已采集 {row['full_name']}，README={row['readme_status']}，技能证据={len(row['skill_evidence'])}")
        if limit and added >= limit:
            break
    manifest = {"batch_id": batch_id, "observed_at": now_iso(), "added": added, "total": len(existing), "api_only": True}
    save_payload(batch_dir / "manifest.json", manifest)
    print(json.dumps(manifest, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
