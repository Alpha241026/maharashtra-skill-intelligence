-- Maharashtra Skill Intelligence Platform
-- MVP PostgreSQL Schema

DROP TABLE IF EXISTS iti_offerings CASCADE;
DROP TABLE IF EXISTS iti_institutes CASCADE;
DROP TABLE IF EXISTS district_sector_intelligence CASCADE;
DROP TABLE IF EXISTS trade_skill_reference CASCADE;
DROP TABLE IF EXISTS sectors CASCADE;
DROP TABLE IF EXISTS districts CASCADE;

CREATE TABLE districts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE sectors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);

CREATE TABLE district_sector_intelligence (
    id SERIAL PRIMARY KEY,
    district_id INTEGER NOT NULL REFERENCES districts(id),
    sector_id INTEGER NOT NULL REFERENCES sectors(id),

    industry_opportunity_score NUMERIC,
    training_pressure_score NUMERIC,
    evidence_confidence NUMERIC,
    projection_available BOOLEAN,

    industry_size NUMERIC,
    organization_count NUMERIC,
    candidate_aspiration NUMERIC,
    mssds_trained_2022_23 NUMERIC,
    dsdp_training NUMERIC,
    projected_training NUMERIC,

    source TEXT,

    UNIQUE (district_id, sector_id)
);

CREATE TABLE iti_institutes (
    id SERIAL PRIMARY KEY,
    district_id INTEGER NOT NULL REFERENCES districts(id),

    taluka VARCHAR(150),
    iti_type VARCHAR(50),
    iti_name TEXT NOT NULL,

    source TEXT,
    source_file TEXT
);

CREATE TABLE iti_offerings (
    id SERIAL PRIMARY KEY,
    iti_id INTEGER NOT NULL REFERENCES iti_institutes(id),

    trade_name TEXT NOT NULL,
    admission_year VARCHAR(20),
    intake INTEGER,
    pdf_page INTEGER,

    source TEXT
);

CREATE TABLE trade_skill_reference (
    id SERIAL PRIMARY KEY,

    trade TEXT UNIQUE NOT NULL,
    competency_summary TEXT,

    official_source TEXT,
    source_url TEXT,
    source_type TEXT,
    evidence TEXT
);

-- Helpful indexes for API queries
CREATE INDEX idx_dsi_district
    ON district_sector_intelligence(district_id);

CREATE INDEX idx_dsi_sector
    ON district_sector_intelligence(sector_id);

CREATE INDEX idx_iti_district
    ON iti_institutes(district_id);

CREATE INDEX idx_offerings_iti
    ON iti_offerings(iti_id);

CREATE INDEX idx_offerings_trade
    ON iti_offerings(trade_name);