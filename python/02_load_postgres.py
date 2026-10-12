"""
02_load_postgres.py --target prod|test
Loads the 9 tables into PostgreSQL and builds the reporting layer.

  prod -> schema "synthea"       from data/raw/*.csv.gz   (Synthea output as generated)
  test -> schema "synthea_test"  from data/test/*.csv.gz  (copy with injected errors)

Steps: drop/recreate schema -> sql/01_schema.sql -> COPY each table -> indexes ->
sql/02_reporting_views.sql -> sql/03_reconciliation.sql -> export reconciliation CSVs.
"""
import argparse, gzip, csv
from pathlib import Path
import pandas as pd
from db import connect, run_sql_file, ROOT_SCHEMAS, TABLES

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--target", choices=["prod", "test"], default="prod")
target = ap.parse_args().target
schema = ROOT_SCHEMAS[target]
src = ROOT / "data" / ("raw" if target == "prod" else "test")
out = ROOT / "reports" / "output"; out.mkdir(parents=True, exist_ok=True)

with connect() as con, con.cursor() as cur:
    cur.execute(f"SET TIME ZONE 'UTC'; DROP SCHEMA IF EXISTS {schema} CASCADE; CREATE SCHEMA {schema}; SET search_path TO {schema};")
    run_sql_file(cur, ROOT / "sql" / "01_schema.sql")
    for t in TABLES:
        with gzip.open(src / f"{t}.csv.gz", "rt", encoding="utf-8") as f:
            header = next(csv.reader([f.readline()]))
            with cur.copy(f"COPY {t} ({', '.join(header)}) FROM STDIN WITH (FORMAT csv)") as cp:
                while chunk := f.read(1 << 20):
                    cp.write(chunk)
        cur.execute(f"SELECT COUNT(*) FROM {t}")
        print(f"[{schema}] loaded {t:<14} {cur.fetchone()[0]:>8,} rows")
    for t in ["patients", "providers", "organizations", "payers", "encounters"]:
        cur.execute(f"CREATE INDEX ON {t} (id)")
    for t in ["encounters", "conditions", "procedures", "medications", "immunizations"]:
        cur.execute(f"CREATE INDEX ON {t} (patient)")
    for t in ["conditions", "procedures", "medications", "immunizations"]:
        cur.execute(f"CREATE INDEX ON {t} (encounter)")
    cur.execute("ANALYZE")
    run_sql_file(cur, ROOT / "sql" / "02_reporting_views.sql")
    run_sql_file(cur, ROOT / "sql" / "03_reconciliation.sql")
    for tbl in ["recon_encounter_counts", "recon_child_linkage"]:
        cur.execute(f"SELECT * FROM {tbl}")
        df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
        df.to_csv(out / f"{target}_{tbl}.csv", index=False)
        print(df.to_string(index=False))
    cur.execute("SELECT COUNT(*) FROM information_schema.views WHERE table_schema = %s", (schema,))
    print(f"[{schema}] reporting views: {cur.fetchone()[0]}")
