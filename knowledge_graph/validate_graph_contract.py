#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
IMPORT = ROOT / "import"
SCHEMA = ROOT / "graph_schema.json"


def main() -> int:
    contract = json.loads(SCHEMA.read_text(encoding="utf-8"))
    checks = {}
    counts = {}
    errors = []
    csv_rows = {}
    for filename, required in contract["required_files"].items():
        path = IMPORT / filename
        checks[f"exists:{filename}"] = path.exists()
        if not path.exists():
            errors.append(f"missing file: {filename}")
            continue
        with path.open(encoding="utf-8-sig", newline="") as handle:
            reader = csv.DictReader(handle)
            header = reader.fieldnames or []
            file_rows = list(reader)
            count = len(file_rows)
            csv_rows[filename] = file_rows
        counts[filename] = count
        missing = [column for column in required if column not in header]
        checks[f"columns:{filename}"] = not missing
        checks[f"nonempty:{filename}"] = count > 0
        if missing: errors.append(f"{filename} missing columns: {', '.join(missing)}")
        if count == 0: errors.append(f"empty file: {filename}")

    node_files = {
        "nodes_job.csv": "job_id:ID",
        "nodes_skill.csv": "skill_id:ID",
        "nodes_job_cluster.csv": "cluster_id:ID",
    }
    node_ids = {}
    for filename, id_column in node_files.items():
        ids = [row.get(id_column, "").strip() for row in csv_rows.get(filename, [])]
        unique_ids = set(ids)
        valid = bool(ids) and "" not in unique_ids and len(ids) == len(unique_ids)
        checks[f"unique_ids:{filename}"] = valid
        node_ids[filename] = unique_ids
        if not valid:
            errors.append(f"{filename} has blank or duplicate {id_column} values")

    relation_contracts = {
        "rel_job_requires_skill.csv": ("nodes_job.csv", "nodes_skill.csv"),
        "rel_job_belongs_cluster.csv": ("nodes_job.csv", "nodes_job_cluster.csv"),
        "rel_skill_parent.csv": ("nodes_skill.csv", "nodes_skill.csv"),
    }
    for filename, (start_file, end_file) in relation_contracts.items():
        relation_rows = csv_rows.get(filename, [])
        missing_start = [row.get(":START_ID", "") for row in relation_rows if row.get(":START_ID", "") not in node_ids.get(start_file, set())]
        missing_end = [row.get(":END_ID", "") for row in relation_rows if row.get(":END_ID", "") not in node_ids.get(end_file, set())]
        pairs = [(row.get(":START_ID", ""), row.get(":END_ID", "")) for row in relation_rows]
        checks[f"valid_endpoints:{filename}"] = not missing_start and not missing_end
        checks[f"unique_pairs:{filename}"] = len(pairs) == len(set(pairs))
        if missing_start or missing_end:
            errors.append(f"{filename} has {len(missing_start)} missing start and {len(missing_end)} missing end nodes")
        if len(pairs) != len(set(pairs)):
            errors.append(f"{filename} has duplicate start/end pairs")

    result = {
        "contract_version": contract["version"],
        "passed": not errors,
        "checks": checks,
        "counts": counts,
        "errors": errors,
    }
    report = IMPORT / "graph_contract_report.json"
    report.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
