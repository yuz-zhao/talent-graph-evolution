#!/usr/bin/env python3
"""Copy the MySQL application schema into PostgreSQL legacy_app for API compatibility."""
import argparse
import os
import re

import pymysql
import psycopg2
from psycopg2.extras import execute_values


TABLES = [
    "users", "user_profiles", "resumes", "resume_skills", "resume_projects",
    "match_records", "gap_analyses", "learning_plans", "learning_tasks",
    "learning_resources", "learning_video_progress", "notifications",
    "operation_logs", "system_config", "user_job_actions",
]


def required(name):
    value = os.getenv(name)
    if not value:
        raise RuntimeError(f"必须设置 {name}")
    return value


def pg_type(mysql_type, extra):
    value = mysql_type.lower()
    if "auto_increment" in extra:
        return "bigserial"
    if value.startswith(("tinyint", "smallint")):
        return "smallint"
    if value.startswith(("int", "mediumint")):
        return "integer"
    if value.startswith("bigint"):
        return "bigint"
    if value.startswith(("decimal", "numeric", "float", "double")):
        return "numeric"
    if value.startswith(("datetime", "timestamp")):
        return "timestamptz"
    if value.startswith("date"):
        return "date"
    if value.startswith(("json",)):
        return "jsonb"
    if value.startswith(("blob", "binary", "varbinary")):
        return "bytea"
    return "text"


def quote(name):
    return '"' + name.replace('"', '""') + '"'


def pg_default(value):
    if value is None:
        return ""
    text = str(value)
    upper = text.upper()
    if upper in {"CURRENT_TIMESTAMP", "CURRENT_TIMESTAMP()", "NOW()"}:
        return " DEFAULT CURRENT_TIMESTAMP"
    if re.fullmatch(r"-?\d+(\.\d+)?", text):
        return f" DEFAULT {text}"
    return " DEFAULT '" + text.replace("'", "''") + "'"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--replace", action="store_true", help="drop and recreate legacy_app")
    args = parser.parse_args()
    mysql = pymysql.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"), port=int(os.getenv("MYSQL_PORT", "3306")),
        user=os.getenv("MYSQL_USER", "root"), password=required("MYSQL_PASSWORD"),
        db=os.getenv("MYSQL_DB", "talent_graph_evolution"), charset="utf8mb4",
        cursorclass=pymysql.cursors.DictCursor,
    )
    postgres = psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"), port=int(os.getenv("PGPORT", "5432")),
        user=os.getenv("PGUSER", "postgres"), password=required("PGPASSWORD"),
        dbname=os.getenv("PGDATABASE", "talentgraph_dev"),
    )
    try:
        my = mysql.cursor()
        pg = postgres.cursor()
        if args.replace:
            pg.execute("DROP SCHEMA IF EXISTS legacy_app CASCADE")
        pg.execute("CREATE SCHEMA IF NOT EXISTS legacy_app")
        for table in TABLES:
            my.execute(f"SHOW TABLES LIKE %s", (table,))
            if not my.fetchone():
                print(f"[skip] {table}")
                continue
            my.execute(f"SHOW COLUMNS FROM `{table}`")
            columns = my.fetchall()
            definitions = []
            primary = []
            for column in columns:
                name = column["Field"]
                definition = f"{quote(name)} {pg_type(column['Type'], column['Extra'])}"
                if column["Null"] == "NO" and "auto_increment" not in column["Extra"]:
                    definition += " NOT NULL"
                if "auto_increment" not in column["Extra"]:
                    definition += pg_default(column["Default"])
                if column["Key"] == "PRI":
                    primary.append(name)
                definitions.append(definition)
            if primary:
                definitions.append("PRIMARY KEY (" + ",".join(quote(x) for x in primary) + ")")
            pg.execute(f"CREATE TABLE IF NOT EXISTS legacy_app.{quote(table)} ({','.join(definitions)})")
            pg.execute(f"TRUNCATE legacy_app.{quote(table)} RESTART IDENTITY CASCADE")
            my.execute(f"SELECT * FROM `{table}`")
            rows = my.fetchall()
            names = [column["Field"] for column in columns]
            if rows:
                values = [[row.get(name) for name in names] for row in rows]
                execute_values(
                    pg,
                    f"INSERT INTO legacy_app.{quote(table)} ({','.join(quote(x) for x in names)}) VALUES %s",
                    values,
                    page_size=500,
                )
            auto_columns = [
                column["Field"] for column in columns
                if "auto_increment" in column["Extra"]
            ]
            for column_name in auto_columns:
                pg.execute(
                    "SELECT setval(pg_get_serial_sequence(%s, %s), "
                    "COALESCE((SELECT MAX(" + quote(column_name) + ") FROM legacy_app." + quote(table) + "), 0) + 1, false)",
                    (f"legacy_app.{table}", column_name),
                )
            # Recreate unique indexes used by application upserts.
            my.execute(f"SHOW INDEX FROM `{table}`")
            grouped = {}
            for index in my.fetchall():
                if index["Key_name"] == "PRIMARY" or index["Non_unique"]:
                    continue
                grouped.setdefault(index["Key_name"], []).append((index["Seq_in_index"], index["Column_name"]))
            for index_name, parts in grouped.items():
                cols = ",".join(quote(x[1]) for x in sorted(parts))
                safe_name = re.sub(r"[^a-zA-Z0-9_]", "_", f"{table}_{index_name}")
                pg.execute(f"CREATE UNIQUE INDEX IF NOT EXISTS {quote(safe_name)} ON legacy_app.{quote(table)} ({cols})")
            print(f"[{table}] {len(rows)}")
        pg.execute("ALTER ROLE CURRENT_USER SET search_path = legacy_app, app, core, ingest, ops, public")
        postgres.commit()
    finally:
        mysql.close()
        postgres.close()


if __name__ == "__main__":
    main()
