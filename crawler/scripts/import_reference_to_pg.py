# -*- coding: utf-8 -*-
"""
TalentGraph · 参考/时态/新岗位/金标数据导入器（PostgreSQL）
===========================================================
读取 crawler/data/gold 下的 reference / temporal / new_jobs / 金标集，导入到：
  core.job_standard_dict / skill_candidate / ontology_changelog / ontology_version
  core.job_version_history / job_temporal_index / new_job_candidate
  eval.gold_jd / gold_resume / match_label / negative_sample

用法：
  python crawler/scripts/import_reference_to_pg.py [--dry-run] [--verbose]
"""
import argparse
import csv
import io
import json
import os
import sys
import time

try:
    import psycopg2
    from psycopg2.extras import Json
except ImportError:
    sys.exit("缺少 psycopg2-binary")

GOLD_DIR = os.path.join(os.path.dirname(__file__), "..", "data", "gold")


def db_connect():
    password = os.environ.get("PGPASSWORD")
    if not password:
        raise RuntimeError("必须通过 PGPASSWORD 环境变量提供 PostgreSQL 密码")
    return psycopg2.connect(
        host=os.environ.get("PGHOST", "127.0.0.1"),
        port=int(os.environ.get("PGPORT", "5432")),
        user=os.environ.get("PGUSER", "postgres"),
        password=password,
        dbname=os.environ.get("PGDATABASE", "talentgraph_dev"),
    )


def _ts(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return v


def _num(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


def _int(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    try:
        return int(float(v))
    except (ValueError, TypeError):
        return None


def load_json(name, sub="reference"):
    p = os.path.join(GOLD_DIR, sub, name)
    if not os.path.exists(p):
        print(f"[skip] 未找到 {p}")
        return None
    return json.load(open(p, encoding="utf-8"))


def load_jsonl(name, sub="temporal"):
    p = os.path.join(GOLD_DIR, sub, name)
    if not os.path.exists(p):
        print(f"[skip] 未找到 {p}")
        return []
    out = []
    with open(p, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def import_job_standard_dict(conn, dry):
    p = os.path.join(GOLD_DIR, "reference", "job_standard_dict.csv")
    if not os.path.exists(p):
        print("[job_standard_dict] 未找到，跳过"); return
    cur = conn.cursor()
    n = 0
    with open(p, encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            if dry:
                n += 1; continue
            cur.execute(
                """INSERT INTO core.job_standard_dict
                     (raw_job_name, standard_job_name, job_family, job_level, job_direction,
                      business_scene, occurrence_count, mapping_confidence, mapping_method,
                      mapping_evidence, review_status)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (raw_job_name, standard_job_name) DO UPDATE SET
                     mapping_confidence=EXCLUDED.mapping_confidence,
                     review_status=EXCLUDED.review_status""",
                (row.get("raw_job_name"), row.get("standard_job_name"), row.get("job_family"),
                 row.get("job_level"), row.get("job_direction"), row.get("business_scene"),
                 _int(row.get("occurrence_count")), _num(row.get("mapping_confidence")),
                 row.get("mapping_method"),
                 Json(json.loads(row["mapping_evidence"]) if row.get("mapping_evidence") else []),
                 row.get("review_status")))
            n += 1
    if not dry:
        conn.commit()
    print(f"[job_standard_dict] {n}" + (" (DRY)" if dry else ""))


def import_skill_candidates(conn, dry):
    d = load_json("skill_candidates.json")
    if not d:
        return
    cur = conn.cursor(); n = 0
    for name, cfg in d.items():
        if dry:
            n += 1; continue
        cur.execute(
            """INSERT INTO core.skill_candidate (candidate_name, skill_id, standard_name, skill_type, aliases, status, evidence)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (candidate_name) DO UPDATE SET
                 standard_name=EXCLUDED.standard_name, status=EXCLUDED.status""",
            (name, cfg.get("skill_id"), cfg.get("standard_name"), cfg.get("skill_type"),
             Json(cfg.get("aliases") or []), cfg.get("status"),
             Json({k: v for k, v in cfg.items() if k not in ("skill_id", "standard_name", "skill_type", "aliases", "status")})))
        n += 1
    if not dry:
        conn.commit()
    print(f"[skill_candidates] {n}" + (" (DRY)" if dry else ""))


def import_ontology_changelog(conn, dry):
    rows = load_jsonl("skill_ontology.changelog.jsonl", sub="reference")
    cur = conn.cursor(); n = 0
    for r in rows:
        if dry:
            n += 1; continue
        cur.execute(
            """INSERT INTO core.ontology_changelog (version, released_at, added_stable_ids, migration_summary, lifecycle_algorithm, source_policy)
               VALUES (%s,%s,%s,%s,%s,%s)
               ON CONFLICT DO NOTHING""",
            (r.get("version"), _ts(r.get("released_at")), _int(r.get("added_stable_ids")),
             Json(r.get("migration_summary") or {}), r.get("lifecycle_algorithm"), r.get("source_policy")))
        n += 1
    if not dry:
        conn.commit()
    print(f"[ontology_changelog] {n}" + (" (DRY)" if dry else ""))


def import_ontology_version(conn, dry):
    d = load_json("skill_ontology.version.json")
    if not d:
        return
    cur = conn.cursor()
    if not dry:
        cur.execute(
            """INSERT INTO core.ontology_version (version, released_at, skill_count, candidate_count, deprecated_count,
                                                  algorithm_version, promotion_rule, source_policy, previous_version)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (version) DO UPDATE SET skill_count=EXCLUDED.skill_count""",
            (d.get("version"), _ts(d.get("released_at")), _int(d.get("skill_count")),
             _int(d.get("candidate_count")), _int(d.get("deprecated_count")),
             d.get("algorithm_version"), d.get("promotion_rule"), d.get("source_policy"),
             d.get("previous_version")))
        conn.commit()
    print(f"[ontology_version] {d.get('version')}" + (" (DRY)" if dry else ""))


def import_job_versions(conn, dry):
    rows = load_jsonl("job_versions.jsonl")
    cur = conn.cursor(); n = 0
    for r in rows:
        if dry:
            n += 1; continue
        cur.execute(
            """INSERT INTO core.job_version_history
                 (version_id, record_id, canonical_job_id, version_number, content_hash, valid_from, valid_to,
                  is_current, change_type, changed_fields, previous_version_id, crawl_batch_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (version_id) DO UPDATE SET is_current=EXCLUDED.is_current""",
            (r.get("version_id"), r.get("record_id"), r.get("canonical_job_id"),
             _int(r.get("version_number")), r.get("content_hash"), _ts(r.get("valid_from")),
             _ts(r.get("valid_to")), r.get("is_current"), r.get("change_type"),
             Json(r.get("changed_fields") or {}), r.get("previous_version_id"), r.get("crawl_batch_id")))
        n += 1
    if not dry:
        conn.commit()
    print(f"[job_versions] {n}" + (" (DRY)" if dry else ""))


def import_temporal_index(conn, dry):
    rows = load_jsonl("job_temporal_index.jsonl")
    cur = conn.cursor(); n = 0
    for r in rows:
        if dry:
            n += 1; continue
        cur.execute(
            """INSERT INTO core.job_temporal_index
                 (record_id, canonical_job_id, source, source_url, job_title, standard_job_name, location,
                  first_seen_at, last_seen_at, observed_at, observed_date, publish_time_raw, source_published_at,
                  time_precision, time_source, time_parse_confidence, publication_quarter, temporal_eligible,
                  temporal_exclusion_reason, crawl_batch_id)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (record_id, observed_date) DO UPDATE SET last_seen_at=EXCLUDED.last_seen_at""",
            (r.get("record_id"), r.get("canonical_job_id"), r.get("source"), r.get("source_url"),
             r.get("job_title"), r.get("standard_job_name"), r.get("location"),
             _ts(r.get("first_seen_at")), _ts(r.get("last_seen_at")), _ts(r.get("observed_at")),
             _ts(r.get("observed_date")), r.get("publish_time_raw"), _ts(r.get("source_published_at")),
             r.get("time_precision"), r.get("time_source"), _num(r.get("time_parse_confidence")),
             r.get("publication_quarter"), r.get("temporal_eligible"),
             r.get("temporal_exclusion_reason"), r.get("crawl_batch_id")))
        n += 1
    if not dry:
        conn.commit()
    print(f"[job_temporal_index] {n}" + (" (DRY)" if dry else ""))


def import_new_job_candidates(conn, dry):
    d = load_json("new_job_candidates.json", sub="new_jobs")
    if not d:
        return
    cur = conn.cursor(); n = 0
    for c in d.get("candidates", []):
        if dry:
            n += 1; continue
        cur.execute(
            """INSERT INTO core.new_job_candidate
                 (candidate_id, name, candidate_type, parent_job, unique_jd_count, job_count, cluster_size,
                  company_count, source_count, region_count, top_skills, member_record_ids, evidence)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (candidate_id) DO UPDATE SET candidate_type=EXCLUDED.candidate_type""",
            (c.get("candidate_id"), c.get("name"), c.get("candidate_type"), c.get("parent_job"),
             _int(c.get("unique_jd_count")), _int(c.get("job_count")), _int(c.get("cluster_size")),
             _int(c.get("company_count")), _int(c.get("source_count")), _int(c.get("region_count")),
             Json(c.get("top_skills") or []), Json(c.get("member_record_ids") or []),
             Json({k: v for k, v in c.items() if k not in ("candidate_id", "name", "candidate_type",
                                                           "parent_job", "unique_jd_count", "job_count",
                                                           "cluster_size", "company_count", "source_count",
                                                           "region_count", "top_skills", "member_record_ids")})))
        n += 1
    if not dry:
        conn.commit()
    print(f"[new_job_candidates] {n}" + (" (DRY)" if dry else ""))


def import_gold_set(conn, dry, filename, table, id_col, id_field, extra_fields):
    rows = load_json(filename)
    if rows is None:
        return
    cur = conn.cursor(); n = 0
    for r in rows:
        if dry:
            n += 1; continue
        cols = [id_col, "split", "dataset_type", "annotation", "full_record"]
        vals = [r.get(id_field), r.get("split"), r.get("dataset_type"),
                Json(r.get("annotation") if "annotation" in r else r.get("task") or {}), Json(r)]
        for f in extra_fields:
            cols.append(f)
            vals.append(r.get(f))
        ph = ", ".join(["%s"] * len(vals))
        cur.execute(
            f"""INSERT INTO {table} ({', '.join(cols)}) VALUES ({ph})
                ON CONFLICT ({id_col}) DO UPDATE SET split=EXCLUDED.split, full_record=EXCLUDED.full_record""",
            vals)
        n += 1
    if not dry:
        conn.commit()
    print(f"[{filename}] {n}" + (" (DRY)" if dry else ""))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    conn = db_connect()
    try:
        import_job_standard_dict(conn, args.dry_run)
        import_skill_candidates(conn, args.dry_run)
        import_ontology_changelog(conn, args.dry_run)
        import_ontology_version(conn, args.dry_run)
        import_job_versions(conn, args.dry_run)
        import_temporal_index(conn, args.dry_run)
        import_new_job_candidates(conn, args.dry_run)
        import_gold_set(conn, args.dry_run, "gold_jd_set_reviewed.json", "eval.gold_jd", "sample_id", "sample_id",
                        ["source_job_id", "job_title"])
        import_gold_set(conn, args.dry_run, "gold_resume_set_reviewed.json", "eval.gold_resume", "sample_id", "sample_id",
                        ["resume_id", "display_name"])
        import_gold_set(conn, args.dry_run, "match_label_set_reviewed.json", "eval.match_label", "pair_id", "pair_id",
                        ["jd_sample_id", "source_job_id", "resume_sample_id"])
        import_gold_set(conn, args.dry_run, "negative_samples_reviewed.json", "eval.negative_sample", "sample_id", "sample_id",
                        ["type", "expected_anomaly"])
    finally:
        conn.close()
    print("完成。")


if __name__ == "__main__":
    main()
