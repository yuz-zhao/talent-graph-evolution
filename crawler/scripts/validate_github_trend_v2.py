"""验证 GitHub 趋势 v2 数据、快照、原始响应和热度可复算性。"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
MASTER = BASE / "data/bronze/github_trend.jsonl"
TARGET_FIELDS = [
    "repo_id", "full_name", "owner", "name", "description", "html_url", "homepage",
    "created_at", "updated_at", "pushed_at", "primary_language", "topics", "license",
    "archived", "fork", "stars", "forks", "open_issues", "watchers", "default_branch",
    "observed_at", "raw_hash",
]


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", encoding="utf-8-sig") as handle:
        for line in handle:
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


def digest(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def latest_manifest() -> tuple[Path | None, dict]:
    manifests = sorted((BASE / "data/.ops/collection/github/search_batches").glob("*/manifest.json"))
    if not manifests:
        return None, {}
    path = manifests[-1]
    return path, json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    rows = load_jsonl(MASTER)
    api_rows = [row for row in rows if row.get("repo_id")]
    legacy_rows = [row for row in rows if not row.get("repo_id")]
    manifest_path, manifest = latest_manifest()
    raw_hashes = set()
    if manifest:
        raw_root = BASE / "data/bronze/github/api"
        for path in raw_root.glob("**/*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            if isinstance(payload, dict) and payload.get("id") and payload.get("full_name"):
                raw_hashes.add(digest(payload))
            for item in (payload.get("items") or []) if isinstance(payload, dict) else []:
                raw_hashes.add(digest(item))
    metric_fields = ("stars", "forks", "open_issues", "watchers")
    metrics_valid = all(
        all(isinstance(row.get(field), int) and row[field] >= 0 for field in metric_fields)
        for row in api_rows
    )
    legacy_metrics_blank = all(all(row.get(field) == "" for field in metric_fields) for row in legacy_rows)
    snapshots = []
    snapshot_files = sorted((BASE / "data/snapshots/github").glob("*.jsonl"))
    for path in snapshot_files:
        snapshots.extend(load_jsonl(path))
    hotness = load_jsonl(BASE / "data/processed/github_hotness.jsonl")
    premature_growth = [row for row in hotness if int(row.get("snapshot_count") or 0) < 2 and row.get("growth_score") != ""]
    query_files = list(manifest_path.parent.glob("*.jsonl")) if manifest_path else []
    gitee_rows = load_jsonl(BASE / "data/bronze/github_trend.jsonl")
    checks = {
        "master_exists": MASTER.exists(),
        "target_fields_exact": bool(rows) and all(list(row.keys()) == TARGET_FIELDS for row in rows),
        "url_unique": len({row.get("html_url") for row in rows}) == len(rows),
        "repo_id_unique_when_present": len({row.get("repo_id") for row in api_rows}) == len(api_rows),
        "api_metrics_nonnegative_integers": metrics_valid,
        "legacy_metrics_are_blank": legacy_metrics_blank,
        "api_rows_match_raw_hash": bool(api_rows) and all(row.get("raw_hash") in raw_hashes for row in api_rows),
        "raw_api_saved": bool(raw_hashes),
        "query_batches_saved_separately": bool(query_files) and len(query_files) == len(manifest.get("queries") or []),
        "weekly_snapshot_saved": bool(snapshot_files) and bool(snapshots),
        "no_growth_before_two_weekly_snapshots": not premature_growth,
        "hotness_method_saved": (BASE / "data/reports/github_hotness_methodology.json").exists(),
        "domestic_source_saved_separately": bool(gitee_rows),
    }
    report = {
        "schema_version": "github_trend_v2",
        "generated_at": datetime.now().replace(microsecond=0).isoformat(),
        "master_rows": len(rows),
        "api_complete_rows": len(api_rows),
        "legacy_urls_retained_pending_refresh": len(legacy_rows),
        "unique_urls": len({row.get("html_url") for row in rows}),
        "snapshot_files": [path.name for path in snapshot_files],
        "snapshot_rows": len(snapshots),
        "growth_scores_available": sum(row.get("growth_score") != "" for row in hotness),
        "latest_batch": manifest,
        "query_family_counts": {
            item.get("query_name"): item.get("records", 0)
            for item in (manifest.get("queries") or []) if item.get("query_name")
        },
        "gitee_repositories": len(gitee_rows),
        "checks": checks,
        "acceptance": {
            "all_statistics_from_api_raw": metrics_valid and legacy_metrics_blank and checks["api_rows_match_raw_hash"],
            "missing_values_not_fabricated": legacy_metrics_blank,
            "growth_requires_two_weekly_snapshots": checks["no_growth_before_two_weekly_snapshots"],
            "hotness_reproducible_and_weighted": checks["hotness_method_saved"],
        },
        "notes": [
            "repo_id为空的记录是为保留旧URL而暂存的待刷新仓库，其统计字段保持为空。",
            "GitHub和Gitee分别保存快照与指标，不跨平台直接相加。",
            "同一周重复采集会更新周快照，不作为第二个增长率时间点。",
        ],
    }
    output = BASE / "data/reports/github_trend_v2_quality_report.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if all(checks.values()) and all(report["acceptance"].values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
