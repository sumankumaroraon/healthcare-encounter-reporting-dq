"""
05_score_detection.py
Scores the validation checks against the injected-error log.

  * Baseline flags (already present in the production Synthea copy) are subtracted first.
  * An injected error is DETECTED if any check flags its (table, _row_id) in the test run.
  * It is detected BY THE EXPECTED CHECK if one of the checks named in expected_check flags it.
  * Secondary flags = new flags on rows that were not injected (e.g. the original row of a
    duplicate pair, or child events of an encounter whose patient key was broken). Each one
    is traced back to an injected error; anything that cannot be traced is a false positive.

Outputs (reports/output/):
  detection_by_error.csv   one row per injected error with detected / expected-check flags
  detection_summary.csv    roll-up by group and error type
  secondary_flags.csv      new flags on non-injected rows, with trace result
  detection_headline.csv   headline numbers used in the report
"""
from pathlib import Path
import gzip
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/output"
log = pd.read_csv(ROOT / "data/test/injected_error_log.csv")
base = pd.read_csv(OUT / "prod_dq_exceptions.csv")
test = pd.read_csv(OUT / "test_dq_exceptions.csv")

key = ["check_id", "table_name", "row_id"]
base_keys = set(map(tuple, base[key].values))
new = test[[tuple(r) not in base_keys for r in test[key].values]].copy()

flags_by_row = new.groupby(["table_name", "row_id"])["check_id"].apply(lambda s: sorted(set(s))).to_dict()
log["checks_fired"] = [", ".join(flags_by_row.get((r.table_name, r.row_id), [])) for r in log.itertuples()]
log["detected"] = log["checks_fired"] != ""
log["detected_by_expected_check"] = [
    any(c in str(r.checks_fired).split(", ") for c in str(r.expected_check).split("/")) for r in log.itertuples()]
log.to_csv(OUT / "detection_by_error.csv", index=False)

summary = (log.groupby(["group", "error_type", "expected_check"])
              .agg(injected=("error_id", "count"), detected=("detected", "sum"),
                   by_expected_check=("detected_by_expected_check", "sum")).reset_index())
summary["detection_rate"] = (summary.detected / summary.injected).round(3)
summary.to_csv(OUT / "detection_summary.csv", index=False)

# ---------------------------------------------------------------- trace secondary flags
def read(t):
    return pd.read_csv(ROOT / f"data/test/{t}.csv.gz", dtype=str, keep_default_na=False, na_values=[""])
enc_test = read("encounters"); pat_test = read("patients")
row2id = {t: dict(zip(read(t)["_row_id"].astype(int), read(t)["id"])) for t in ["encounters", "patients", "providers"]}
enc_patient = dict(zip(enc_test["id"], enc_test["patient"]))

inj_rows = set(zip(log.table_name, log.row_id))
inj_enc_ids = {row2id["encounters"][r] for t, r in inj_rows if t == "encounters"}
inj_pat_ids = {row2id["patients"][r] for t, r in inj_rows if t == "patients"}
inj_prov_ids = {row2id["providers"][r] for t, r in inj_rows if t == "providers"}

sec = new[[ (r.table_name, r.row_id) not in inj_rows for r in new.itertuples()]].copy()
def trace(r):
    if r.table_name == "encounters":
        eid = row2id["encounters"].get(r.row_id)
        if eid in inj_enc_ids: return "original row of an injected duplicate encounter"
        if enc_patient.get(eid) in inj_pat_ids: return "encounter of a patient whose dates were corrupted"
    if r.table_name == "patients" and row2id["patients"].get(r.row_id) in inj_pat_ids:
        return "original row of an injected duplicate patient"
    if r.table_name == "providers" and row2id["providers"].get(r.row_id) in inj_prov_ids:
        return "original row of an injected duplicate provider"
    if r.table_name in ("conditions", "procedures", "medications", "immunizations"):
        if r.record_key in inj_enc_ids: return "clinical event attached to an injected encounter"
        if r.check_id in ("DU07", "DU08"): return "original row of an injected duplicate event"
    return "UNTRACED (false positive)"
sec["trace"] = sec.apply(trace, axis=1)
sec.to_csv(OUT / "secondary_flags.csv", index=False)

structural = log[log.group != "E"]
head = {
    "injected_errors": len(log),
    "structural_errors": len(structural),
    "plausible_but_wrong_errors": int((log.group == "E").sum()),
    "detected": int(log.detected.sum()),
    "detected_structural": int(structural.detected.sum()),
    "detected_by_expected_check": int(log.detected_by_expected_check.sum()),
    "missed": int((~log.detected).sum()),
    "checks_fired_in_test": int(new.check_id.nunique()),
    "new_flagged_rows": int(new[["table_name", "row_id"]].drop_duplicates().shape[0]),
    "secondary_flag_rows": int(sec[["table_name", "row_id"]].drop_duplicates().shape[0]),
    "untraced_false_positives": int((sec.trace.str.startswith("UNTRACED")).sum()),
}
pd.Series(head, name="value").to_csv(OUT / "detection_headline.csv")
print(summary.to_string(index=False))
print("\nmissed errors:\n", log.loc[~log.detected, ["error_id", "group", "error_type", "table_name", "row_id"]].to_string(index=False))
print("\nsecondary flags by trace:\n", sec.groupby(["check_id", "trace"]).size().to_string())
print("\n", pd.Series(head).to_string())
