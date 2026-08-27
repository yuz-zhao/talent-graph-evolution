"""对 jd_clean.csv 全量重算中英文技能，并生成可审计报告。"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "crawler"))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from utils.skill_mapping import identify_skills  # noqa: E402


def _skills(value: str) -> list[str]:
    return [x.strip() for x in str(value or "").split(";") if x.strip()]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "crawler/data/silver/jobs/jd_clean.csv")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    path = args.input.resolve()
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fields = list(reader.fieldnames or [])
        rows = list(reader)

    before_covered = sum(bool(_skills(r.get("skill_standard", ""))) for r in rows)
    before_terms = sum(len(_skills(r.get("skill_standard", ""))) for r in rows)
    source_stats: dict[str, Counter] = defaultdict(Counter)
    skill_frequency: Counter[str] = Counter()
    missing_samples: list[dict[str, str]] = []

    for row in rows:
        text = "\n".join(str(row.get(name, "") or "") for name in (
            "job_title", "standard_job_name", "description", "requirements"
        ))
        raw, standard = identify_skills(text)
        row["skill_raw"] = ";".join(raw)
        row["skill_standard"] = ";".join(standard)
        source = row.get("source_name", "未知来源") or "未知来源"
        source_stats[source]["total"] += 1
        if standard:
            source_stats[source]["covered"] += 1
            skill_frequency.update(standard)
        elif len(missing_samples) < 40:
            missing_samples.append({"source": source, "job_title": row.get("job_title", "")})

    after_covered = sum(bool(_skills(r.get("skill_standard", ""))) for r in rows)
    after_terms = sum(len(_skills(r.get("skill_standard", ""))) for r in rows)
    report = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "input": str(path), "total_jobs": len(rows),
        "before": {"covered_jobs": before_covered, "coverage": round(before_covered / max(len(rows), 1), 4), "skill_mentions": before_terms},
        "after": {"covered_jobs": after_covered, "coverage": round(after_covered / max(len(rows), 1), 4), "skill_mentions": after_terms},
        "by_source": {
            name: {"total": stat["total"], "covered": stat["covered"], "coverage": round(stat["covered"] / stat["total"], 4)}
            for name, stat in sorted(source_stats.items())
        },
        "top_skills": skill_frequency.most_common(80), "unmatched_samples": missing_samples,
    }

    report_dir = ROOT / "crawler/data/reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / "skill_extraction_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    if not args.dry_run:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = ROOT / f"crawler/data/backup/jd_clean_before_skill_reextract_{stamp}.zip"
        backup.parent.mkdir(parents=True, exist_ok=True)
        with ZipFile(backup, "w", ZIP_DEFLATED) as archive:
            archive.write(path, path.name)
        temp = path.with_suffix(".tmp.csv")
        with temp.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(rows)
        shutil.move(str(temp), str(path))
        report["backup"] = str(backup)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
