-- 01_schema.sql  (PostgreSQL 16)
-- Creates the 9 source tables inside the current search_path schema.
-- The loader runs this once for the production copy (schema "synthea") and once for the
-- error-injected test copy (schema "synthea_test").
--
-- Keys are documented here but deliberately NOT enforced with PRIMARY KEY / FOREIGN KEY
-- constraints: the point of the project is to load data as received and let the validation
-- checks (sql/04_dq_checks.sql) find missing keys, orphans and duplicates. Logical keys:
--   patients.id, organizations.id, providers.id, payers.id, encounters.id      (unique)
--   providers.organization            -> organizations.id
--   encounters.patient / provider / organization / payer -> patients / providers / organizations / payers
--   conditions / procedures / medications / immunizations .encounter -> encounters.id
--   conditions / procedures / medications / immunizations .patient   -> patients.id
--   medications.payer                 -> payers.id

CREATE TABLE patients (
    _row_id             INTEGER,
    id                  TEXT,
    birthdate           DATE,
    deathdate           DATE,
    marital             TEXT,
    race                TEXT,
    ethnicity           TEXT,
    gender              TEXT,
    city                TEXT,
    state               TEXT,
    county              TEXT,
    zip                 TEXT,
    healthcare_expenses NUMERIC,
    healthcare_coverage NUMERIC,
    income              NUMERIC
);

CREATE TABLE organizations (
    _row_id     INTEGER,
    id          TEXT,
    name        TEXT,
    city        TEXT,
    state       TEXT,
    zip         TEXT,
    revenue     NUMERIC,
    utilization INTEGER
);

CREATE TABLE providers (
    _row_id      INTEGER,
    id           TEXT,
    organization TEXT,
    name         TEXT,
    gender       TEXT,
    speciality   TEXT,
    city         TEXT,
    state        TEXT,
    zip          TEXT,
    encounters   INTEGER,
    procedures   INTEGER
);

CREATE TABLE payers (
    _row_id   INTEGER,
    id        TEXT,
    name      TEXT,
    ownership TEXT
);

CREATE TABLE encounters (
    _row_id             INTEGER,
    id                  TEXT,
    start               TIMESTAMPTZ,
    stop                TIMESTAMPTZ,
    patient             TEXT,
    organization        TEXT,
    provider            TEXT,
    payer               TEXT,
    encounterclass      TEXT,
    code                TEXT,
    description         TEXT,
    base_encounter_cost NUMERIC,
    total_claim_cost    NUMERIC,
    payer_coverage      NUMERIC,
    reasoncode          TEXT,
    reasondescription   TEXT
);

CREATE TABLE conditions (
    _row_id     INTEGER,
    start       DATE,
    stop        DATE,
    patient     TEXT,
    encounter   TEXT,
    system      TEXT,
    code        TEXT,
    description TEXT
);

CREATE TABLE procedures (
    _row_id           INTEGER,
    start             TIMESTAMPTZ,
    stop              TIMESTAMPTZ,
    patient           TEXT,
    encounter         TEXT,
    system            TEXT,
    code              TEXT,
    description       TEXT,
    base_cost         NUMERIC,
    reasoncode        TEXT,
    reasondescription TEXT
);

CREATE TABLE medications (
    _row_id           INTEGER,
    start             TIMESTAMPTZ,
    stop              TIMESTAMPTZ,
    patient           TEXT,
    payer             TEXT,
    encounter         TEXT,
    code              TEXT,
    description       TEXT,
    base_cost         NUMERIC,
    payer_coverage    NUMERIC,
    dispenses         INTEGER,
    totalcost         NUMERIC,
    reasoncode        TEXT,
    reasondescription TEXT
);

CREATE TABLE immunizations (
    _row_id     INTEGER,
    date        TIMESTAMPTZ,
    patient     TEXT,
    encounter   TEXT,
    code        TEXT,
    description TEXT,
    base_cost   NUMERIC
);
