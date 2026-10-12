"""
01_prepare_raw.py
Selects the 9 related tables used in this project from the Synthea CSV export, removes
identifier-style fields that are not needed for reporting (SSN, driver's license, passport,
names, street address, coordinates), adds a stable _row_id to every table, and writes
gzip-compressed CSVs to data/raw/.

Input : synthea/output/csv/*.csv   (run synthea/generate_synthea.sh first)
Output: data/raw/<table>.csv.gz
"""
from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "synthea" / "output" / "csv"
OUT = ROOT / "data" / "raw"
OUT.mkdir(parents=True, exist_ok=True)

TABLES = {
    "patients": ["Id", "BIRTHDATE", "DEATHDATE", "MARITAL", "RACE", "ETHNICITY", "GENDER", "CITY",
                 "STATE", "COUNTY", "ZIP", "HEALTHCARE_EXPENSES", "HEALTHCARE_COVERAGE", "INCOME"],
    "organizations": ["Id", "NAME", "CITY", "STATE", "ZIP", "REVENUE", "UTILIZATION"],
    "providers": ["Id", "ORGANIZATION", "NAME", "GENDER", "SPECIALITY", "CITY", "STATE", "ZIP",
                  "ENCOUNTERS", "PROCEDURES"],
    "payers": ["Id", "NAME", "OWNERSHIP"],
    "encounters": None,     # all columns
    "conditions": None,
    "procedures": None,
    "medications": None,
    "immunizations": None,
}

for table, cols in TABLES.items():
    df = pd.read_csv(SRC / f"{table}.csv", dtype=str, keep_default_na=False, na_values=[""])
    if cols:
        df = df[cols]
    df.columns = [c.lower() for c in df.columns]
    df.insert(0, "_row_id", range(1, len(df) + 1))
    df.to_csv(OUT / f"{table}.csv.gz", index=False, compression="gzip")
    print(f"{table:<14} {len(df):>8,} rows  {len(df.columns):>2} cols")
