# -*- coding: utf-8 -*-
"""
TalentGraph · Gold 数据导入器（PostgreSQL 事实库）
===================================================
读取 crawler/data/gold 数据，按 database/migrations 的 schema 导入 PostgreSQL：

  1. reference/skill_ontology.json + skill_deprecated.json  -> core.skill / core.skill_alias
  2. records/*.jsonl                                        -> ingest.data_source / crawl_batch / source_record
                                                                 + core.entity / entity_source / entity_version
                                                                 + 类型化表（job/paper/project/course/...）
                                                                 + 由岗位 payload 派生 core.company
  3. evidence/skill_evidence.jsonl                          -> core.entity_skill_evidence（证据回连实体）

幂等原则（与设计方案 §8 一致）：
  - 所有 upsert 走自然唯一键（record_id / canonical_key / evidence 五元组），同一批数据重复导入不产生增量。
  - content_hash 未变只更新 last_seen_at；变化则关闭旧版本并创建新版本（SCD2）。

用法：
  python crawler/scripts/import_gold_to_pg.py [--dry-run] [--limit N] [--verbose] [--only skills|records|evidence]

环境变量（缺省值见下）：
  PGHOST=127.0.0.1  PGPORT=5432  PGUSER=postgres  PGPASSWORD=<required>  PGDATABASE=talentgraph_dev
"""
import argparse
import hashlib
import json
import os
import sys
import time

try:
    import psycopg2
    from psycopg2.extras import Json, RealDictCursor
except ImportError:
    sys.exit("缺少 psycopg2-binary，请先安装：python -m pip install psycopg2-binary")

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


# canonical key 解析（设计方案 §5.2：平台稳定 ID → 规范化 URL → 字段哈希）
def canonical_key(data_type, rec, payload):
    url = rec.get("source_url") or ""
    if data_type == "job":
        # canonical_job_id 是岗位族/相似岗位聚类键，不能作为单个招聘记录的实体键。
        # 同一平台的稳定岗位 ID 优先；缺失时退回规范 URL，最后使用 record_id。
        source_job_id = _norm(payload.get("source_job_id"))
        platform = _norm(rec.get("source_platform")) or "unknown"
        if source_job_id:
            return f"{platform}:{source_job_id}"
        if url:
            return f"{platform}:url:{url}"
        return f"{platform}:record:{rec.get('record_id')}"
    if data_type == "paper":
        return payload.get("arxiv_id") or url
    if data_type == "technology_project":
        rid = payload.get("repo_id")
        if rid not in (None, ""):
            return str(rid)
        # github 项目 repo_id 为空，用 html_url（完整 URL，与证据 source_url 一致）
        return payload.get("html_url") or payload.get("full_name") or url
    if data_type == "course":
        # 证据用 course_id（course_xxx 哈希）；canonical_course_id 只是 learn.xxx 别名
        return payload.get("course_id") or payload.get("canonical_course_id") or url
    if data_type == "certificate":
        return payload.get("certificate_id") or url
    if data_type == "technology_article":
        return url or payload.get("article_id") or rec.get("record_id")
    if data_type == "public_profile":
        return payload.get("github_login") or payload.get("profile_id") or url
    return url or rec.get("record_id")


def _norm(val):
    if val is None:
        return None
    return str(val).strip() or None


def _ts(val):
    """空串/None 一律转 NULL（PostgreSQL timestamptz 不接受 ''）"""
    if val is None or (isinstance(val, str) and not val.strip()):
        return None
    return val


# 1. 技能本体
def import_skills(conn, verbose):
    path = os.path.join(GOLD_DIR, "reference", "skill_ontology.json")
    if not os.path.exists(path):
        print("[skills] 未找到 skill_ontology.json，跳过")
        return
    ontology = json.load(open(path, encoding="utf-8"))
    dep_path = os.path.join(GOLD_DIR, "reference", "skill_deprecated.json")
    deprecated = json.load(open(dep_path, encoding="utf-8")) if os.path.exists(dep_path) else {}

    cur = conn.cursor()
    n_skill = n_alias = n_rel = 0
    for name, cfg in ontology.items():
        skill_code = cfg.get("skill_id") or ("skill_" + hashlib.sha1(name.encode()).hexdigest()[:12])
        replaced_by = cfg.get("replaced_by") or ""
        cur.execute(
            """INSERT INTO core.skill (skill_code, name, category, skill_type, lifecycle, ontology_version, deprecated)
               VALUES (%s,%s,%s,%s,%s,%s,%s)
               ON CONFLICT (skill_code) DO UPDATE SET
                 name=EXCLUDED.name, category=EXCLUDED.category, skill_type=EXCLUDED.skill_type,
                 lifecycle=EXCLUDED.lifecycle, ontology_version=EXCLUDED.ontology_version,
                 deprecated=EXCLUDED.deprecated, updated_at=now()""",
            (skill_code, name, _norm(cfg.get("category")), _norm(cfg.get("skill_type")),
             _norm(cfg.get("lifecycle_stage")), _norm(cfg.get("ontology_version")), bool(cfg.get("deprecated"))),
        )
        n_skill += 1
        for alias in cfg.get("aliases") or []:
            cur.execute(
                """INSERT INTO core.skill_alias (skill_id, alias, normalized_alias, language, source)
                   SELECT id, %s, lower(%s), 'zh', 'ontology' FROM core.skill WHERE skill_code=%s
                   ON CONFLICT (skill_id, alias) DO NOTHING""",
                (alias, alias, skill_code),
            )
            n_alias += 1
        # parent / replaced_by 关系
        parent = cfg.get("parent_skill") or ""
        for rel_code, rel_type in ((parent, "parent"), (replaced_by, "replaced_by")):
            if rel_code and rel_code != name:
                cur.execute(
                    """INSERT INTO core.skill_relation (from_skill_id, to_skill_id, relation_type)
                       SELECT a.id, b.id, %s FROM core.skill a, core.skill b
                       WHERE a.skill_code=%s AND b.name=%s
                       ON CONFLICT DO NOTHING""",
                    (rel_type, skill_code, rel_code),
                )
                n_rel += 1
    conn.commit()
    print(f"[skills] 技能本体 {n_skill} / 别名 {n_alias} / 关系 {n_rel}")


# 2. 记录 -> source_record + entity + 类型表
TYPED_COLS = {
    "job": ("core.job", ["canonical_job_id", "title", "standard_job_name", "company_name", "location",
                          "work_mode", "education", "experience", "salary", "industry", "description", "requirements",
                          "published_at", "first_seen_at", "last_seen_at", "time_precision", "status"]),
    "paper": ("core.paper", ["arxiv_id", "title", "abstract", "authors", "categories", "published_at", "updated_at", "pdf_url"]),
    "technology_project": ("core.technology_project", ["repo_id", "owner", "full_name", "language", "stars",
                                                       "forks", "topics", "created_at", "updated_at", "archived"]),
    "course": ("core.course", ["course_id", "canonical_course_id", "course_name", "provider", "language", "difficulty",
                               "duration_value", "duration_unit", "course_type", "syllabus", "prerequisites",
                               "price_type", "availability"]),
    "certificate": ("core.certificate", ["certificate_id", "name", "issuer", "level", "status", "validity_rule"]),
    "technology_article": ("core.technology_article", ["article_id", "title", "abstract", "source_name", "article_type", "published_at"]),
    "public_profile": ("core.public_profile", ["profile_id", "platform_account", "display_name", "bio", "location",
                                               "public_metrics", "authorization_status", "retention_until", "statistics_scope"]),
}


FIELD_SOURCES = {
    "job": {"title": "job_title", "company_name": "company", "published_at": "publish_time"},
    "technology_article": {"abstract": "rss_summary"},
    "public_profile": {"platform_account": "github_login"},
}


JSON_COLS = {"topics", "authors", "categories", "syllabus", "prerequisites", "public_metrics"}


def _typed_row(payload, data_type, rec=None):
    if data_type not in TYPED_COLS:
        return None, None
    table, cols = TYPED_COLS[data_type]
    aliases = FIELD_SOURCES.get(data_type, {})
    row = {}
    for c in cols:
        v = payload.get(aliases.get(c, c))
        if v in (None, "") and rec:
            envelope_sources = {
                "first_seen_at": "first_seen_at", "last_seen_at": "last_seen_at",
                "published_at": "source_published_at", "status": "lifecycle_status",
            }
            if c in envelope_sources:
                v = rec.get(envelope_sources[c])
        if c in JSON_COLS:
            # JSON 数组/对象列：空值给空容器，避免 NULL 违反 NOT NULL
            row[c] = Json(v if isinstance(v, (list, dict)) else ({} if c == "public_metrics" else []))
        elif isinstance(v, (dict, list)):
            row[c] = Json(v)
        else:
            row[c] = _ts(v)   # 空串一律转 NULL，避免 numeric/timestamptz 拒绝 ''
    return table, row


def _company_for(payload):
    name = _norm(payload.get("company"))
    if not name:
        return None, None
    key = "company_name_hash:" + hashlib.sha1(name.encode("utf-8")).hexdigest()[:16]
    return name, key


def import_records(conn, dry_run, limit, verbose):
    rec_dir = os.path.join(GOLD_DIR, "records")
    files = sorted(f for f in os.listdir(rec_dir) if f.endswith(".jsonl"))
    cur = conn.cursor()

    total_records = total_entities = total_versions = 0
    batch = 0
    start = time.time()
    for fn in files:
        path = os.path.join(rec_dir, fn)
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                payload = rec.get("payload") or {}
                data_type = rec.get("data_type") or "unknown"
                record_id = rec.get("record_id") or hashlib.sha1(line.encode()).hexdigest()
                if limit and total_records >= limit:
                    break

                if not dry_run:
                    platform = rec.get("source_platform") or "unknown"
                    source_type = rec.get("source_type") or "unknown"
                    cur.execute(
                        """INSERT INTO ingest.data_source (code, name, source_type, base_url)
                           VALUES (%s,%s,%s,%s)
                           ON CONFLICT (code) DO UPDATE SET
                             source_type=EXCLUDED.source_type,
                             base_url=COALESCE(ingest.data_source.base_url, EXCLUDED.base_url),
                             updated_at=now()
                           RETURNING id""",
                        (platform, platform, source_type, rec.get("source_url")),
                    )
                    source_id = cur.fetchone()[0]
                    # crawl_batch
                    batch_id = rec.get("crawl_batch_id")
                    cur.execute("""INSERT INTO ingest.crawl_batch
                                     (external_batch_id, source_id, source_code, status)
                                   VALUES (%s,%s,%s,'ingested')
                                   ON CONFLICT (external_batch_id) DO UPDATE SET
                                     source_id=EXCLUDED.source_id, source_code=EXCLUDED.source_code""",
                                (batch_id, source_id, platform))
                    # source_record
                    cur.execute(
                        """INSERT INTO ingest.source_record
                             (record_id, batch_id, source_id, data_type, source_platform, source_type,
                              source_url, source_published_at, crawled_at, content_hash, previous_content_hash,
                              lineage_uri, payload, content, collection_status, lifecycle_status,
                              first_seen_at, last_seen_at)
                           SELECT %s, b.id, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                           FROM ingest.crawl_batch b
                           WHERE b.external_batch_id=%s
                           ON CONFLICT (record_id) DO UPDATE SET
                             last_seen_at=EXCLUDED.last_seen_at,
                             content_hash=EXCLUDED.content_hash,
                             payload=EXCLUDED.payload,
                             lifecycle_status=EXCLUDED.lifecycle_status""",
                        (record_id, source_id, data_type, platform, source_type,
                         rec.get("source_url"), _ts(rec.get("source_published_at")), _ts(rec.get("crawled_at")),
                         rec.get("content_hash"), rec.get("previous_content_hash"), rec.get("lineage_uri"),
                         Json(payload), rec.get("content"), rec.get("collection_status"),
                         rec.get("lifecycle_status"), _ts(rec.get("first_seen_at")), _ts(rec.get("last_seen_at")),
                         batch_id),
                    )
                    # entity + entity_source + entity_version
                    ck = canonical_key(data_type, rec, payload)
                    if ck:
                        cur.execute(
                            """INSERT INTO core.entity (entity_type, canonical_key, display_name, status)
                               VALUES (%s, %s, %s, %s)
                               ON CONFLICT (entity_type, canonical_key) DO UPDATE SET updated_at=now()
                               RETURNING id""",
                            (data_type, ck, _norm(payload.get("job_title") or payload.get("course_name")
                                                  or payload.get("name") or rec.get("source_platform")),
                             rec.get("lifecycle_status") or "active"),
                        )
                        entity_id = cur.fetchone()[0]
                        total_entities += 1
                        # entity_source 关联
                        cur.execute("""INSERT INTO core.entity_source (entity_id, source_record_id, is_primary)
                                       SELECT %s, id, true FROM ingest.source_record WHERE record_id=%s
                                       ON CONFLICT (entity_id, source_record_id) DO NOTHING""",
                                    (entity_id, record_id))
                        # 版本 SCD2：以 source_record 为幂等锚点，同一记录只产生一个版本
                        content_hash = rec.get("content_hash") or ""
                        vf = _ts(payload.get("valid_from") or rec.get("first_seen_at"))
                        vt = _ts(payload.get("valid_to"))
                        cur.execute(
                            """SELECT ev.id FROM core.entity_version ev
                               JOIN ingest.source_record sr ON sr.id = ev.source_record_id
                               WHERE ev.entity_id=%s AND sr.record_id=%s""", (entity_id, record_id))
                        exist = cur.fetchone()
                        if not exist:
                            cur.execute(
                                """SELECT id, version_no, content_hash FROM core.entity_version
                                   WHERE entity_id=%s AND is_current""", (entity_id,))
                            curv = cur.fetchone()
                            close_at = vf or rec.get("crawled_at") or "now()"
                            if curv and curv[2] != content_hash:  # 内容变化才关闭旧 current
                                cur.execute(
                                    """UPDATE core.entity_version SET is_current=false, valid_to=%s
                                       WHERE id=%s""", (close_at, curv[0]))
                            new_no = (curv[1] if curv else 0) + 1
                            cur.execute(
                                """INSERT INTO core.entity_version
                                     (entity_id, version_no, content_hash, valid_from, valid_to, is_current,
                                      change_type, changed_fields, snapshot, source_record_id)
                                   VALUES (%s, %s, %s, %s, %s, true, %s, %s, %s,
                                           (SELECT id FROM ingest.source_record WHERE record_id=%s))
                                   ON CONFLICT (entity_id, version_no) DO NOTHING""",
                                (entity_id, new_no, content_hash, vf, vt,
                                 "update" if curv else "new",
                                 Json(rec.get("changed_fields") or {}), Json(rec.get("payload") or {}), record_id),
                            )
                            total_versions += 1
                            # 类型表
                            table, row = _typed_row(payload, data_type, rec)
                            if table:
                                cols = list(row.keys())
                                if cols:
                                    placeholders = ", ".join(["%s"] * len(cols))
                                    upd = ", ".join([f"{c}=EXCLUDED.{c}" for c in cols])
                                    cur.execute(
                                        f"""INSERT INTO {table} (entity_id, {', '.join(cols)})
                                            VALUES (%s, {placeholders})
                                            ON CONFLICT (entity_id) DO UPDATE SET {upd}""",
                                        [entity_id] + list(row.values()))
                            # 公司派生
                            comp_name, comp_key = _company_for(payload)
                            if comp_name and data_type == "job":
                                cur.execute(
                                    """INSERT INTO core.entity (entity_type, canonical_key, display_name)
                                       VALUES ('company', %s, %s)
                                       ON CONFLICT (entity_type, canonical_key) DO UPDATE SET updated_at=now()
                                       RETURNING id""", (comp_key, comp_name))
                                crow = cur.fetchone()
                                comp_id = crow[0] if crow else None
                                if not comp_id:
                                    cur.execute("SELECT id FROM core.entity WHERE entity_type='company' AND canonical_key=%s",
                                                (comp_key,))
                                    rr = cur.fetchone()
                                    comp_id = rr[0] if rr else None
                                if comp_id:
                                    cur.execute(
                                        """INSERT INTO core.company (entity_id, canonical_name)
                                           VALUES (%s,%s) ON CONFLICT (entity_id) DO NOTHING""",
                                        (comp_id, comp_name))
                                    cur.execute(
                                        """UPDATE core.job SET company_id=%s WHERE entity_id=%s""",
                                        (comp_id, entity_id))
                        # 类型字段也必须在幂等重跑时刷新，便于修复映射而不制造新版本。
                        table, row = _typed_row(payload, data_type, rec)
                        if table:
                            cols = list(row.keys())
                            placeholders = ", ".join(["%s"] * len(cols))
                            upd = ", ".join([f"{c}=EXCLUDED.{c}" for c in cols])
                            cur.execute(
                                f"""INSERT INTO {table} (entity_id, {', '.join(cols)})
                                    VALUES (%s, {placeholders})
                                    ON CONFLICT (entity_id) DO UPDATE SET {upd}""",
                                [entity_id] + list(row.values()),
                            )
                    else:
                        if verbose:
                            print(f"[records] 跳过无 canonical key 的记录 {record_id}")

                total_records += 1
                if not dry_run and total_records % 200 == 0:
                    conn.commit()
                    if verbose:
                        print(f"[records] {total_records} ...")
        if limit and total_records >= limit:
            break
    if not dry_run:
        conn.commit()
    dur = time.time() - start
    print(f"[records] 记录 {total_records} / 实体 {total_entities} / 版本 {total_versions}  ({dur:.1f}s, {'DRY-RUN 未写入' if dry_run else '已写入'})")


# 3. 证据
def import_evidence(conn, dry_run, verbose):
    path = os.path.join(GOLD_DIR, "evidence", "skill_evidence.jsonl")
    if not os.path.exists(path):
        print("[evidence] 未找到 skill_evidence.jsonl，跳过")
        return
    cur = conn.cursor()
    total = linked = skipped = 0
    start = time.time()
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            ev = json.loads(line)
            skill_code = ev.get("skill_id")
            source_entity_id = ev.get("source_entity_id")
            source_url = ev.get("source_url")
            total += 1
            if dry_run:
                continue
            # 技能：确保存在（本体里没有的建占位技能，不允许偷偷重名）
            if skill_code:
                cur.execute("SELECT id FROM core.skill WHERE skill_code=%s", (skill_code,))
                r = cur.fetchone()
                if not r:
                    cur.execute(
                        """INSERT INTO core.skill (skill_code, name) VALUES (%s,%s)
                           ON CONFLICT (skill_code) DO NOTHING""",
                        (skill_code, ev.get("skill_name") or skill_code))
                    cur.execute("SELECT id FROM core.skill WHERE skill_code=%s", (skill_code,))
                    r = cur.fetchone()
                skill_id = r[0] if r else None
            else:
                skill_id = None
            # 证据先回连 source_record，再通过 entity_source 获取实体。
            entity_id = None
            source_record_pk = None
            if source_url:
                expected_type = {
                    "official_company": "job",
                    "project": "technology_project",
                    "blog": "technology_article",
                }.get(ev.get("source_type"), ev.get("source_type"))
                cur.execute(
                    """SELECT sr.id, es.entity_id
                       FROM ingest.source_record sr
                       JOIN core.entity_source es ON es.source_record_id=sr.id
                       WHERE sr.source_url=%s
                         AND (%s IS NULL OR sr.data_type=%s)
                       ORDER BY sr.ingested_at DESC LIMIT 1""",
                    (source_url, expected_type, expected_type))
                r = cur.fetchone()
                if r:
                    source_record_pk, entity_id = r
            if not entity_id and source_entity_id:
                # 非岗位实体的证据文件仍使用稳定 canonical key。
                cur.execute("SELECT id FROM core.entity WHERE canonical_key=%s LIMIT 1", (source_entity_id,))
                r = cur.fetchone()
                entity_id = r[0] if r else None
            if not (skill_id and entity_id):
                skipped += 1
                continue
            relation_type = ev.get("relation_type") or ev.get("claim_type") or "mentions_skill"
            evidence_hash = ev.get("evidence_hash") or ev.get("evidence_id") or hashlib.sha1(
                f"{entity_id}|{skill_id}|{ev.get('relation_type')}|{ev.get('source_record_id')}|{ev.get('evidence_text')}"
                .encode()).hexdigest()
            cur.execute(
                """INSERT INTO core.entity_skill_evidence
                     (entity_id, skill_id, relation_type, claim_type, evidence_text, source_record_id, source_url,
                      extraction_confidence, source_reliability, relevance, freshness, evidence_score,
                      independent_group_id, is_independent_representative, observed_at, time_window,
                      extraction_method, algorithm_version, evidence_hash)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (entity_id, skill_id, relation_type, source_record_id, evidence_hash)
                   DO UPDATE SET observed_at=EXCLUDED.observed_at, evidence_score=EXCLUDED.evidence_score""",
                (entity_id, skill_id, relation_type, ev.get("claim_type"), ev.get("evidence_text"),
                 source_record_pk, source_url, ev.get("extraction_confidence"), ev.get("source_reliability"), ev.get("relevance"),
                 ev.get("freshness"), ev.get("evidence_score"), ev.get("independent_group_id"),
                 ev.get("is_independent_representative"), ev.get("observed_at"), ev.get("time_window"),
                 ev.get("extraction_method"), ev.get("algorithm_version"), evidence_hash),
            )
            linked += 1
            if total % 500 == 0:
                conn.commit()
    if not dry_run:
        conn.commit()
    print(f"[evidence] 共 {total} / 成功回连 {linked} / 跳过 {skipped}  ({time.time()-start:.1f}s, {'DRY-RUN' if dry_run else '已写入'})")


def finalize_metadata(conn):
    """补齐批次计数、质量门和算法版本，保证导入结果可运维、可审计。"""
    cur = conn.cursor()
    cur.execute(
        """UPDATE ingest.crawl_batch b SET
             record_count=x.record_count,
             success_count=x.record_count,
             error_count=0,
             finished_at=COALESCE(b.finished_at, now()),
             status='success'
           FROM (
             SELECT batch_id, count(*)::int AS record_count
             FROM ingest.source_record GROUP BY batch_id
           ) x WHERE x.batch_id=b.id"""
    )
    cur.execute(
        """INSERT INTO ingest.quality_check
             (batch_id, rule_code, severity, passed, details)
           SELECT b.id, 'gold_import_integrity', 'error',
                  b.record_count=b.success_count AND b.error_count=0,
                  jsonb_build_object('record_count', b.record_count,
                                     'success_count', b.success_count,
                                     'error_count', b.error_count)
           FROM ingest.crawl_batch b
           WHERE NOT EXISTS (
             SELECT 1 FROM ingest.quality_check q
             WHERE q.batch_id=b.id AND q.rule_code='gold_import_integrity'
           )"""
    )
    cur.execute(
        """INSERT INTO ops.algorithm_version (algo_name, version)
           SELECT DISTINCT 'skill_evidence', algorithm_version
           FROM core.entity_skill_evidence
           WHERE algorithm_version IS NOT NULL AND algorithm_version <> ''
           ON CONFLICT (algo_name, version) DO NOTHING"""
    )
    conn.commit()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="只统计不写入")
    ap.add_argument("--limit", type=int, default=None, help="仅处理前 N 条记录")
    ap.add_argument("--verbose", action="store_true")
    ap.add_argument("--only", choices=["skills", "records", "evidence"], default=None)
    args = ap.parse_args()

    conn = db_connect()
    run_id = None
    try:
        if not args.dry_run:
            cur = conn.cursor()
            cur.execute(
                """UPDATE ops.pipeline_run
                   SET status='failed', error=COALESCE(error, '导入进程被中断'), finished_at=now()
                   WHERE pipeline_name='import-gold' AND status='running'"""
            )
            cur.execute(
                """INSERT INTO ops.pipeline_run
                     (pipeline_name, input_uri, status)
                   VALUES ('import-gold', 'crawler/data/gold', 'running') RETURNING id"""
            )
            run_id = cur.fetchone()[0]
            conn.commit()
        if args.only in (None, "skills"):
            import_skills(conn, args.verbose)
        if args.only in (None, "records"):
            import_records(conn, args.dry_run, args.limit, args.verbose)
        if args.only in (None, "evidence"):
            import_evidence(conn, args.dry_run, args.verbose)
        if not args.dry_run:
            finalize_metadata(conn)
            cur = conn.cursor()
            cur.execute(
                """UPDATE ops.pipeline_run SET status='success', finished_at=now(), metrics=jsonb_build_object(
                     'source_records', (SELECT count(*) FROM ingest.source_record),
                     'entities', (SELECT count(*) FROM core.entity),
                     'evidence', (SELECT count(*) FROM core.entity_skill_evidence))
                   WHERE id=%s""", (run_id,)
            )
            conn.commit()
    except Exception as exc:
        conn.rollback()
        if run_id:
            cur = conn.cursor()
            cur.execute(
                "UPDATE ops.pipeline_run SET status='failed', error=%s, finished_at=now() WHERE id=%s",
                (str(exc), run_id),
            )
            conn.commit()
        raise
    finally:
        conn.close()
    print("完成。")


if __name__ == "__main__":
    main()
