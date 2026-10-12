-- 04_dq_checks.sql  (PostgreSQL 16)
-- Data-quality checks in four groups: missing keys (MK), orphan records (OR),
-- duplicate identifiers (DU) and inconsistent dates (DT).
-- Every failing row is written to dq_exceptions with its table and _row_id, so results
-- can be traced back to source rows and scored against the injected-error log.
-- Outputs (current schema): dq_check_catalog, dq_exceptions, dq_results

SET TIME ZONE 'UTC';

DROP TABLE IF EXISTS dq_check_catalog CASCADE;
CREATE TABLE dq_check_catalog (
    check_id    TEXT PRIMARY KEY,
    category    TEXT,
    table_name  TEXT,
    description TEXT,
    severity    TEXT
);

INSERT INTO dq_check_catalog VALUES
-- Missing keys
('MK01','Missing key','patients',     'patients.id is null',                                   'Critical'),
('MK02','Missing key','encounters',   'encounters.id is null',                                 'Critical'),
('MK03','Missing key','encounters',   'encounters.patient is null',                            'Critical'),
('MK04','Missing key','encounters',   'encounters.provider is null',                           'High'),
('MK05','Missing key','encounters',   'encounters.organization is null',                       'High'),
('MK06','Missing key','encounters',   'encounters.payer is null',                              'High'),
('MK07','Missing key','providers',    'providers.organization is null',                        'Medium'),
('MK08','Missing key','conditions',   'conditions.patient or .encounter is null',              'High'),
('MK09','Missing key','procedures',   'procedures.patient or .encounter is null',              'High'),
('MK10','Missing key','medications',  'medications.patient or .encounter is null',             'High'),
('MK11','Missing key','immunizations','immunizations.patient or .encounter is null',           'High'),
-- Orphan records
('OR01','Orphan record','encounters',   'encounters.patient not found in patients',            'Critical'),
('OR02','Orphan record','encounters',   'encounters.provider not found in providers',          'High'),
('OR03','Orphan record','encounters',   'encounters.organization not found in organizations',  'High'),
('OR04','Orphan record','encounters',   'encounters.payer not found in payers',                'High'),
('OR05','Orphan record','providers',    'providers.organization not found in organizations',   'Medium'),
('OR06','Orphan record','conditions',   'conditions.encounter not found in encounters',        'High'),
('OR07','Orphan record','procedures',   'procedures.encounter not found in encounters',        'High'),
('OR08','Orphan record','medications',  'medications.encounter not found in encounters',       'High'),
('OR09','Orphan record','immunizations','immunizations.encounter not found in encounters',     'High'),
('OR10','Orphan record','clinical events','event patient differs from its encounter''s patient','High'),
-- Duplicate identifiers
('DU01','Duplicate identifier','patients',      'patients.id appears more than once',                     'Critical'),
('DU02','Duplicate identifier','encounters',    'encounters.id appears more than once',                   'Critical'),
('DU03','Duplicate identifier','providers',     'providers.id appears more than once',                    'High'),
('DU04','Duplicate identifier','organizations', 'organizations.id appears more than once',                'High'),
('DU05','Duplicate identifier','payers',        'payers.id appears more than once',                       'High'),
('DU06','Duplicate identifier','encounters',    'exact duplicate encounter row (all fields equal)',       'High'),
('DU07','Duplicate identifier','procedures',    'same patient + encounter + code + start recorded twice', 'Medium'),
('DU08','Duplicate identifier','immunizations', 'same patient + vaccine code + date recorded twice',      'Medium'),
-- Inconsistent dates
('DT01','Inconsistent date','encounters',   'encounter stop before start',                              'High'),
('DT02','Inconsistent date','encounters',   'encounter start before patient birthdate',                 'Critical'),
('DT03','Inconsistent date','encounters',   'encounter start more than 1 day after patient deathdate (excl. Death Certification)', 'Critical'),
('DT04','Inconsistent date','encounters',   'encounter start after data reference date (2026-09-30)',   'High'),
('DT05','Inconsistent date','patients',     'deathdate before birthdate',                               'Critical'),
('DT06','Inconsistent date','patients',     'birthdate after data reference date',                      'Critical'),
('DT07','Inconsistent date','procedures',   'procedure starts before its encounter or >24h after encounter stop', 'Medium'),
('DT08','Inconsistent date','procedures',   'procedure stop before start',                              'Medium'),
('DT09','Inconsistent date','conditions',   'condition stop before start',                              'Medium'),
('DT10','Inconsistent date','medications',  'medication stop before start',                             'Medium'),
('DT11','Inconsistent date','immunizations','immunization date differs from its encounter date',        'Medium');

DROP TABLE IF EXISTS dq_exceptions;
CREATE TABLE dq_exceptions (
    check_id   TEXT,
    table_name TEXT,
    row_id     INTEGER,
    record_key TEXT,
    detail     TEXT
);

-- ======================================================= Missing keys
INSERT INTO dq_exceptions SELECT 'MK01','patients',_row_id,id,NULL FROM patients WHERE id IS NULL;
INSERT INTO dq_exceptions SELECT 'MK02','encounters',_row_id,id,NULL FROM encounters WHERE id IS NULL;
INSERT INTO dq_exceptions SELECT 'MK03','encounters',_row_id,id,NULL FROM encounters WHERE patient IS NULL;
INSERT INTO dq_exceptions SELECT 'MK04','encounters',_row_id,id,NULL FROM encounters WHERE provider IS NULL;
INSERT INTO dq_exceptions SELECT 'MK05','encounters',_row_id,id,NULL FROM encounters WHERE organization IS NULL;
INSERT INTO dq_exceptions SELECT 'MK06','encounters',_row_id,id,NULL FROM encounters WHERE payer IS NULL;
INSERT INTO dq_exceptions SELECT 'MK07','providers',_row_id,id,NULL FROM providers WHERE organization IS NULL;
INSERT INTO dq_exceptions SELECT 'MK08','conditions',_row_id,encounter,NULL FROM conditions WHERE patient IS NULL OR encounter IS NULL;
INSERT INTO dq_exceptions SELECT 'MK09','procedures',_row_id,encounter,NULL FROM procedures WHERE patient IS NULL OR encounter IS NULL;
INSERT INTO dq_exceptions SELECT 'MK10','medications',_row_id,encounter,NULL FROM medications WHERE patient IS NULL OR encounter IS NULL;
INSERT INTO dq_exceptions SELECT 'MK11','immunizations',_row_id,encounter,NULL FROM immunizations WHERE patient IS NULL OR encounter IS NULL;

-- ======================================================= Orphan records (non-null key with no parent)
INSERT INTO dq_exceptions SELECT 'OR01','encounters',e._row_id,e.id,e.patient FROM encounters e
  WHERE e.patient IS NOT NULL AND NOT EXISTS (SELECT 1 FROM patients p WHERE p.id = e.patient);
INSERT INTO dq_exceptions SELECT 'OR02','encounters',e._row_id,e.id,e.provider FROM encounters e
  WHERE e.provider IS NOT NULL AND NOT EXISTS (SELECT 1 FROM providers p WHERE p.id = e.provider);
INSERT INTO dq_exceptions SELECT 'OR03','encounters',e._row_id,e.id,e.organization FROM encounters e
  WHERE e.organization IS NOT NULL AND NOT EXISTS (SELECT 1 FROM organizations o WHERE o.id = e.organization);
INSERT INTO dq_exceptions SELECT 'OR04','encounters',e._row_id,e.id,e.payer FROM encounters e
  WHERE e.payer IS NOT NULL AND NOT EXISTS (SELECT 1 FROM payers p WHERE p.id = e.payer);
INSERT INTO dq_exceptions SELECT 'OR05','providers',p._row_id,p.id,p.organization FROM providers p
  WHERE p.organization IS NOT NULL AND NOT EXISTS (SELECT 1 FROM organizations o WHERE o.id = p.organization);
INSERT INTO dq_exceptions SELECT 'OR06','conditions',c._row_id,c.encounter,NULL FROM conditions c
  WHERE c.encounter IS NOT NULL AND NOT EXISTS (SELECT 1 FROM encounters e WHERE e.id = c.encounter);
INSERT INTO dq_exceptions SELECT 'OR07','procedures',c._row_id,c.encounter,NULL FROM procedures c
  WHERE c.encounter IS NOT NULL AND NOT EXISTS (SELECT 1 FROM encounters e WHERE e.id = c.encounter);
INSERT INTO dq_exceptions SELECT 'OR08','medications',c._row_id,c.encounter,NULL FROM medications c
  WHERE c.encounter IS NOT NULL AND NOT EXISTS (SELECT 1 FROM encounters e WHERE e.id = c.encounter);
INSERT INTO dq_exceptions SELECT 'OR09','immunizations',c._row_id,c.encounter,NULL FROM immunizations c
  WHERE c.encounter IS NOT NULL AND NOT EXISTS (SELECT 1 FROM encounters e WHERE e.id = c.encounter);
INSERT INTO dq_exceptions
SELECT 'OR10', t.table_name, t._row_id, t.encounter, 'event patient ' || t.patient || ' vs encounter patient ' || e.patient
FROM (
    SELECT 'conditions' AS table_name, _row_id, patient, encounter FROM conditions
    UNION ALL SELECT 'procedures',    _row_id, patient, encounter FROM procedures
    UNION ALL SELECT 'medications',   _row_id, patient, encounter FROM medications
    UNION ALL SELECT 'immunizations', _row_id, patient, encounter FROM immunizations
) t
JOIN encounters e ON e.id = t.encounter
WHERE t.patient IS NOT NULL AND e.patient IS NOT NULL AND t.patient <> e.patient;

-- ======================================================= Duplicate identifiers
INSERT INTO dq_exceptions SELECT 'DU01','patients',_row_id,id,NULL FROM
  (SELECT _row_id, id, COUNT(*) OVER (PARTITION BY id) AS n FROM patients WHERE id IS NOT NULL) x WHERE n > 1;
INSERT INTO dq_exceptions SELECT 'DU02','encounters',_row_id,id,NULL FROM
  (SELECT _row_id, id, COUNT(*) OVER (PARTITION BY id) AS n FROM encounters WHERE id IS NOT NULL) x WHERE n > 1;
INSERT INTO dq_exceptions SELECT 'DU03','providers',_row_id,id,NULL FROM
  (SELECT _row_id, id, COUNT(*) OVER (PARTITION BY id) AS n FROM providers WHERE id IS NOT NULL) x WHERE n > 1;
INSERT INTO dq_exceptions SELECT 'DU04','organizations',_row_id,id,NULL FROM
  (SELECT _row_id, id, COUNT(*) OVER (PARTITION BY id) AS n FROM organizations WHERE id IS NOT NULL) x WHERE n > 1;
INSERT INTO dq_exceptions SELECT 'DU05','payers',_row_id,id,NULL FROM
  (SELECT _row_id, id, COUNT(*) OVER (PARTITION BY id) AS n FROM payers WHERE id IS NOT NULL) x WHERE n > 1;
INSERT INTO dq_exceptions SELECT 'DU06','encounters',_row_id,id,NULL FROM
  (SELECT _row_id, id, COUNT(*) OVER (PARTITION BY id, start, stop, patient, organization, provider, payer,
          encounterclass, code, description, base_encounter_cost, total_claim_cost, payer_coverage,
          reasoncode, reasondescription) AS n FROM encounters) x WHERE n > 1;
INSERT INTO dq_exceptions SELECT 'DU07','procedures',_row_id,encounter,code FROM
  (SELECT _row_id, encounter, code, COUNT(*) OVER (PARTITION BY patient, encounter, code, start) AS n FROM procedures) x WHERE n > 1;
INSERT INTO dq_exceptions SELECT 'DU08','immunizations',_row_id,encounter,code FROM
  (SELECT _row_id, encounter, code, COUNT(*) OVER (PARTITION BY patient, code, date) AS n FROM immunizations) x WHERE n > 1;

-- ======================================================= Inconsistent dates
INSERT INTO dq_exceptions SELECT 'DT01','encounters',_row_id,id,start || ' > ' || stop FROM encounters WHERE stop < start;
INSERT INTO dq_exceptions SELECT 'DT02','encounters',e._row_id,e.id,e.start::date || ' < birth ' || p.birthdate
  FROM encounters e JOIN patients p ON p.id = e.patient WHERE e.start::date < p.birthdate;
INSERT INTO dq_exceptions SELECT 'DT03','encounters',e._row_id,e.id,e.start::date || ' > death ' || p.deathdate
  FROM encounters e JOIN patients p ON p.id = e.patient WHERE p.deathdate IS NOT NULL AND e.start::date > p.deathdate + 1
    AND e.code IS DISTINCT FROM '308646001';   -- exception rule: Death Certification is recorded after death by design
INSERT INTO dq_exceptions SELECT 'DT04','encounters',_row_id,id,start::date::text FROM encounters WHERE start::date > DATE '2026-09-30';
INSERT INTO dq_exceptions SELECT 'DT05','patients',_row_id,id,deathdate || ' < ' || birthdate FROM patients WHERE deathdate < birthdate;
INSERT INTO dq_exceptions SELECT 'DT06','patients',_row_id,id,birthdate::text FROM patients WHERE birthdate > DATE '2026-09-30';
INSERT INTO dq_exceptions SELECT 'DT07','procedures',c._row_id,c.encounter,c.start || ' outside ' || e.start || ' - ' || e.stop
  FROM procedures c JOIN encounters e ON e.id = c.encounter
  WHERE c.start < e.start OR c.start > COALESCE(e.stop, e.start) + INTERVAL '24 hours';   -- exception rule: Synthea sequences procedures after a short encounter closes
INSERT INTO dq_exceptions SELECT 'DT08','procedures',_row_id,encounter,NULL FROM procedures WHERE stop < start;
INSERT INTO dq_exceptions SELECT 'DT09','conditions',_row_id,encounter,NULL FROM conditions WHERE stop < start;
INSERT INTO dq_exceptions SELECT 'DT10','medications',_row_id,encounter,NULL FROM medications WHERE stop < start;
INSERT INTO dq_exceptions SELECT 'DT11','immunizations',c._row_id,c.encounter,c.date::date || ' vs ' || e.start::date
  FROM immunizations c JOIN encounters e ON e.id = c.encounter WHERE c.date::date <> e.start::date;

-- ======================================================= Summary
DROP TABLE IF EXISTS dq_results;
CREATE TABLE dq_results AS
SELECT c.check_id, c.category, c.table_name, c.description, c.severity,
       COUNT(x.row_id)                                AS rows_flagged,
       CASE WHEN COUNT(x.row_id) = 0 THEN 'PASS' ELSE 'FAIL' END AS status
FROM dq_check_catalog c
LEFT JOIN dq_exceptions x ON x.check_id = c.check_id
GROUP BY c.check_id, c.category, c.table_name, c.description, c.severity
ORDER BY c.check_id;
