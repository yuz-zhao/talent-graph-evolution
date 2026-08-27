"""从 GitHub 周快照构建可复算热度；不足两个快照时不计算增长率。"""

from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


BASE = Path(__file__).resolve().parents[1]
SNAPSHOT_DIR = BASE / "data/snapshots/github"
OUTPUT = BASE / "data/processed/github_hotness.jsonl"
METHOD = BASE / "data/reports/github_hotness_methodology.json"
POPULARITY_WEIGHTS = {"stars": 0.45, "forks": 0.25, "open_issues": 0.10, "recency": 0.20}
GROWTH_WEIGHTS = {"stars_growth": 0.60, "forks_growth": 0.25, "issues_activity": 0.15}


def load_rows() -> list[dict]:
    rows = []
    for path in sorted(SNAPSHOT_DIR.glob("*.jsonl")):
        with path.open("r", encoding="utf-8-sig") as handle:
            for line in handle:
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                row["snapshot_file"] = path.name
                rows.append(row)
    return rows


def number(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def log_norm(value: float, maximum: float) -> float:
    return 0.0 if maximum <= 0 else math.log1p(max(value, 0)) / math.log1p(maximum)


def recency_score(pushed_at: str, observed_at: str) -> float:
    try:
        pushed = datetime.fromisoformat(pushed_at.replace("Z", "+00:00"))
        observed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
        days = max(0.0, (observed - pushed).total_seconds() / 86400)
        return 2 ** (-days / 180.0)
    except (ValueError, AttributeError):
        return 0.0


def main() -> int:
    snapshots = load_rows()
    if not snapshots:
        print("没有 GitHub 周快照")
        return 2
    latest_by_repo: dict[str, dict] = {}
    history: dict[str, list[dict]] = defaultdict(list)
    for row in snapshots:
        repo_id = str(row.get("repo_id") or "")
        if repo_id:
            history[repo_id].append(row)
    for repo_id, rows in history.items():
        # 同一周重复运行只保留最新 observed_at，不形成虚假的第二个时间快照。
        weekly = {}
        for row in rows:
            week = row.get("snapshot_file")
            if week not in weekly or str(row.get("observed_at")) > str(weekly[week].get("observed_at")):
                weekly[week] = row
        history[repo_id] = sorted(weekly.values(), key=lambda row: str(row.get("observed_at")))
        latest_by_repo[repo_id] = history[repo_id][-1]

    maxima = {
        field: max((number(row.get(field)) for row in latest_by_repo.values()), default=0.0)
        for field in ("stars", "forks", "open_issues")
    }
    output = []
    for repo_id, latest in latest_by_repo.items():
        components = {
            "stars": log_norm(number(latest.get("stars")), maxima["stars"]),
            "forks": log_norm(number(latest.get("forks")), maxima["forks"]),
            "open_issues": log_norm(number(latest.get("open_issues")), maxima["open_issues"]),
            "recency": recency_score(str(latest.get("pushed_at") or ""), str(latest.get("observed_at") or "")),
        }
        popularity = sum(components[key] * POPULARITY_WEIGHTS[key] for key in POPULARITY_WEIGHTS)
        repo_history = history[repo_id]
        growth = ""
        growth_components = {}
        star_rate = fork_rate = issues_rate = ""
        trend = ""
        if len(repo_history) >= 2:
            previous = repo_history[-2]
            star_rate = (number(latest.get("stars")) - number(previous.get("stars"))) / max(number(previous.get("stars")), 1)
            fork_rate = (number(latest.get("forks")) - number(previous.get("forks"))) / max(number(previous.get("forks")), 1)
            issues_rate = abs(number(latest.get("open_issues")) - number(previous.get("open_issues"))) / max(number(previous.get("open_issues")), 1)
            growth_components = {
                "stars_growth": min(max(star_rate, 0.0), 1.0),
                "forks_growth": min(max(fork_rate, 0.0), 1.0),
                "issues_activity": min(max(issues_rate, 0.0), 1.0),
            }
            growth = sum(growth_components[key] * GROWTH_WEIGHTS[key] for key in GROWTH_WEIGHTS)
            trend = 0.70 * popularity + 0.30 * growth
        output.append({
            "repo_id": repo_id, "full_name": latest.get("full_name") or "",
            "snapshot_count": len(repo_history), "latest_observed_at": latest.get("observed_at") or "",
            "popularity_score": round(popularity, 6),
            "popularity_components": {key: round(value, 6) for key, value in components.items()},
            "star_growth_rate": "" if star_rate == "" else round(star_rate, 6),
            "fork_growth_rate": "" if fork_rate == "" else round(fork_rate, 6),
            "issues_activity_rate": "" if issues_rate == "" else round(issues_rate, 6),
            "growth_score": "" if growth == "" else round(growth, 6),
            "growth_components": growth_components,
            "trend_score": "" if trend == "" else round(trend, 6),
            "formula_version": "github_hotness_v2",
        })
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT.open("w", encoding="utf-8") as handle:
        for row in sorted(output, key=lambda row: row["popularity_score"], reverse=True):
            handle.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    methodology = {
        "formula_version": "github_hotness_v2",
        "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "popularity_formula": "0.45*log_norm(stars)+0.25*log_norm(forks)+0.10*log_norm(open_issues)+0.20*recency_half_life_180d",
        "popularity_weights": POPULARITY_WEIGHTS,
        "growth_formula": "0.60*positive_star_growth+0.25*positive_fork_growth+0.15*absolute_issue_activity",
        "growth_weights": GROWTH_WEIGHTS,
        "trend_formula": "0.70*popularity+0.30*growth，仅在至少两个不同周快照时计算",
        "missing_policy": "API缺失保持为空；增长率不以同一周重复采集冒充第二快照",
        "normalization": "stars/forks/open_issues 使用当期横截面 log1p(value)/log1p(max_value)",
    }
    METHOD.parent.mkdir(parents=True, exist_ok=True)
    METHOD.write_text(json.dumps(methodology, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "repositories": len(output),
        "with_two_snapshots": sum(row["snapshot_count"] >= 2 for row in output),
        "growth_scores": sum(row["growth_score"] != "" for row in output),
        "output": str(OUTPUT),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
