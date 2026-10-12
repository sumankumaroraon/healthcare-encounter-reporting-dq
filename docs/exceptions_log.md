# Exceptions Log

## 1. Source exceptions in the production data

Found by running the 40 checks on the untouched Synthea output (schema `synthea`). These are real quirks of the source, not injected errors. They are left in place, flagged, and subtracted from the test results. Row-level detail: `reports/output/prod_dq_exceptions.csv`.

| Check | Rows | Finding | Handling |
|---|---:|---|---|
| DT04 | 131 | Encounters dated 2026-10-01 to 2026-10-16, after the 2026-09-30 reference date. Synthea schedules a few visits past the reference date. | Kept in source; excluded from trend views by the reporting window (Oct 2016 – Sep 2026). |
| DT07 | 56 | Procedures starting more than 24 h after their encounter closed (51 are digital rectal exams). | Kept and flagged; raise with data owner. |
| DT10 | 76 | Medications with a stop date 4–6 days before the start date (e.g., hydrochlorothiazide, lisinopril, insulin). | Kept and flagged; exclude from medication-duration metrics. |
| DT11 | 42 | Immunizations dated 1–35 days after the encounter they reference (41 are COVID-19 vaccine doses). | Kept and flagged; use the immunization date for dose timing. |
| **Total** | **305** | 4 of 40 checks | |

## 2. Rule adjustments

Two rules flagged expected behaviour in their first version. Each was narrowed, not deleted.

| Check | First version | Rows flagged | Adjusted rule | Rationale |
|---|---|---:|---|---|
| DT03 | Encounter > 1 day after patient death | 118 | Excludes encounter code `308646001` (Death Certification) | Death certification is recorded 2–14 days after death by design. After the change, 0 rows fail. |
| DT07 | Procedure start outside encounter start–stop | 36,728 | Procedure before encounter start, or > 24 h after encounter stop | Synthea encounters last ~15–60 minutes and procedures are timed sequentially after them (median gap under one hour). After the change, 56 genuine exceptions remain (above). |

## 3. Reporting-window decision

Synthea exports encounters from 1917-01-31 to 2026-10-16 (older encounters are kept when they relate to long-running conditions). Trend and mix analysis uses a 10-year window, **2016-10-01 to 2026-09-30 (44,424 encounters)**, flagged as `in_reporting_window` in `vw_encounter_detail`. All encounters remain in the tables and in reconciliation.

## 4. Injected errors the checks did not detect

From the test run (schema `synthea_test`, `reports/output/detection_by_error.csv`). All 13 belong to group E, "plausible-but-wrong", which was designed to be invisible to structural checks.

| Error type | Count | Why it is missed | Control that would catch it |
|---|---:|---|---|
| Encounter assigned to a different valid provider | 4 | Provider exists; no rule defines the correct provider | Reconcile to source scheduling or billing records |
| Encounter billed to a different valid payer | 3 | Payer exists | Compare with the patient's coverage period (Synthea `payer_transitions`) |
| Encounter date shifted 20 days | 3 | Date stays inside the patient's lifetime and the data window; encounter has no child events | Source-to-target comparison or audit trail |
| Birth date off by one year | 3 | Still before the patient's first encounter | Cross-check age-specific care (e.g., well-child visit timing) |

## 5. Secondary flags in the test run

The test run flagged 451 new rows: the 137 detected injected rows plus 314 related rows (322 flags, because some rows fail more than one check). All of them trace back to an injected error (0 false positives):

| Cause | Flags |
|---|---:|
| Encounters of 2 patients whose death date was set before birth (DT03) | 209 |
| Clinical events attached to an injected encounter (DT07, DT11, OR10) | 81 |
| Original row of a duplicated encounter (DU02, DU06) | 20 |
| Original row of a duplicated procedure or immunization (DU07, DU08) | 6 |
| Original row of a duplicated patient (DU01) | 4 |
| Original row of a duplicated provider (DU03) | 2 |
