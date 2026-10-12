-- 03_reconciliation.sql  (PostgreSQL 16)
-- Reconciles encounter counts before and after each join used by the reporting layer.
--   * INNER JOIN steps show how many encounters would be silently dropped by orphan keys.
--   * LEFT JOIN step shows whether duplicate dimension keys fan out (inflate) the row count.
--   * Roll-up steps prove every aggregate view adds back to the detail view.
-- Result: table recon_encounter_counts (one row per step) in the current schema.

DROP TABLE IF EXISTS recon_encounter_counts;
CREATE TABLE recon_encounter_counts AS
WITH base AS (SELECT COUNT(*) AS n FROM encounters),
steps AS (
    SELECT 1 AS step, 'Source: encounters table' AS description, 'base' AS join_type,
           (SELECT COUNT(*) FROM encounters) AS row_count
    UNION ALL
    SELECT 2, 'INNER JOIN patients', 'inner',
           (SELECT COUNT(*) FROM encounters e JOIN patients p ON p.id = e.patient)
    UNION ALL
    SELECT 3, '+ INNER JOIN providers', 'inner',
           (SELECT COUNT(*) FROM encounters e
              JOIN patients p ON p.id = e.patient
              JOIN providers pr ON pr.id = e.provider)
    UNION ALL
    SELECT 4, '+ INNER JOIN organizations', 'inner',
           (SELECT COUNT(*) FROM encounters e
              JOIN patients p ON p.id = e.patient
              JOIN providers pr ON pr.id = e.provider
              JOIN organizations o ON o.id = e.organization)
    UNION ALL
    SELECT 5, '+ INNER JOIN payers', 'inner',
           (SELECT COUNT(*) FROM encounters e
              JOIN patients p ON p.id = e.patient
              JOIN providers pr ON pr.id = e.provider
              JOIN organizations o ON o.id = e.organization
              JOIN payers py ON py.id = e.payer)
    UNION ALL
    SELECT 6, 'Reporting view vw_encounter_detail (4 LEFT JOINs)', 'left',
           (SELECT COUNT(*) FROM vw_encounter_detail)
    UNION ALL
    SELECT 7, 'Distinct encounter IDs in vw_encounter_detail', 'distinct',
           (SELECT COUNT(DISTINCT encounter_id) FROM vw_encounter_detail)
    UNION ALL
    SELECT 8, 'Roll-up: SUM(vw_encounter_class_summary.encounters)', 'rollup',
           (SELECT SUM(encounters) FROM vw_encounter_class_summary)
    UNION ALL
    SELECT 9, 'Roll-up: SUM(vw_encounter_volume_monthly.encounters)', 'rollup',
           (SELECT SUM(encounters) FROM vw_encounter_volume_monthly)
    UNION ALL
    SELECT 10, 'Roll-up: SUM(vw_encounter_by_payer.encounters)', 'rollup',
           (SELECT SUM(encounters) FROM vw_encounter_by_payer)
    UNION ALL
    SELECT 11, 'Roll-up: SUM(vw_patient_utilization.encounters)', 'rollup',
           (SELECT SUM(encounters) FROM vw_patient_utilization)
)
SELECT s.step,
       s.description,
       s.join_type,
       s.row_count,
       s.row_count - LAG(s.row_count) OVER (ORDER BY s.step) AS change_vs_previous_step,
       s.row_count - b.n                                       AS change_vs_source,
       CASE WHEN s.row_count = b.n THEN 'PASS' ELSE 'FAIL' END AS status
FROM steps s CROSS JOIN base b
ORDER BY s.step;

-- Child-table linkage: share of clinical event rows that join back to an encounter
DROP TABLE IF EXISTS recon_child_linkage;
CREATE TABLE recon_child_linkage AS
SELECT t.table_name, t.source_rows, t.linked_rows,
       t.source_rows - t.linked_rows AS unlinked_rows,
       ROUND(100.0 * t.linked_rows / NULLIF(t.source_rows, 0), 2) AS linked_pct
FROM (
    SELECT 'conditions' AS table_name, (SELECT COUNT(*) FROM conditions) AS source_rows,
           (SELECT COUNT(*) FROM conditions c WHERE EXISTS (SELECT 1 FROM encounters e WHERE e.id = c.encounter)) AS linked_rows
    UNION ALL
    SELECT 'procedures', (SELECT COUNT(*) FROM procedures),
           (SELECT COUNT(*) FROM procedures c WHERE EXISTS (SELECT 1 FROM encounters e WHERE e.id = c.encounter))
    UNION ALL
    SELECT 'medications', (SELECT COUNT(*) FROM medications),
           (SELECT COUNT(*) FROM medications c WHERE EXISTS (SELECT 1 FROM encounters e WHERE e.id = c.encounter))
    UNION ALL
    SELECT 'immunizations', (SELECT COUNT(*) FROM immunizations),
           (SELECT COUNT(*) FROM immunizations c WHERE EXISTS (SELECT 1 FROM encounters e WHERE e.id = c.encounter))
) t;
