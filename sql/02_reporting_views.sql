-- 02_reporting_views.sql  (PostgreSQL 16)
-- Reporting layer for encounter volume and visit-type analysis.
-- Built on the 9 source tables; created in whichever schema is first on the search_path.

-- ---------------------------------------------------------------------------
-- 1. Encounter detail: one row per encounter, enriched with patient, provider,
--    organization and payer attributes. LEFT JOINs keep every encounter so that
--    orphans surface as NULL attributes instead of silently disappearing; the
--    reconciliation in 03_reconciliation.sql proves the row count is unchanged.
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_encounter_detail AS
SELECT
    e.id                                                     AS encounter_id,
    e.patient                                                AS patient_id,
    e.provider                                               AS provider_id,
    e.organization                                           AS organization_id,
    e.payer                                                  AS payer_id,
    e.start                                                  AS start_ts,
    e.stop                                                   AS stop_ts,
    e.start::date                                            AS encounter_date,
    EXTRACT(YEAR FROM e.start)::int                          AS encounter_year,
    DATE_TRUNC('month', e.start)::date                       AS encounter_month,
    ROUND(EXTRACT(EPOCH FROM (e.stop - e.start)) / 60.0, 1)  AS duration_minutes,
    e.encounterclass,
    e.code                                                   AS visit_code,
    e.description                                            AS visit_description,
    e.reasondescription                                      AS reason_description,
    e.base_encounter_cost,
    e.total_claim_cost,
    e.payer_coverage,
    p.gender,
    p.race,
    p.ethnicity,
    DATE_PART('year', AGE(e.start::date, p.birthdate))::int  AS age_at_encounter,
    CASE
        WHEN p.birthdate IS NULL                                   THEN 'Unknown'
        WHEN DATE_PART('year', AGE(e.start::date, p.birthdate)) < 18 THEN '0-17'
        WHEN DATE_PART('year', AGE(e.start::date, p.birthdate)) < 40 THEN '18-39'
        WHEN DATE_PART('year', AGE(e.start::date, p.birthdate)) < 65 THEN '40-64'
        ELSE '65+'
    END                                                      AS age_group,
    (p.deathdate IS NOT NULL)                                AS patient_deceased,
    pr.speciality                                            AS provider_specialty,
    o.name                                                   AS organization_name,
    py.name                                                  AS payer_name,
    py.ownership                                             AS payer_ownership,
    (e.start >= TIMESTAMPTZ '2016-10-01 00:00:00+00'
     AND e.start <  TIMESTAMPTZ '2026-10-01 00:00:00+00')    AS in_reporting_window,   -- 10-year window Oct 2016 - Sep 2026
    (p.id  IS NOT NULL)                                      AS has_patient,
    (pr.id IS NOT NULL)                                      AS has_provider,
    (o.id  IS NOT NULL)                                      AS has_organization,
    (py.id IS NOT NULL)                                      AS has_payer
FROM encounters e
LEFT JOIN patients      p  ON p.id  = e.patient
LEFT JOIN providers     pr ON pr.id = e.provider
LEFT JOIN organizations o  ON o.id  = e.organization
LEFT JOIN payers        py ON py.id = e.payer;

-- ---------------------------------------------------------------------------
-- 2. Monthly encounter volume by encounter class
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_encounter_volume_monthly AS
SELECT encounter_month,
       encounterclass,
       COUNT(*)                   AS encounters,
       COUNT(DISTINCT patient_id) AS unique_patients
FROM vw_encounter_detail
GROUP BY encounter_month, encounterclass;

-- ---------------------------------------------------------------------------
-- 3. Encounter class summary (the "visit type" roll-up)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_encounter_class_summary AS
SELECT encounterclass,
       COUNT(*)                                                         AS encounters,
       ROUND(100.0 * COUNT(*) / SUM(COUNT(*)) OVER (), 2)               AS pct_of_encounters,
       COUNT(DISTINCT patient_id)                                       AS unique_patients,
       ROUND(1.0 * COUNT(*) / NULLIF(COUNT(DISTINCT patient_id), 0), 2) AS encounters_per_patient,
       ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY duration_minutes)::numeric, 1) AS median_duration_min,
       ROUND(AVG(total_claim_cost), 2)                                  AS avg_claim_cost,
       ROUND(100.0 * SUM(payer_coverage) / NULLIF(SUM(total_claim_cost), 0), 1) AS payer_covered_pct
FROM vw_encounter_detail
GROUP BY encounterclass;

-- ---------------------------------------------------------------------------
-- 4. Visit types (SNOMED encounter code) ranked within each class
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_visit_type_summary AS
SELECT encounterclass,
       visit_code,
       visit_description,
       COUNT(*)                   AS encounters,
       COUNT(DISTINCT patient_id) AS unique_patients,
       RANK() OVER (PARTITION BY encounterclass ORDER BY COUNT(*) DESC) AS rank_in_class
FROM vw_encounter_detail
GROUP BY encounterclass, visit_code, visit_description;

-- ---------------------------------------------------------------------------
-- 5. Encounters by age group and gender
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_encounter_by_age_gender AS
SELECT age_group,
       gender,
       encounterclass,
       COUNT(*)                   AS encounters,
       COUNT(DISTINCT patient_id) AS unique_patients
FROM vw_encounter_detail
GROUP BY age_group, gender, encounterclass;

-- ---------------------------------------------------------------------------
-- 6. Encounters and cost coverage by payer
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_encounter_by_payer AS
SELECT COALESCE(payer_name, '(unmatched payer)') AS payer_name,
       payer_ownership,
       COUNT(*)                                  AS encounters,
       COUNT(DISTINCT patient_id)                AS unique_patients,
       ROUND(SUM(total_claim_cost), 0)           AS total_claim_cost,
       ROUND(100.0 * SUM(payer_coverage) / NULLIF(SUM(total_claim_cost), 0), 1) AS payer_covered_pct
FROM vw_encounter_detail
GROUP BY COALESCE(payer_name, '(unmatched payer)'), payer_ownership;

-- ---------------------------------------------------------------------------
-- 7. Encounters per patient per year (utilization)
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_patient_utilization AS
SELECT patient_id,
       encounter_year,
       COUNT(*)                                                    AS encounters,
       COUNT(*) FILTER (WHERE encounterclass IN ('emergency', 'urgentcare')) AS acute_visits,
       COUNT(*) FILTER (WHERE encounterclass = 'inpatient')        AS inpatient_stays,
       COUNT(*) FILTER (WHERE encounterclass = 'wellness')         AS wellness_visits
FROM vw_encounter_detail
GROUP BY patient_id, encounter_year;

-- ---------------------------------------------------------------------------
-- 8. Organization volume
-- ---------------------------------------------------------------------------
CREATE OR REPLACE VIEW vw_organization_volume AS
SELECT COALESCE(organization_name, '(unmatched organization)') AS organization_name,
       COUNT(*)                    AS encounters,
       COUNT(DISTINCT patient_id)  AS unique_patients,
       COUNT(DISTINCT provider_id) AS providers_seen,
       MODE() WITHIN GROUP (ORDER BY encounterclass) AS most_common_class
FROM vw_encounter_detail
GROUP BY COALESCE(organization_name, '(unmatched organization)');
