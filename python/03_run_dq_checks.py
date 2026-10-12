"""
03_run_dq_checks.py --target prod|test
Runs sql/04_dq_checks.sql in the chosen schema and exports:
  reports/output/<target>_dq_results.csv     one row per check (rows flagged, PASS/FAIL)
  reports/output/<target>_dq_exceptions.csv  one row per flagged source row
"""
import argparse
from pathlib import Path
import pandas as pd
from db import connect, run_sql_file, ROOT_SCHEMAS

ROOT = Path(__file__).resolve().parents[1]
ap = argparse.ArgumentParser(); ap.add_argument("--target", choices=["prod", "test"], default="prod")
target = ap.parse_args().target
schema = ROOT_SCHEMAS[target]
out = ROOT / "reports" / "output"; out.mkdir(parents=True, exist_ok=True)

with connect() as con, con.cursor() as cur:
    cur.execute(f"SET TIME ZONE 'UTC'; SET search_path TO {schema}")
    run_sql_file(cur, ROOT / "sql" / "04_dq_checks.sql")
    for tbl in ["dq_results", "dq_exceptions"]:
        cur.execute(f"SELECT * FROM {tbl} ORDER BY 1")
        df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
        df.to_csv(out / f"{target}_{tbl}.csv", index=False)
res = pd.read_csv(out / f"{target}_dq_results.csv")
print(res.to_string(index=False))
print(f"\n[{schema}] checks={len(res)}  failing={int((res.status == 'FAIL').sum())}  rows flagged={int(res.rows_flagged.sum()):,}")
