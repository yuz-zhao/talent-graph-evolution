#!/usr/bin/env python3
"""Read-only acceptance checks for the TalentGraph PostgreSQL fact store."""
import os
import sys

import psycopg2


def main():
    password = os.environ.get("PGPASSWORD")
    if not password:
        raise RuntimeError("必须设置 PGPASSWORD")
    conn = psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"), port=int(os.getenv("PGPORT", "5432")),
        user=os.getenv("PGUSER", "postgres"), dbname=os.getenv("PGDATABASE", "talentgraph_dev"),
        password=password,
    )
    checks = {}
    with conn, conn.cursor() as cur:
        queries = {
            "source_records": "SELECT count(*) FROM ingest.source_record",
            "job_records": "SELECT count(*) FROM ingest.source_record WHERE data_type='job'",
            "job_entities": "SELECT count(*) FROM core.entity WHERE entity_type='job'",
            "job_rows": "SELECT count(*) FROM core.job",
            "evidence": "SELECT count(*) FROM core.entity_skill_evidence",
            "evidence_with_source": "SELECT count(*) FROM core.entity_skill_evidence WHERE source_record_id IS NOT NULL",
            "quality_checks": "SELECT count(*) FROM ingest.quality_check",
            "failed_quality_checks": "SELECT count(*) FROM ingest.quality_check WHERE NOT passed",
            "current_version_violations": "SELECT count(*) FROM (SELECT entity_id FROM core.entity_version GROUP BY entity_id HAVING count(*) FILTER (WHERE is_current) <> 1) x",
        }
        for name, sql in queries.items():
            cur.execute(sql)
            checks[name] = cur.fetchone()[0]
    conn.close()
    for name, value in checks.items():
        print(f"{name}={value}")
    failures = []
    if checks["source_records"] != 5101: failures.append("source_records != Gold 5101")
    if checks["job_records"] != checks["job_entities"] or checks["job_entities"] != checks["job_rows"]:
        failures.append("岗位 source/entity/typed counts differ")
    if checks["evidence"] != checks["evidence_with_source"]:
        failures.append("存在未回连 source_record 的技能证据")
    if checks["quality_checks"] == 0 or checks["failed_quality_checks"]: failures.append("质量门缺失或有失败项")
    if checks["current_version_violations"]: failures.append("SCD2 current version 约束异常")
    if failures:
        print("FAILED:")
        print("\n".join(f"- {item}" for item in failures))
        sys.exit(1)
    print("PASSED")


if __name__ == "__main__":
    main()
