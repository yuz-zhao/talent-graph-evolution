"""低并发核验岗位来源链接，并区分可访问、反爬限制与真实失效。"""

from __future__ import annotations

import argparse
import csv
import json
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

import requests


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CSV = ROOT / "crawler/data/silver/jobs/jd_clean.csv"
DEFAULT_CACHE = ROOT / "crawler/data/.ops/collection/enrichment_cache/job_url_status.json"
DEFAULT_REPORT = ROOT / "crawler/data/reports/jd_url_check_report.json"
USER_AGENT = "Mozilla/5.0 (compatible; TalentGraphResearch/1.0; link-validation)"


def check_url(url: str, host_limits: dict[str, threading.Semaphore], timeout: float) -> dict:
    host = urlparse(url).netloc.casefold()
    semaphore = host_limits[host]
    checked_at = datetime.now().replace(microsecond=0).isoformat()
    try:
        with semaphore:
            response = requests.get(
                url,
                headers={"User-Agent": USER_AGENT, "Range": "bytes=0-2047"},
                timeout=timeout,
                allow_redirects=True,
                stream=True,
            )
            status_code = response.status_code
            final_url = response.url
            response.close()
        if 200 <= status_code < 400:
            status = "verified_live"
        elif status_code in {401, 403, 405, 406, 418, 429}:
            status = "reachable_blocked"
        elif status_code in {404, 410}:
            status = "not_found"
        elif status_code >= 500:
            status = "server_error"
        else:
            status = "http_error"
        return {"status": status, "http_status": status_code, "final_url": final_url, "checked_at": checked_at}
    except requests.RequestException as exc:
        return {"status": "network_error", "http_status": 0, "final_url": "", "checked_at": checked_at, "error": str(exc)[:300]}


def main() -> int:
    parser = argparse.ArgumentParser(description="岗位来源 URL 可达性核验")
    parser.add_argument("--csv", default=str(DEFAULT_CSV))
    parser.add_argument("--workers", type=int, default=10)
    parser.add_argument("--per-host", type=int, default=3)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--include-reference", action="store_true")
    args = parser.parse_args()

    csv_path = Path(args.csv)
    with csv_path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    DEFAULT_CACHE.parent.mkdir(parents=True, exist_ok=True)
    cache = {}
    if DEFAULT_CACHE.exists():
        try:
            cache = json.loads(DEFAULT_CACHE.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache = {}

    candidates = {}
    for row in rows:
        if not args.include_reference and row.get("statistics_scope") != "china_main":
            continue
        url = str(row.get("source_url") or "").strip()
        if not url or row.get("source_url_status") == "verified_live":
            continue
        if url in cache:
            continue
        candidates[url] = True

    host_limits = defaultdict(lambda: threading.Semaphore(max(1, args.per_host)))
    failures = 0
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as pool:
        futures = {pool.submit(check_url, url, host_limits, args.timeout): url for url in candidates}
        for index, future in enumerate(as_completed(futures), 1):
            url = futures[future]
            result = future.result()
            cache[url] = result
            failures += result["status"] in {"not_found", "server_error", "network_error", "http_error"}
            if index % 50 == 0:
                print(f"checked={index}/{len(candidates)} failures={failures}")
                DEFAULT_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    DEFAULT_CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    for row in rows:
        result = cache.get(str(row.get("source_url") or "").strip())
        if not result:
            continue
        row["source_url_status"] = result["status"]
        row["source_url_checked_at"] = result["checked_at"]

    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    china = [row for row in rows if row.get("statistics_scope") == "china_main"]
    effective = {"verified_live", "reachable_blocked"}
    status_counts = Counter(row.get("source_url_status") or "unchecked" for row in china)
    source_counts = {}
    for source in sorted({row.get("source_name") or "未知来源" for row in china}):
        items = [row for row in china if (row.get("source_name") or "未知来源") == source]
        source_counts[source] = {
            "count": len(items),
            "effective": sum(row.get("source_url_status") in effective for row in items),
            "status_counts": dict(Counter(row.get("source_url_status") or "unchecked" for row in items)),
        }
    report = {
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "scope": "china_main",
        "checked_this_run": len(candidates),
        "status_counts": dict(status_counts),
        "effective_rate": round(sum(row.get("source_url_status") in effective for row in china) / max(len(china), 1), 4),
        "source_counts": source_counts,
        "notes": [
            "verified_live 表示 2xx/3xx；reachable_blocked 表示服务器明确响应但限制自动访问。",
            "404/410 才直接判为链接失效；超时和 5xx 保留为待复核，不自动删除岗位。",
        ],
    }
    DEFAULT_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
