"""Portable interval scheduler for R04. Use --once for Task Scheduler/cron deployments."""
from __future__ import annotations
import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
CONFIG = BASE / "config/schedule_registry.json"
STATE = BASE / "data/.ops/scheduler/state.json"
RUNTIME_CONFIG = BASE / "data/.ops/runtime_config.json"


def load_runtime_config():
    if not RUNTIME_CONFIG.exists(): return {"scheduler_enabled": True, "crawl_frequency": "registry", "max_concurrency": 1}
    try: return json.loads(RUNTIME_CONFIG.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError): return {"scheduler_enabled": False, "crawl_frequency": "registry", "max_concurrency": 1}


def load_state():
    if not STATE.exists(): return {}
    try: return json.loads(STATE.read_text(encoding="utf-8"))
    except json.JSONDecodeError: return {}


def save_state(state):
    STATE.parent.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def due(last_run: str, interval: int, now: datetime) -> bool:
    if not last_run: return True
    try: previous = datetime.fromisoformat(last_run.replace("Z", "+00:00"))
    except ValueError: return True
    return now >= previous + timedelta(minutes=interval)


def tick(dry_run=False):
    runtime = load_runtime_config()
    if not runtime.get("scheduler_enabled", False): return []
    config = json.loads(CONFIG.read_text(encoding="utf-8")); state = load_state(); now = datetime.now(timezone.utc)
    frequency_minutes = {"hourly": 60, "daily": 1440, "weekly": 10080}.get(str(runtime.get("crawl_frequency", "registry")).lower())
    decisions = []; max_runs = max(1, int(runtime.get("max_concurrency", 1)))
    for name, job in config["jobs"].items():
        if len(decisions) >= max_runs: break
        if not job.get("enabled", True): continue
        interval = frequency_minutes or int(job["interval_minutes"])
        if not due(state.get(name, {}).get("last_started_at", ""), interval, now): continue
        command = [sys.executable, str(BASE / "scripts/run_incremental_pipeline.py"), "--sources", ",".join(job["sources"]), "--timeout-minutes", str(job.get("timeout_minutes", 90))]
        decisions.append({"job": name, "command": command})
    if dry_run or not decisions: return decisions
    for item in decisions: state[item["job"]] = {"last_started_at": now.replace(microsecond=0).isoformat(), "status": "running"}
    save_state(state)
    with ThreadPoolExecutor(max_workers=max_runs) as executor:
        futures = {executor.submit(subprocess.run, item["command"], cwd=BASE.parent): item["job"] for item in decisions}
        for future in as_completed(futures):
            name = futures[future]
            try: return_code = future.result().returncode
            except Exception: return_code = -1
            state[name].update(last_finished_at=datetime.now(timezone.utc).replace(microsecond=0).isoformat(), status="success" if return_code == 0 else "failed", return_code=return_code)
            save_state(state)
    return decisions


def main() -> int:
    parser = argparse.ArgumentParser(); parser.add_argument("--once", action="store_true"); parser.add_argument("--dry-run", action="store_true"); parser.add_argument("--poll-seconds", type=int, default=60); args = parser.parse_args()
    while True:
        decisions = tick(args.dry_run); print(json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(), "due_jobs": decisions}, ensure_ascii=False))
        if args.once or args.dry_run: return 0
        time.sleep(max(10, args.poll_seconds))


if __name__ == "__main__": raise SystemExit(main())
