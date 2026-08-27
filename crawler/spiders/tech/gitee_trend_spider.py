"""Gitee 国内开源生态采集器；指标与 GitHub 分开保存、分开计算。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import requests


BASE = Path(__file__).resolve().parents[2]
API = "https://gitee.com/api/v5"
OFFICIAL_REPOSITORIES = {
    "openeuler/kernel": "操作系统/云原生",
    "openeuler/community": "操作系统/开源社区",
    "mindspore/mindspore": "人工智能框架",
    "rtthread/rt-thread": "物联网/嵌入式",
    "openharmony/kernel_liteos_a": "物联网/嵌入式操作系统",
    "openharmony/communication_wifi": "通信/物联网",
    "opengauss/openGauss-server": "数据库",
    "openkylin/kernel": "操作系统",
    "anolis/cloud-kernel": "云计算/操作系统",
    "dromara/hutool": "软件开发",
    "dromara/Sa-Token": "网络与信息安全",
    "alibaba/arthas": "云原生/运维",
    "baomidou/mybatis-plus": "软件开发",
    "jeecg/jeecg-boot": "工业软件/低代码",
    "tencent/tdesign": "软件开发",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def digest(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    with temp.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    temp.replace(path)


def normalize(item: dict, category: str, observed_at: str) -> dict:
    namespace = item.get("namespace") or {}
    owner = item.get("owner") or {}
    return {
        "repo_id": str(item.get("id") or ""),
        "full_name": item.get("full_name") or item.get("path_with_namespace") or "",
        "owner": owner.get("login") or namespace.get("path") or "",
        "name": item.get("name") or item.get("path") or "",
        "description": item.get("description") or "",
        "html_url": item.get("html_url") or "",
        "homepage": item.get("homepage") or "",
        "created_at": item.get("created_at") or "",
        "updated_at": item.get("updated_at") or "",
        "pushed_at": item.get("pushed_at") or "",
        "primary_language": item.get("language") or "",
        "license": item.get("license") or "",
        "stars": item.get("stargazers_count") if item.get("stargazers_count") is not None else "",
        "forks": item.get("forks_count") if item.get("forks_count") is not None else "",
        "open_issues": item.get("open_issues_count") if item.get("open_issues_count") is not None else "",
        "watchers": item.get("watchers_count") if item.get("watchers_count") is not None else "",
        "default_branch": item.get("default_branch") or "",
        "category": category,
        "observed_at": observed_at,
        "raw_hash": digest(item),
        "source": "gitee_api",
    }


def run(limit: int = 0) -> list[dict]:
    observed_at = now_iso()
    batch_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    raw_dir = BASE / "data/bronze/github/api" / batch_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update({"User-Agent": "TalentGraph-Evolution-Research"})
    rows, failures = [], []
    entries = list(OFFICIAL_REPOSITORIES.items())[:limit or None]
    for full_name, category in entries:
        response = session.get(f"{API}/repos/{full_name}", timeout=40)
        try:
            payload = response.json()
        except ValueError:
            payload = {}
        safe = full_name.replace("/", "__")
        (raw_dir / f"repo_{safe}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        if response.status_code == 200 and payload.get("id"):
            rows.append(normalize(payload, category, observed_at))
        else:
            failures.append({"full_name": full_name, "status": response.status_code})
    write_jsonl(BASE / "data/bronze/github_trend.jsonl", rows)
    year, week, _ = datetime.now(timezone.utc).isocalendar()
    write_jsonl(BASE / "data/snapshots/gitee" / f"{year}-W{week:02d}.jsonl", [{
        "repo_id": row["repo_id"], "full_name": row["full_name"], "stars": row["stars"],
        "forks": row["forks"], "open_issues": row["open_issues"], "watchers": row["watchers"],
        "observed_at": observed_at, "source": "gitee_api",
    } for row in rows])
    manifest = {
        "batch_id": batch_id, "observed_at": observed_at, "source": "gitee_api",
        "requested": len(entries), "collected": len(rows), "failures": failures,
        "metric_policy": "Gitee指标独立统计，不与GitHub stars/forks直接相加",
    }
    (raw_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(manifest, ensure_ascii=False, indent=2))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()
    run(args.limit)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
