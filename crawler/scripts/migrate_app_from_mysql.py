# -*- coding: utf-8 -*-
"""
TalentGraph · 业务数据从 MySQL 迁入 PostgreSQL app schema
===========================================================
将 MySQL talent_graph_evolution 的用户/简历/匹配/学习/差距数据迁入 talentgraph_dev.app schema。

要点：
  - 确定性 UUID（uuid5，基于 MySQL 表+id）→ 重跑幂等
  - 密码为 bcrypt 哈希，原样迁移到 password_hash
  - resume_skills / learning_tasks / gap_skills：skill_name 通过本体/别名解析为 skill_id，
    解析不到的跳过（符合设计方案：未知技能进隔离，不偷偷建同名技能）
  - match_records / user_job_actions / gap_analyses 的 job_id 实际是岗位名，
    按 standard_job_name / title 模糊匹配 core.entity；匹配不到标记 orphaned（job_id 置空）

用法：
  python crawler/scripts/migrate_app_from_mysql.py [--dry-run] [--verbose]

MySQL 连接（环境变量）：MYSQL_HOST/PORT/USER/PASSWORD/DB
PG 连接（环境变量）：PGHOST/PORT/USER/PASSWORD/DATABASE
"""
import argparse
import hashlib
import json
import os
import sys
import time
import uuid

import pymysql
import psycopg2
from psycopg2.extras import Json

def required_env(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"必须设置环境变量 {name}")
    return value


MYSQL = dict(
    host=os.environ.get("MYSQL_HOST", "127.0.0.1"),
    port=int(os.environ.get("MYSQL_PORT", "3306")),
    user=os.environ.get("MYSQL_USER", "root"),
    password=required_env("MYSQL_PASSWORD"),
    db=os.environ.get("MYSQL_DB", "talent_graph_evolution"),
    charset="utf8mb4",
)
PG = dict(
    host=os.environ.get("PGHOST", "127.0.0.1"),
    port=int(os.environ.get("PGPORT", "5432")),
    user=os.environ.get("PGUSER", "postgres"),
    password=required_env("PGPASSWORD"),
    dbname=os.environ.get("PGDATABASE", "talentgraph_dev"),
)


def det_uuid(ns, key):
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{ns}:{key}"))


def _ts(v):
    if v is None or (isinstance(v, str) and not v.strip()):
        return None
    return v


def _num(v):
    try:
        f = float(v)
        return f
    except (TypeError, ValueError):
        return None


def _score(v):
    value = _num(v)
    if value is None:
        return None
    return value / 100.0 if value > 1 else value


def _int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


class Migrator:
    def __init__(self, dry=False, verbose=False):
        self.dry = dry
        self.verbose = verbose
        self.my = pymysql.connect(**MYSQL, cursorclass=pymysql.cursors.DictCursor)
        self.pg = psycopg2.connect(**PG)
        self.pc = self.pg.cursor()
        # 技能名/别名 -> skill_id
        self.skill_lookup = {}
        self._load_skills()
        # 岗位名 -> entity_id
        self.job_lookup = {}
        self._load_jobs()

    def _load_skills(self):
        self.pc.execute("SELECT id, lower(name) n FROM core.skill")
        for rid, n in self.pc.fetchall():
            self.skill_lookup.setdefault(n, rid)
        self.pc.execute("SELECT skill_id, lower(alias) a FROM core.skill_alias")
        for rid, a in self.pc.fetchall():
            self.skill_lookup.setdefault(a, rid)

    def _load_jobs(self):
        self.pc.execute("SELECT e.id, lower(coalesce(j.standard_job_name,'')) s, lower(coalesce(j.title,'')) t "
                        "FROM core.entity e JOIN core.job j ON j.entity_id=e.id")
        for rid, s, t in self.pc.fetchall():
            if s:
                self.job_lookup.setdefault(s, rid)
            if t:
                self.job_lookup.setdefault(t, rid)

    def skill_id(self, name):
        if not name:
            return None
        return self.skill_lookup.get(str(name).strip().lower())

    def job_id(self, name):
        if not name:
            return None
        k = str(name).strip().lower()
        return self.job_lookup.get(k)

    def query(self, sql, args=None):
        cur = self.my.cursor()
        cur.execute(sql, args or ())
        return cur.fetchall()

    def exec_pg(self, sql, args):
        if self.dry:
            return
        self.pc.execute(sql, args)

    def commit(self):
        if not self.dry:
            self.pg.commit()

    def migrate_users(self):
        rows = self.query("SELECT * FROM users")
        n = 0
        for r in rows:
            self.exec_pg(
                """INSERT INTO app.user_account (id, username, password_hash, real_name, role, status, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET updated_at=EXCLUDED.updated_at""",
                (det_uuid("user", r["id"]), r["username"], r["password"], r["real_name"],
                 r["role"], r["status"], _ts(r["created_at"]), _ts(r["updated_at"])))
            n += 1
        self.commit()
        print(f"[users] {n}" + (" (DRY)" if self.dry else ""))

    def migrate_profiles(self):
        rows = self.query("SELECT * FROM user_profiles")
        n = 0
        for r in rows:
            self.exec_pg(
                """INSERT INTO app.user_profile (id, user_id, school, major, education, target_location, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (det_uuid("profile", r["id"]), det_uuid("user", r["user_id"]), r["school"], r["major"],
                 r["degree"], r["target_city"], _ts(r["updated_at"])))
            n += 1
        self.commit()
        print(f"[user_profiles] {n}" + (" (DRY)" if self.dry else ""))

    def migrate_resumes(self):
        rows = self.query("SELECT * FROM resumes")
        n = nv = 0
        for r in rows:
            rid = det_uuid("resume", r["id"])
            self.exec_pg(
                """INSERT INTO app.resume (id, user_id, file_uri, status, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO UPDATE SET status=EXCLUDED.status""",
                (rid, det_uuid("user", r["user_id"]), r["file_path"], r["parse_status"] or "pending",
                 _ts(r["uploaded_at"]), _ts(r["parsed_at"]) or _ts(r["uploaded_at"])))
            self.exec_pg(
                """INSERT INTO app.resume_version (id, resume_id, version_no, parse_status, parse_engine)
                   VALUES (%s,%s,1,%s,'legacy_mysql')
                   ON CONFLICT (id) DO NOTHING""",
                (det_uuid("resume_version", r["id"]), rid, r["parse_status"] or "pending"))
            n += 1
            nv += 1
        self.commit()
        print(f"[resumes] {n} / versions {nv}" + (" (DRY)" if self.dry else ""))

    def migrate_resume_skills(self):
        rows = self.query("SELECT * FROM resume_skills")
        n = skip = 0
        for r in rows:
            sid = self.skill_id(r["skill_name"]) or self.skill_id(r["standard_name"])
            if not sid:
                skip += 1
                continue
            self.exec_pg(
                """INSERT INTO app.resume_skill (id, resume_version_id, skill_id, confidence, evidence_text)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (det_uuid("resume_skill", r["id"]), det_uuid("resume_version", r["resume_id"]),
                 sid, _num(r["confidence"]), r["source_text"]))
            n += 1
        self.commit()
        print(f"[resume_skills] {n} / 跳过(未解析) {skip}" + (" (DRY)" if self.dry else ""))

    def migrate_resume_projects(self):
        rows = self.query("SELECT * FROM resume_projects")
        n = 0
        for r in rows:
            self.exec_pg(
                """INSERT INTO app.resume_project (id, resume_version_id, project_name, description)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (det_uuid("resume_project", r["id"]), det_uuid("resume_version", r["resume_id"]),
                 r["project_name"], r["description"]))
            n += 1
        self.commit()
        print(f"[resume_projects] {n}" + (" (DRY)" if self.dry else ""))

    def migrate_matches(self):
        rows = self.query("SELECT * FROM match_records")
        n = nres = nskill = orphan = 0
        for r in rows:
            run_id = det_uuid("match_run", r["id"])
            self.exec_pg(
                """INSERT INTO app.match_run (id, user_id, model_version, status, created_at)
                   VALUES (%s,%s,'legacy_mysql','done',%s)
                   ON CONFLICT (id) DO NOTHING""",
                (run_id, det_uuid("user", r["user_id"]), _ts(r["created_at"])))
            jid = self.job_id(r["job_name"])
            if not jid:
                orphan += 1
            self.exec_pg(
                """INSERT INTO app.match_result (id, match_run_id, job_id, legacy_job_name, total_score, dim_scores)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (det_uuid("match_result", r["id"]), run_id, jid, r["job_name"] if not jid else None, _score(r["match_score"]),
                 Json({"skill_match": _num(r["skill_match"]), "project_match": _num(r["project_match"]),
                       "potential_match": _num(r["potential_match"]), "level": r["match_level"]})))
            nres += 1
            # matched / missing skills
            for grp, raw_skills in (("matched", r.get("matched_skills")), ("missing", r.get("missing_skills"))):
                try:
                    skills = json.loads(raw_skills) if raw_skills else []
                except (TypeError, json.JSONDecodeError):
                    skills = []
                for sk in skills:
                    sid = self.skill_id(sk)
                    if not sid:
                        continue
                    self.exec_pg(
                        """INSERT INTO app.match_result_skill (id, match_result_id, skill_id, matched, contribution)
                           VALUES (%s,%s,%s,%s,0)
                           ON CONFLICT (id) DO NOTHING""",
                        (det_uuid("match_result_skill", f"{r['id']}:{grp}:{sk}"),
                         det_uuid("match_result", r["id"]), sid, grp == "matched"))
                    nskill += 1
            n += 1
        self.commit()
        print(f"[match_records] run {n} / result {nres} / skill {nskill} / orphaned_job {orphan}" +
              (" (DRY)" if self.dry else ""))

    def migrate_job_actions(self):
        rows = self.query("SELECT * FROM user_job_actions")
        n = orphan = 0
        for r in rows:
            jid = self.job_id(r["job_id"])
            if not jid:
                orphan += 1
            self.exec_pg(
                """INSERT INTO app.user_job_action (id, user_id, job_id, legacy_job_name, action_type, created_at)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (det_uuid("user_job_action", r["id"]), det_uuid("user", r["user_id"]), jid,
                 r["job_id"] if not jid else None,
                 r["action_type"], _ts(r["created_at"])))
            n += 1
        self.commit()
        print(f"[user_job_actions] {n} / orphaned_job {orphan}" + (" (DRY)" if self.dry else ""))

    def migrate_learning(self):
        plans = self.query("SELECT * FROM learning_plans")
        tasks = self.query("SELECT * FROM learning_tasks")
        np = nt = skip = 0
        for r in plans:
            self.exec_pg(
                """INSERT INTO app.learning_plan (id, user_id, status, created_at)
                   VALUES (%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (det_uuid("learning_plan", r["id"]), det_uuid("user", r["user_id"]),
                 r["status"], _ts(r["created_at"])))
            np += 1
        for r in tasks:
            sid = self.skill_id(r["skill_name"])
            if not sid:
                skip += 1
            self.exec_pg(
                """INSERT INTO app.learning_task (id, plan_id, skill_id, title, status, sort_order)
                   VALUES (%s,%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (det_uuid("learning_task", r["id"]), det_uuid("learning_plan", r["plan_id"]),
                 sid, r["title"], "done" if r["is_completed"] else "pending", _int(r["step_order"]) or 1))
            nt += 1
        self.commit()
        print(f"[learning] plans {np} / tasks {nt} / 跳过(未解析skill) {skip}" + (" (DRY)" if self.dry else ""))

    def migrate_gaps(self):
        rows = self.query("SELECT * FROM gap_analyses")
        n = nskill = orphan = 0
        for r in rows:
            jid = self.job_id(r["job_name"])
            if not jid:
                orphan += 1
            self.exec_pg(
                """INSERT INTO app.gap_analysis (id, user_id, target_job_id, legacy_job_name, created_at)
                   VALUES (%s,%s,%s,%s,%s)
                   ON CONFLICT (id) DO NOTHING""",
                (det_uuid("gap_analysis", r["id"]), det_uuid("user", r["user_id"]), jid,
                 r["job_name"] if not jid else None, _ts(r["created_at"])))
            n += 1
            for sk in (json.loads(r["gap_skills"]) if r.get("gap_skills") else []):
                sid = self.skill_id(sk)
                if not sid:
                    continue
                self.exec_pg(
                    """INSERT INTO app.gap_skill (id, gap_analysis_id, skill_id)
                       VALUES (%s,%s,%s)
                       ON CONFLICT (id) DO NOTHING""",
                    (det_uuid("gap_skill", f"{r['id']}:{sk}"), det_uuid("gap_analysis", r["id"]), sid))
                nskill += 1
        self.commit()
        print(f"[gap_analyses] {n} / gap_skill {nskill} / orphaned_job {orphan}" + (" (DRY)" if self.dry else ""))

    def migrate_config(self):
        # 非密钥配置迁入 ops.system_config（剔除含 password/token/key/secret 的键）
        rows = self.query("SELECT * FROM system_config")
        n = skip = 0
        for r in rows:
            k = str(r.get("config_key") or r.get("key") or "")
            if any(x in k.lower() for x in ("password", "token", "secret", "apikey", "api_key", "key")):
                skip += 1
                continue
            self.exec_pg(
                """INSERT INTO ops.system_config (config_key, config_value) VALUES (%s,%s)
                   ON CONFLICT (config_key) DO UPDATE SET config_value=EXCLUDED.config_value""",
                (k, json.dumps(r.get("config_value") or r.get("value") or {}, ensure_ascii=False)))
            n += 1
        self.commit()
        print(f"[system_config] {n} / 跳过敏感键 {skip}" + (" (DRY)" if self.dry else ""))

    def close(self):
        self.my.close()
        if not self.dry:
            self.pg.commit()
        self.pg.close()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()
    m = Migrator(dry=args.dry_run, verbose=args.verbose)
    try:
        m.migrate_users()
        m.migrate_profiles()
        m.migrate_resumes()
        m.migrate_resume_skills()
        m.migrate_resume_projects()
        m.migrate_matches()
        m.migrate_job_actions()
        m.migrate_learning()
        m.migrate_gaps()
        m.migrate_config()
    finally:
        m.close()
    print("完成。")


if __name__ == "__main__":
    main()
