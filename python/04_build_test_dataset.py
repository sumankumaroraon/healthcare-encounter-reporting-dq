"""
04_build_test_dataset.py
Builds a SEPARATE test copy of the 9 tables (data/test/) with 150 deliberately introduced errors,
and writes the ground-truth log data/test/injected_error_log.csv (one row per error, with the
table and _row_id it lives in, the error type, and the check expected to catch it).

The production copy (data/raw/) is never modified. Rows that already fail a check in production
(reports/output/prod_dq_exceptions.csv) are excluded from selection, so every detection in the
test run can be attributed to an injected error.

Error groups (counts):
  A. Missing keys          35   nulls in required key columns
  B. Orphan records        37   keys pointing at parents that do not exist / wrong patient
  C. Duplicate identifiers 24   repeated IDs and repeated event rows (appended rows)
  D. Inconsistent dates    41   impossible or contradictory dates
  E. Plausible-but-wrong   13   referentially valid, date-valid errors: included on purpose to
                                show what structural checks cannot catch
"""
import uuid
from pathlib import Path
import numpy as np
import pandas as pd

SEED = 2026
rng = np.random.default_rng(SEED)
ROOT = Path(__file__).resolve().parents[1]
RAW, TEST = ROOT / "data/raw", ROOT / "data/test"
TEST.mkdir(parents=True, exist_ok=True)
TABLES = ["patients", "organizations", "providers", "payers", "encounters",
          "conditions", "procedures", "medications", "immunizations"]
DEATH_CERT = "308646001"

t = {n: pd.read_csv(RAW / f"{n}.csv.gz", dtype=str, keep_default_na=False, na_values=[""]) for n in TABLES}
for n in TABLES:
    t[n]["_row_id"] = t[n]["_row_id"].astype(int)

base = pd.read_csv(ROOT / "reports/output/prod_dq_exceptions.csv")
excluded = {n: set(base.loc[base.table_name == n, "row_id"]) for n in TABLES}
used = {n: set() for n in TABLES}
log = []

def iso(ts):  # Synthea timestamp format
    return ts.strftime("%Y-%m-%dT%H:%M:%SZ")

def pick(table, k, mask=None):
    df = t[table]
    ok = ~df["_row_id"].isin(excluded[table] | used[table])
    if mask is not None:
        ok &= mask
    idx = rng.choice(df.index[ok], size=k, replace=False)
    used[table].update(df.loc[idx, "_row_id"])
    return list(idx)

def record(group, etype, table, idx, column, before, after, expected, note=""):
    log.append({"error_id": f"E{len(log) + 1:03d}", "group": group, "error_type": etype, "table_name": table,
                "row_id": int(t[table].at[idx, "_row_id"]), "column": column, "original_value": before,
                "injected_value": after, "expected_check": expected, "note": note})

def set_val(group, etype, table, idx, col, new, expected, note=""):
    old = t[table].at[idx, col]
    t[table].at[idx, col] = new
    record(group, etype, table, idx, col, old, new, expected, note)

def append_copy(group, etype, table, idx, expected, changes=None, note=""):
    row = t[table].loc[[idx]].copy()
    new_id = int(t[table]["_row_id"].max()) + 1
    row["_row_id"] = new_id
    for c, v in (changes or {}).items():
        row[c] = v
    t[table] = pd.concat([t[table], row], ignore_index=True)
    new_idx = t[table].index[-1]
    used[table].add(new_id)
    record(group, etype, table, new_idx, "(row)", f"copy of _row_id {int(t[table].at[idx, '_row_id'])}",
           "appended", expected, note)

enc = t["encounters"]
pat = t["patients"]
not_dc = enc["code"] != DEATH_CERT
in_window = pd.to_datetime(enc["start"], utc=True).between(
    pd.Timestamp("2016-10-01", tz="UTC"), pd.Timestamp("2026-09-01", tz="UTC"))
has_child = enc["id"].isin(pd.concat([t[c]["encounter"] for c in ["conditions", "procedures", "medications", "immunizations"]]))
patient_ids, provider_ids, org_ids, payer_ids = (t[n]["id"].tolist() for n in ["patients", "providers", "organizations", "payers"])

# ------------------------------------------------------------------ A. Missing keys (35)
for col, k, chk in [("patient", 8, "MK03"), ("provider", 6, "MK04"), ("organization", 5, "MK05"), ("payer", 5, "MK06")]:
    for i in pick("encounters", k, not_dc):
        set_val("A", f"null encounters.{col}", "encounters", i, col, None, chk)
for table, col, k, chk in [("conditions", "encounter", 4, "MK08"), ("procedures", "patient", 4, "MK09"),
                           ("immunizations", "encounter", 3, "MK11")]:
    for i in pick(table, k):
        set_val("A", f"null {table}.{col}", table, i, col, None, chk)

# ------------------------------------------------------------------ B. Orphan records (37)
fake = lambda: str(uuid.UUID(int=int(rng.integers(0, 2**63)) << 64 | int(rng.integers(0, 2**63))))
for col, k, chk in [("patient", 8, "OR01"), ("provider", 5, "OR02"), ("organization", 5, "OR03"), ("payer", 3, "OR04")]:
    for i in pick("encounters", k, not_dc):
        set_val("B", f"orphan encounters.{col}", "encounters", i, col, fake(), chk)
for i in pick("providers", 3):
    set_val("B", "orphan providers.organization", "providers", i, "organization", fake(), "OR05")
for table, k, chk in [("procedures", 5, "OR07"), ("medications", 4, "OR08")]:
    for i in pick(table, k):
        set_val("B", f"orphan {table}.encounter", table, i, "encounter", fake(), chk)
for i in pick("conditions", 4):
    other = rng.choice([p for p in patient_ids if p != t["conditions"].at[i, "patient"]])
    set_val("B", "condition linked to wrong patient", "conditions", i, "patient", other, "OR10")

# ------------------------------------------------------------------ C. Duplicate identifiers (24)
for i in pick("encounters", 8, not_dc):
    append_copy("C", "exact duplicate encounter row", "encounters", i, "DU02/DU06")
for i in pick("encounters", 4, not_dc):
    new_start = pd.Timestamp(enc.at[i, "start"]) + pd.Timedelta(days=int(rng.integers(30, 200)))
    new_stop = new_start + (pd.Timestamp(enc.at[i, "stop"]) - pd.Timestamp(enc.at[i, "start"]))
    append_copy("C", "encounter id reused for a different visit", "encounters", i, "DU02",
                {"start": iso(new_start), "stop": iso(new_stop)})
for i in pick("patients", 4):
    append_copy("C", "patient id reused with conflicting demographics", "patients", i, "DU01",
                {"zip": "19104", "marital": "S"})
for i in pick("providers", 2):
    append_copy("C", "provider id duplicated", "providers", i, "DU03")
for i in pick("procedures", 4):
    append_copy("C", "procedure recorded twice", "procedures", i, "DU07")
for i in pick("immunizations", 2):
    append_copy("C", "immunization recorded twice", "immunizations", i, "DU08")
enc = t["encounters"]; pat = t["patients"]

# ------------------------------------------------------------------ D. Inconsistent dates (41)
for i in pick("encounters", 8, not_dc):
    s, e = enc.at[i, "start"], enc.at[i, "stop"]
    t["encounters"].at[i, "start"], t["encounters"].at[i, "stop"] = e, s
    record("D", "encounter stop before start (swapped)", "encounters", i, "start/stop", f"{s} / {e}", f"{e} / {s}", "DT01")
birth = dict(zip(pat["id"], pd.to_datetime(pat["birthdate"])))
death = dict(zip(pat["id"], pd.to_datetime(pat["deathdate"])))
for i in pick("encounters", 6, not_dc):
    dur = pd.Timestamp(enc.at[i, "stop"]) - pd.Timestamp(enc.at[i, "start"])
    ns = pd.Timestamp(birth[enc.at[i, "patient"]], tz="UTC") - pd.Timedelta(days=45) + pd.Timedelta(hours=9)
    old = enc.at[i, "start"]
    t["encounters"].at[i, "start"], t["encounters"].at[i, "stop"] = iso(ns), iso(ns + dur)
    record("D", "encounter dated before patient birth", "encounters", i, "start", old, iso(ns), "DT02")
deceased = enc["patient"].map(lambda p: pd.notna(death.get(p)))
for i in pick("encounters", 5, not_dc & deceased):
    dur = pd.Timestamp(enc.at[i, "stop"]) - pd.Timestamp(enc.at[i, "start"])
    ns = pd.Timestamp(death[enc.at[i, "patient"]], tz="UTC") + pd.Timedelta(days=60, hours=10)
    old = enc.at[i, "start"]
    t["encounters"].at[i, "start"], t["encounters"].at[i, "stop"] = iso(ns), iso(ns + dur)
    record("D", "encounter dated after patient death", "encounters", i, "start", old, iso(ns), "DT03")
for i in pick("encounters", 5, not_dc):
    old = enc.at[i, "start"]
    ns, ne = old.replace(old[:4], "2027", 1), enc.at[i, "stop"].replace(enc.at[i, "stop"][:4], "2027", 1)
    t["encounters"].at[i, "start"], t["encounters"].at[i, "stop"] = ns, ne
    record("D", "encounter dated in the future (year typo)", "encounters", i, "start", old, ns, "DT04")
used_pat_ids = set(enc.loc[enc["_row_id"].isin(used["encounters"]), "patient"])
for i in pick("patients", 2, pat["deathdate"].notna() & ~pat["id"].isin(used_pat_ids)):
    old = pat.at[i, "deathdate"]
    new = (pd.Timestamp(pat.at[i, "birthdate"]) - pd.Timedelta(days=365)).strftime("%Y-%m-%d")
    set_val("D", "death date before birth date", "patients", i, "deathdate", new, "DT05", f"was {old}")
proc_enc_start = t["procedures"]["encounter"].map(dict(zip(enc["id"], enc["start"])))
for i in pick("procedures", 5, proc_enc_start.notna()):
    ns = pd.Timestamp(proc_enc_start[i]) - pd.Timedelta(days=3)
    set_val("D", "procedure dated before its encounter", "procedures", i, "start", iso(ns), "DT07")
cond = t["conditions"]
for i in pick("conditions", 4, cond["stop"].notna()):
    new = (pd.Timestamp(cond.at[i, "start"]) - pd.Timedelta(days=30)).strftime("%Y-%m-%d")
    set_val("D", "condition stop before start", "conditions", i, "stop", new, "DT09")
imm = t["immunizations"]
for i in pick("immunizations", 4, imm["encounter"].notna()):
    ns = pd.Timestamp(imm.at[i, "date"]) + pd.Timedelta(days=5)
    set_val("D", "immunization date not on encounter date", "immunizations", i, "date", iso(ns), "DT11")
med = t["medications"]
for i in pick("medications", 2, med["stop"].notna()):
    ns = pd.Timestamp(med.at[i, "start"]) - pd.Timedelta(days=90)
    set_val("D", "medication stop before start", "medications", i, "stop", iso(ns), "DT10")

# ------------------------------------------------------------------ E. Plausible-but-wrong (13)
for i in pick("encounters", 4, not_dc):
    other = rng.choice([p for p in provider_ids if p != enc.at[i, "provider"]])
    set_val("E", "encounter assigned to a different valid provider", "encounters", i, "provider", other,
            "none (expected miss)", "referentially valid value")
for i in pick("encounters", 3, not_dc):
    other = rng.choice([p for p in payer_ids if p != enc.at[i, "payer"]])
    set_val("E", "encounter billed to a different valid payer", "encounters", i, "payer", other,
            "none (expected miss)", "referentially valid value")
for i in pick("encounters", 3, not_dc & ~has_child & in_window):
    dur = pd.Timestamp(enc.at[i, "stop"]) - pd.Timestamp(enc.at[i, "start"])
    ns = pd.Timestamp(enc.at[i, "start"]) - pd.Timedelta(days=20)
    old = enc.at[i, "start"]
    t["encounters"].at[i, "start"], t["encounters"].at[i, "stop"] = iso(ns), iso(ns + dur)
    record("E", "encounter date shifted 20 days (still plausible)", "encounters", i, "start", old, iso(ns),
           "none (expected miss)", "date stays inside the patient's lifetime and the data window")
first_enc = enc.groupby("patient")["start"].min().map(lambda s: pd.Timestamp(s).tz_localize(None))
gap_ok = pat["id"].map(first_enc).sub(pd.to_datetime(pat["birthdate"])).dt.days > 800
for i in pick("patients", 3, gap_ok & ~pat["id"].isin(used_pat_ids)):
    new = (pd.Timestamp(pat.at[i, "birthdate"]) + pd.Timedelta(days=365)).strftime("%Y-%m-%d")
    set_val("E", "birth date off by one year", "patients", i, "birthdate", new, "none (expected miss)",
            "still before the patient's first encounter")

# ------------------------------------------------------------------ write
for n in TABLES:
    t[n].to_csv(TEST / f"{n}.csv.gz", index=False, compression="gzip")
logdf = pd.DataFrame(log)
logdf.to_csv(TEST / "injected_error_log.csv", index=False)
print(logdf.groupby(["group", "error_type"]).size().to_string())
print(f"\ninjected errors: {len(logdf)}  (A={sum(logdf.group=='A')} B={sum(logdf.group=='B')} "
      f"C={sum(logdf.group=='C')} D={sum(logdf.group=='D')} E={sum(logdf.group=='E')})")
