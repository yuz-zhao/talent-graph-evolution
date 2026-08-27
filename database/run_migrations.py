#!/usr/bin/env python3
"""Apply PostgreSQL migrations once, in lexical order, with a durable ledger."""
import os
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parent


def connect():
    password = os.environ.get("PGPASSWORD")
    if not password:
        raise RuntimeError("必须设置 PGPASSWORD")
    return psycopg2.connect(
        host=os.getenv("PGHOST", "127.0.0.1"),
        port=int(os.getenv("PGPORT", "5432")),
        user=os.getenv("PGUSER", "postgres"),
        dbname=os.getenv("PGDATABASE", "talentgraph_dev"),
        password=password,
    )


def main():
    conn = connect()
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute("CREATE TABLE IF NOT EXISTS public.schema_migration (version text PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())")
            for path in sorted((ROOT / "migrations").glob("*.sql")):
                cur.execute("SELECT 1 FROM public.schema_migration WHERE version=%s", (path.name,))
                if cur.fetchone():
                    print(f"[skip] {path.name}")
                    continue
                sql = path.read_text(encoding="utf-8")
                # Each SQL file owns its BEGIN/COMMIT. Record it only after that commit succeeds.
                cur.execute(sql)
                cur.execute("INSERT INTO public.schema_migration(version) VALUES (%s)", (path.name,))
                print(f"[apply] {path.name}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
