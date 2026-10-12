"""Shared PostgreSQL connection helper.

Connection settings come from the standard libpq environment variables, with local defaults:
  PGHOST (localhost)  PGPORT (5432)  PGUSER (postgres)  PGPASSWORD  PGDATABASE (encounters_dq)
"""
import os
import psycopg

ROOT_SCHEMAS = {"prod": "synthea", "test": "synthea_test"}
TABLES = ["patients", "organizations", "providers", "payers", "encounters",
          "conditions", "procedures", "medications", "immunizations"]


def connect(autocommit=True):
    return psycopg.connect(
        host=os.environ.get("PGHOST", "localhost"),
        port=os.environ.get("PGPORT", "5432"),
        user=os.environ.get("PGUSER", "postgres"),
        password=os.environ.get("PGPASSWORD"),
        dbname=os.environ.get("PGDATABASE", "encounters_dq"),
        autocommit=autocommit,
    )


def run_sql_file(cur, path):
    cur.execute(open(path, encoding="utf-8").read())
