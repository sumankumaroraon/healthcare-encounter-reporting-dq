"""
06_export_reporting.py
Exports the reporting views from the production schema (synthea) to reports/output/ as CSVs
that feed the PDF report (and any BI tool).
"""
from pathlib import Path
import pandas as pd
from db import connect

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "reports/output"
WINDOW = "in_reporting_window"

QUERIES = {
    "rpt_overview": f"""
        SELECT (SELECT COUNT(*) FROM patients)                    AS patients,
               (SELECT COUNT(*) FROM patients WHERE deathdate IS NOT NULL) AS deceased_patients,
               (SELECT COUNT(*) FROM encounters)                  AS encounters,
               (SELECT COUNT(*) FROM vw_encounter_detail WHERE {WINDOW}) AS encounters_in_window,
               (SELECT COUNT(DISTINCT patient_id) FROM vw_encounter_detail WHERE {WINDOW}) AS patients_in_window,
               (SELECT COUNT(*) FROM providers)                   AS providers,
               (SELECT COUNT(*) FROM organizations)               AS organizations,
               (SELECT COUNT(*) FROM payers)                      AS payers,
               (SELECT COUNT(*) FROM conditions)                  AS conditions,
               (SELECT COUNT(*) FROM procedures)                  AS procedures,
               (SELECT COUNT(*) FROM medications)                 AS medications,
               (SELECT COUNT(*) FROM immunizations)               AS immunizations,
               (SELECT MIN(start_ts)::date FROM vw_encounter_detail) AS first_encounter,
               (SELECT MAX(start_ts)::date FROM vw_encounter_detail) AS last_encounter""",
    "rpt_class_summary": "SELECT * FROM vw_encounter_class_summary ORDER BY encounters DESC",
    "rpt_class_summary_window": f"""
        SELECT encounterclass, COUNT(*) AS encounters,
               ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2) AS pct_of_encounters,
               COUNT(DISTINCT patient_id) AS unique_patients,
               ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_minutes)::numeric, 1) AS median_duration_min,
               ROUND(AVG(total_claim_cost), 2) AS avg_claim_cost,
               ROUND(100.0 * SUM(payer_coverage) / NULLIF(SUM(total_claim_cost), 0), 1) AS payer_covered_pct
        FROM vw_encounter_detail WHERE {WINDOW} GROUP BY encounterclass ORDER BY encounters DESC""",
    "rpt_monthly_volume": f"""
        SELECT v.encounter_month, v.encounterclass, v.encounters
        FROM vw_encounter_volume_monthly v
        WHERE v.encounter_month >= DATE '2016-10-01' AND v.encounter_month < DATE '2026-10-01'
        ORDER BY 1, 2""",
    "rpt_annual_volume": f"""
        SELECT encounter_year, COUNT(*) AS encounters, COUNT(DISTINCT patient_id) AS unique_patients,
               ROUND(1.0 * COUNT(*) / COUNT(DISTINCT patient_id), 2) AS encounters_per_patient
        FROM vw_encounter_detail WHERE encounter_year BETWEEN 2017 AND 2025 GROUP BY 1 ORDER BY 1""",
    "rpt_top_visit_types": f"""
        SELECT encounterclass, visit_description, COUNT(*) AS encounters, COUNT(DISTINCT patient_id) AS unique_patients
        FROM vw_encounter_detail WHERE {WINDOW}
        GROUP BY 1, 2 ORDER BY encounters DESC LIMIT 12""",
    "rpt_visit_types_count": f"SELECT COUNT(*) AS visit_types FROM (SELECT DISTINCT visit_code FROM vw_encounter_detail) x",
    "rpt_age_gender": f"""
        SELECT age_group, gender, COUNT(*) AS encounters, COUNT(DISTINCT patient_id) AS unique_patients
        FROM vw_encounter_detail WHERE {WINDOW} GROUP BY 1, 2 ORDER BY 1, 2""",
    "rpt_age_class": f"""
        SELECT age_group, encounterclass, COUNT(*) AS encounters
        FROM vw_encounter_detail WHERE {WINDOW} GROUP BY 1, 2 ORDER BY 1, 2""",
    "rpt_payer": f"""
        SELECT COALESCE(payer_name, '(unmatched)') AS payer_name, payer_ownership, COUNT(*) AS encounters,
               COUNT(DISTINCT patient_id) AS unique_patients, ROUND(SUM(total_claim_cost), 0) AS total_claim_cost,
               ROUND(100.0 * SUM(payer_coverage) / NULLIF(SUM(total_claim_cost), 0), 1) AS payer_covered_pct
        FROM vw_encounter_detail WHERE {WINDOW} GROUP BY 1, 2 ORDER BY encounters DESC""",
    "rpt_utilization_dist": f"""
        SELECT CASE WHEN n = 1 THEN '1' WHEN n <= 3 THEN '2-3' WHEN n <= 6 THEN '4-6'
                    WHEN n <= 10 THEN '7-10' ELSE '11+' END AS encounters_per_year,
               MIN(n) AS sort_key, COUNT(*) AS patient_years
        FROM (SELECT patient_id, encounter_year, encounters AS n FROM vw_patient_utilization
              WHERE encounter_year BETWEEN 2017 AND 2025) x
        GROUP BY 1 ORDER BY 2""",
    "rpt_top_organizations": f"""
        SELECT COALESCE(organization_name, '(unmatched)') AS organization_name, COUNT(*) AS encounters,
               COUNT(DISTINCT patient_id) AS unique_patients
        FROM vw_encounter_detail WHERE {WINDOW} GROUP BY 1 ORDER BY 2 DESC LIMIT 10""",
    "rpt_org_concentration": f"""
        SELECT COUNT(*) FILTER (WHERE cum_pct <= 50) + 1 AS orgs_for_half_of_volume, COUNT(*) AS orgs_with_encounters
        FROM (SELECT organization_name, 100.0 * SUM(COUNT(*)) OVER (ORDER BY COUNT(*) DESC) / SUM(COUNT(*)) OVER () AS cum_pct
              FROM vw_encounter_detail WHERE {WINDOW} GROUP BY organization_name) x""",
}

with connect() as con, con.cursor() as cur:
    cur.execute("SET TIME ZONE 'UTC'; SET search_path TO synthea")
    for name, q in QUERIES.items():
        cur.execute(q)
        df = pd.DataFrame(cur.fetchall(), columns=[d.name for d in cur.description])
        df.to_csv(OUT / f"{name}.csv", index=False)
        print(f"== {name} ({len(df)} rows)\n{df.head(12).to_string(index=False)}\n")
