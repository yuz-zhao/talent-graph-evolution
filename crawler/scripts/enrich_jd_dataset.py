"""将 jd_clean.csv 迁移到岗位数据 v2，并补全官方来源详情。

默认只做离线、可复现的字段迁移；传入 ``--online`` 时才访问腾讯、
中国信通院和中国电信的公开招聘页面。脚本不新增岗位，不会用模板文本填空。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import shutil
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import requests

BASE = Path(__file__).resolve().parents[1]
ROOT = BASE.parent
sys.path.insert(0, str(BASE))

from config.settings import JD_CLEAN_CSV, JD_FIELDS, USER_AGENT  # noqa: E402
from scripts.collect_caict_jobs import fetch_mobile_details, merge_mobile_details  # noqa: E402
from scripts.collect_telecom_jobs import fetch_jobs as fetch_telecom_jobs  # noqa: E402
from utils.save_utils import save_jobs_to_csv  # noqa: E402


TENCENT_DETAIL_API = "https://careers.tencent.com/tencentcareer/api/post/ByPostId"
SECTION_MARKER = re.compile(
    r"(?:任职要求|职位要求|岗位要求|任职资格|资格条件|应聘要求|Qualifications?|Requirements?|"
    r"Minimum Qualifications?|What You Bring|What We(?:'|’)re Looking For|Who You Are)\s*[:：]?",
    re.I,
)


def load_csv(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def ensure_raw_and_split(row: dict) -> None:
    description = str(row.get("description") or "").strip()
    requirements = str(row.get("requirements") or "").strip()
    if not str(row.get("raw_description") or "").strip():
        row["raw_description"] = "\n".join(x for x in (description, requirements) if x)

    # 旧 Greenhouse 采集器曾把技能列表误写入 requirements，不能继续当作原文。
    if row.get("source_name") == "Greenhouse" and len(requirements) < 320 and ";" in requirements:
        requirements = ""
        row["requirements"] = ""
        row["requirements_source"] = "legacy_skill_summary_removed"

    marker = SECTION_MARKER.search(description)
    if marker and (not requirements or requirements == description):
        before = description[:marker.start()].strip(" ;；。")
        after = description[marker.end():].strip(" ;；。")
        if len(before) >= 30 and len(after) >= 20:
            row["description"] = before
            row["requirements"] = after
            row["requirements_source"] = "inferred_section_split"
    elif requirements:
        row.setdefault("requirements_source", "source_page")


def tencent_post_id(row: dict) -> str:
    query = parse_qs(urlparse(str(row.get("source_url") or "")).query)
    return str((query.get("postId") or [""])[0])


def _fetch_tencent_one(post_id: str) -> tuple[str, dict | None, str]:
    try:
        response = requests.get(
            TENCENT_DETAIL_API,
            params={"postId": post_id, "language": "zh-cn"},
            headers={"User-Agent": USER_AGENT, "Referer": "https://careers.tencent.com/"},
            timeout=40,
        )
        response.raise_for_status()
        payload = response.json()
        data = payload.get("Data") or {}
        return post_id, data if data.get("PostId") else None, ""
    except Exception as exc:  # 单条失败不应中止 2,784 条迁移
        return post_id, None, str(exc)


def enrich_tencent(rows: list[dict], workers: int, cache_path: Path) -> dict:
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache = {}
    if cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache = {}
    ids = sorted({tencent_post_id(row) for row in rows if row.get("source_name") == "腾讯招聘官网" and tencent_post_id(row)})
    pending = [post_id for post_id in ids if post_id not in cache]
    failures = []
    if pending:
        with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
            futures = {pool.submit(_fetch_tencent_one, post_id): post_id for post_id in pending}
            for index, future in enumerate(as_completed(futures), 1):
                post_id, data, error = future.result()
                if data:
                    cache[post_id] = data
                else:
                    failures.append({"post_id": post_id, "error": error[:300]})
                if index % 50 == 0:
                    print(f"[腾讯详情] {index}/{len(pending)}，成功缓存 {len(cache)}")
                    cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
        cache_path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")

    checked_at = datetime.now().replace(microsecond=0).isoformat()
    changed = 0
    for row in rows:
        if row.get("source_name") != "腾讯招聘官网":
            continue
        data = cache.get(tencent_post_id(row))
        if not data:
            continue
        responsibility = str(data.get("Responsibility") or "").strip()
        requirement = str(data.get("Requirement") or "").strip()
        if responsibility:
            row["description"] = responsibility
        if requirement:
            row["requirements"] = requirement
            row["requirements_source"] = "source_detail"
        row["raw_description"] = "\n".join(x for x in (responsibility, requirement) if x)
        date_match = re.search(r"(20\d{2})年(\d{1,2})月(\d{1,2})日", str(data.get("LastUpdateTime") or ""))
        if date_match:
            row["publish_time"] = f"{date_match.group(1)}-{int(date_match.group(2)):02d}-{int(date_match.group(3)):02d}"
            row["publish_time_source"] = "source_detail"
        row["source_url_status"] = "verified_live"
        row["source_url_checked_at"] = checked_at
        changed += 1
    return {"requested": len(ids), "cache_hits": len(ids) - len(pending), "updated": changed, "failures": failures}


def enrich_caict(rows: list[dict], max_pages: int, delay: float) -> dict:
    details = fetch_mobile_details(max_pages=max_pages, delay=delay)
    caict_rows = [row for row in rows if row.get("source_name") == "中国信通院招聘官网"]
    _, changed = merge_mobile_details(caict_rows, details)
    return {"fetched_current_details": len(details), "updated": changed}


def enrich_telecom(rows: list[dict], max_pages: int, delay: float) -> dict:
    fetched = fetch_telecom_jobs(max_pages=max_pages, delay=delay)
    by_url = {str(row.get("source_url") or "").strip(): row for row in fetched if row.get("source_url")}
    changed = 0
    for row in rows:
        if row.get("source_name") != "中国电信招聘官网":
            continue
        fresh = by_url.get(str(row.get("source_url") or "").strip())
        if not fresh:
            continue
        for key in (
            "description", "requirements", "raw_description", "publish_time", "publish_time_source",
            "requirements_source", "source_url_status", "source_url_checked_at", "education", "experience",
        ):
            if fresh.get(key):
                row[key] = fresh[key]
        changed += 1
    return {"fetched_current_jobs": len(fetched), "updated": changed}


def coverage(rows: list[dict], field: str) -> float:
    return round(sum(bool(str(row.get(field) or "").strip()) for row in rows) / max(len(rows), 1), 4)


def valid_url_rate(rows: list[dict]) -> float:
    return round(sum(bool(re.match(r"^https?://[^\s]+$", str(row.get("source_url") or ""), re.I)) for row in rows) / max(len(rows), 1), 4)


def evidence_complete_rate(rows: list[dict]) -> float:
    total = complete = 0
    for row in rows:
        skills = [x for x in str(row.get("skill_standard") or "").split(";") if x]
        total += len(skills)
        try:
            evidence = json.loads(row.get("skill_evidence") or "[]")
        except json.JSONDecodeError:
            evidence = []
        proven = {item.get("skill") for item in evidence if item.get("snippet") and item.get("field")}
        complete += sum(skill in proven for skill in skills)
    return round(complete / max(total, 1), 4)


def metrics(rows: list[dict]) -> dict:
    effective_statuses = {"verified_live", "reachable_blocked"}
    return {
        "count": len(rows),
        "source_url_format_valid_rate": valid_url_rate(rows),
        "source_url_live_verified_rate": round(sum(row.get("source_url_status") == "verified_live" for row in rows) / max(len(rows), 1), 4),
        "source_url_effective_rate": round(sum(row.get("source_url_status") in effective_statuses for row in rows) / max(len(rows), 1), 4),
        "requirements_coverage": coverage(rows, "requirements"),
        "publish_time_coverage": coverage(rows, "publish_time"),
        "temporal_anchor_coverage": round(
            sum(bool(str(row.get("publish_time") or "").strip() or str(row.get("valid_from") or "").strip()) for row in rows)
            / max(len(rows), 1), 4
        ),
        "standard_skill_coverage": coverage(rows, "skill_standard"),
        "raw_description_coverage": coverage(rows, "raw_description"),
        "skill_relation_evidence_rate": evidence_complete_rate(rows),
        "company_type_known_rate": round(sum(row.get("company_type") not in {"", "未知"} for row in rows) / max(len(rows), 1), 4),
    }


def build_report(rows: list[dict], enrichment: dict, backup: str) -> dict:
    china = [row for row in rows if row.get("statistics_scope") == "china_main"]
    reference = [row for row in rows if row.get("statistics_scope") == "overseas_reference"]
    main = metrics(china)
    source_ids = [row.get("source_job_id") for row in rows]
    version_ids = [row.get("version_id") for row in rows]
    synthetic = [row for row in rows if str(row.get("is_synthetic") or "").casefold() == "true"]
    acceptance = {
        "scope": "china_main",
        "source_url_format_at_least_95_percent": main["source_url_format_valid_rate"] >= 0.95,
        "source_url_effective_at_least_95_percent": main["source_url_effective_rate"] >= 0.95,
        "requirements_missing_below_10_percent": main["requirements_coverage"] > 0.90,
        "publish_time_at_least_95_percent": main["publish_time_coverage"] >= 0.95,
        "standard_skill_at_least_95_percent": main["standard_skill_coverage"] >= 0.95,
        "every_skill_relation_has_evidence": main["skill_relation_evidence_rate"] == 1.0,
        "no_synthetic_jobs": not synthetic,
    }
    return {
        "schema_version": "2.0",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "backup": backup,
        "total_jobs": len(rows),
        "china_main_jobs": len(china),
        "overseas_reference_jobs": len(reference),
        "source_counts": dict(Counter(row.get("source_name") or "未知来源" for row in rows)),
        "job_family_counts": dict(Counter(family for row in china for family in str(row.get("job_family") or "").split(";") if family)),
        "region_counts": dict(Counter(row.get("region_standard") or "未标注" for row in china)),
        "live_verified_counts_by_source": dict(Counter(
            row.get("source_name") or "未知来源" for row in rows if row.get("source_url_status") == "verified_live"
        )),
        "requirements_source_counts": dict(Counter(row.get("requirements_source") or "missing" for row in rows)),
        "publish_time_source_counts": dict(Counter(row.get("publish_time_source") or "missing" for row in rows)),
        "all_data_metrics": metrics(rows),
        "china_main_metrics": main,
        "id_checks": {
            "source_job_id_nonempty": all(source_ids),
            "source_job_id_unique": len(source_ids) == len(set(source_ids)),
            "version_id_nonempty": all(version_ids),
            "version_id_unique": len(version_ids) == len(set(version_ids)),
        },
        "synthetic_job_count": len(synthetic),
        "enrichment": enrichment,
        "acceptance": acceptance,
        "notes": [
            "英文岗位及明确位于境外的岗位固定为 overseas_reference，不进入中国地区主统计和验收口径。",
            "source_url_format_valid_rate 仅检查 URL 结构；live_verified 单独报告，避免把反爬状态误判为链接失效。",
            "publish_time 缺失时不会用 crawl_time 冒充来源发布时间，valid_from 可记录首次观测日期。",
            "temporal_anchor_coverage 表示 publish_time 或首次观测 valid_from 至少存在一个，仅用于动态演化时序锚点，不替代发布时间验收。",
            "无法从公开原文补出的 requirements 保持为空，不用模板或模型生成内容填充。",
        ],
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="岗位数据 v2 迁移和官方详情补全")
    parser.add_argument("--input", default=JD_CLEAN_CSV)
    parser.add_argument("--output", default=JD_CLEAN_CSV)
    parser.add_argument("--online", action="store_true", help="访问三个官方招聘来源补全公开详情")
    parser.add_argument("--sources", default="tencent,caict,telecom")
    parser.add_argument("--workers", type=int, default=6)
    parser.add_argument("--max-pages", type=int, default=80)
    parser.add_argument("--delay", type=float, default=0.08)
    parser.add_argument("--no-backup", action="store_true")
    parser.add_argument("--report-only", action="store_true", help="仅按当前 CSV 刷新质量报告")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()
    rows = load_csv(input_path)
    original_count = len(rows)
    if args.report_only:
        report = build_report(rows, {"mode": "report_only"}, "")
        report_path = BASE / "data/reports/jd_quality_report.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps({"report": str(report_path), "metrics": report["china_main_metrics"], "acceptance": report["acceptance"]}, ensure_ascii=False, indent=2))
        return 0
    backup_path = ""
    if input_path == output_path and not args.no_backup:
        backup_dir = BASE / "data/backup"
        backup_dir.mkdir(parents=True, exist_ok=True)
        target = backup_dir / f"jd_clean_before_schema_v2_{datetime.now():%Y%m%d_%H%M%S}.csv"
        shutil.copy2(input_path, target)
        backup_path = str(target)
        print(f"已备份: {target}")

    for row in rows:
        ensure_raw_and_split(row)

    enrichment = {"mode": "online" if args.online else "offline", "original_count": original_count}
    if args.online:
        sources = {item.strip() for item in args.sources.split(",") if item.strip()}
        if "tencent" in sources:
            enrichment["tencent"] = enrich_tencent(
                rows, args.workers, BASE / "data/.ops/collection/enrichment_cache/tencent_details.json"
            )
        if "caict" in sources:
            try:
                enrichment["caict"] = enrich_caict(rows, args.max_pages, args.delay)
            except requests.RequestException as exc:
                enrichment["caict"] = {"updated": 0, "error": str(exc)}
        if "telecom" in sources:
            try:
                enrichment["telecom"] = enrich_telecom(rows, args.max_pages, args.delay)
            except requests.RequestException as exc:
                enrichment["telecom"] = {"updated": 0, "error": str(exc)}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    save_jobs_to_csv(str(output_path), rows, JD_FIELDS, sort=False, overwrite=True)
    saved = load_csv(output_path)
    if len(saved) != original_count:
        raise RuntimeError(f"岗位数量发生异常变化: {original_count} -> {len(saved)}")

    report = build_report(saved, enrichment, backup_path)
    report_path = BASE / "data/reports/jd_quality_report.json"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(output_path), "report": str(report_path),
        "total": len(saved), "china_main": report["china_main_jobs"],
        "metrics": report["china_main_metrics"], "acceptance": report["acceptance"],
    }, ensure_ascii=False, indent=2))
    return 0 if all(value is True or key == "scope" for key, value in report["acceptance"].items()) else 3


if __name__ == "__main__":
    raise SystemExit(main())
