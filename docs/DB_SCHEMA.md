# Database Schema

## Maharashtra Skill Intelligence Platform — MVP

This document defines the PostgreSQL schema for the MVP.

The schema is based on the currently available source datasets:

1. MSSDS district-sector intelligence data
2. Maharashtra ITI trade-supply data
3. Official trade/skill reference data

The database should store source/observational data cleanly and allow FastAPI and the AI/ML layer to derive dashboard intelligence from it.

---

## 1. Design Principles

* PostgreSQL is the persistent source of truth for structured project data.
* Districts and sectors use normalized reference tables.
* MSSDS intelligence is represented at District × Sector level.
* ITI supply is represented at ITI × Trade level.
* Source/provenance fields are retained wherever practical.
* ML predictions are derived from stored data and are not treated as independent source records.
* Do not represent a computed value as an official government statistic.
* The current MVP does not claim a true skill shortage/surplus unless an appropriate demand-to-trade/skill mapping exists.
* The current `SupplyAlignmentEngine` comparison is treated as a potential training-capacity alignment signal, not a definitive skill-gap measurement.

---

# 2. Entity Overview

```
districts
    │
    ├───────────────┐
    │               │
    ↓               ↓
district_sector_    iti_institutes
intelligence             │
                         ↓
                    iti_offerings

sectors
    │
    └──────────────→ district_sector_intelligence

trade_skill_reference
    │
    └── official competency/reference information
```

---

# 3. Table: `districts`

Stores the Maharashtra districts used throughout the application.

### Columns

| Column | Type         | Constraints      | Description                  |
| ------ | ------------ | ---------------- | ---------------------------- |
| `id`   | SERIAL       | PRIMARY KEY      | Internal district identifier |
| `name` | VARCHAR(100) | UNIQUE, NOT NULL | District name                |

### Expected data

The current MSSDS and ITI datasets cover 36 districts.

### SQL

```
CREATE TABLE districts (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);
```

---

# 4. Table: `sectors`

Stores normalized sector names used by the MSSDS intelligence dataset.

### Columns

| Column | Type         | Constraints      | Description                |
| ------ | ------------ | ---------------- | -------------------------- |
| `id`   | SERIAL       | PRIMARY KEY      | Internal sector identifier |
| `name` | VARCHAR(100) | UNIQUE, NOT NULL | Sector name                |

### Expected data

The current MSSDS intelligence dataset contains 38 sectors.

### SQL

```
CREATE TABLE sectors (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL
);
```

---

# 5. Table: `district_sector_intelligence`

Stores MSSDS district-sector intelligence.

One row represents one District × Sector observation.

This table is the primary source for the projected-training-demand dashboard.

### Columns

| Column                       | Type    | Constraints                  | Description                                      |
| ---------------------------- | ------- | ---------------------------- | ------------------------------------------------ |
| `id`                         | SERIAL  | PRIMARY KEY                  | Internal record identifier                       |
| `district_id`                | INTEGER | FK → districts(id), NOT NULL | District                                         |
| `sector_id`                  | INTEGER | FK → sectors(id), NOT NULL   | Sector                                           |
| `industry_opportunity_score` | NUMERIC |                              | Industry opportunity score                       |
| `training_pressure_score`    | NUMERIC |                              | Training pressure score                          |
| `evidence_confidence`        | NUMERIC |                              | Confidence/evidence score                        |
| `projection_available`       | BOOLEAN |                              | Whether projection can be generated              |
| `industry_size`              | NUMERIC |                              | Industry-size feature                            |
| `organization_count`         | NUMERIC |                              | Organization-count feature                       |
| `candidate_aspiration`       | NUMERIC |                              | Candidate-aspiration feature                     |
| `mssds_trained_2022_23`      | NUMERIC |                              | Historical MSSDS training value                  |
| `dsdp_training`              | NUMERIC |                              | DSDP training value                              |
| `projected_training`         | NUMERIC |                              | Existing projected-training value in source data |
| `source`                     | TEXT    |                              | Source/provenance information                    |

### Constraints

```
UNIQUE (district_id, sector_id)
```

### SQL

```
CREATE TABLE district_sector_intelligence (
    id SERIAL PRIMARY KEY,

    district_id INTEGER NOT NULL
        REFERENCES districts(id),

    sector_id INTEGER NOT NULL
        REFERENCES sectors(id),

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
```

---

# 6. Table: `iti_institutes`

Stores individual ITI institutions.

The current ITI source contains information for 828 ITIs.

### Columns

| Column        | Type         | Constraints                  | Description             |
| ------------- | ------------ | ---------------------------- | ----------------------- |
| `id`          | SERIAL       | PRIMARY KEY                  | Internal ITI identifier |
| `district_id` | INTEGER      | FK → districts(id), NOT NULL | District                |
| `taluka`      | VARCHAR(150) |                              | Taluka                  |
| `iti_type`    | VARCHAR(50)  |                              | ITI type                |
| `iti_name`    | TEXT         | NOT NULL                     | ITI name                |
| `source`      | TEXT         |                              | Source/provenance       |
| `source_file` | TEXT         |                              | Original source file    |

### SQL

```
CREATE TABLE iti_institutes (
    id SERIAL PRIMARY KEY,

    district_id INTEGER NOT NULL
        REFERENCES districts(id),

    taluka VARCHAR(150),
    iti_type VARCHAR(50),
    iti_name TEXT NOT NULL,

    source TEXT,
    source_file TEXT
);
```

---

# 7. Table: `iti_offerings`

Stores trades offered by individual ITIs.

One row represents one ITI × Trade × Admission Year record.

### Columns

| Column           | Type        | Constraints                       | Description                |
| ---------------- | ----------- | --------------------------------- | -------------------------- |
| `id`             | SERIAL      | PRIMARY KEY                       | Internal record identifier |
| `iti_id`         | INTEGER     | FK → iti_institutes(id), NOT NULL | ITI                        |
| `trade_name`     | TEXT        | NOT NULL                          | Trade name                 |
| `admission_year` | VARCHAR(20) |                                   | Admission year             |
| `intake`         | INTEGER     |                                   | Available intake           |
| `pdf_page`       | INTEGER     |                                   | Source PDF page            |
| `source`         | TEXT        |                                   | Source/provenance          |

### SQL

```
CREATE TABLE iti_offerings (
    id SERIAL PRIMARY KEY,

    iti_id INTEGER NOT NULL
        REFERENCES iti_institutes(id),

    trade_name TEXT NOT NULL,
    admission_year VARCHAR(20),
    intake INTEGER,
    pdf_page INTEGER,

    source TEXT
);
```

---

# 8. Table: `trade_skill_reference`

Stores official competency/reference information for trades currently covered by the supplied reference dataset.

**This is NOT a complete catalogue of all ITI trades.**

The current reference dataset contains 8 trades.

### Current trades

* Electrician
* Fitter
* Welder
* COPA
* Electronics Mechanic
* Plumber
* Aerospace Structure and Equipment Fitter
* Draughtsman (Civil)

### Columns

| Column               | Type   | Constraints      | Description                   |
| -------------------- | ------ | ---------------- | ----------------------------- |
| `id`                 | SERIAL | PRIMARY KEY      | Internal identifier           |
| `trade`              | TEXT   | UNIQUE, NOT NULL | Trade name                    |
| `competency_summary` | TEXT   |                  | Competency information        |
| `official_source`    | TEXT   |                  | Official source name          |
| `source_url`         | TEXT   |                  | Source URL                    |
| `source_type`        | TEXT   |                  | Type of official source       |
| `evidence`           | TEXT   |                  | Supporting evidence/reference |

### SQL

```
CREATE TABLE trade_skill_reference (
    id SERIAL PRIMARY KEY,

    trade TEXT UNIQUE NOT NULL,
    competency_summary TEXT,

    official_source TEXT,
    source_url TEXT,
    source_type TEXT,
    evidence TEXT
);
```

---

# 9. Relationships

```
districts
    │
    ├── 1 : N ── district_sector_intelligence
    │
    └── 1 : N ── iti_institutes
                       │
                       └── 1 : N ── iti_offerings

sectors
    │
    └── 1 : N ── district_sector_intelligence
```

---

# 10. ML / Derived Data

The `ProjectedTrainingIntelligence` module can generate a projected training requirement for a District × Sector.

Conceptually:

```
district + sector
       ↓
district_sector_intelligence
       ↓
ProjectedTrainingIntelligence
       ↓
predicted_projected_training
       ↓
demand_band
```

The current model uses the available MSSDS features and produces a projected training value.

The current demand bands are:

```
>= 500       High
100–499.99   Moderate
< 100        Low
```

These labels describe the project's model output and should not be presented as official government classifications.

---

# 11. Supply Alignment

The current `SupplyAlignmentEngine` compares:

```
predicted training demand
            vs
district-wide ITI intake
```

This is currently a broad capacity comparison.

It does **NOT** establish a validated mapping between:

```
industry sector
        ↕
specific ITI trade
        ↕
specific skill
```

Therefore:

* Do not label its raw difference as a definitive skill shortage.
* Do not claim that a negative value proves excess capacity.
* If displayed, label it as a potential training-capacity alignment signal and provide appropriate context.

---

# 12. Current MVP Scope

The database currently supports:

### Demand

```
District × Sector
```

### Training supply

```
District × ITI × Trade
```

### Official trade reference

```
Trade × Competency/reference information
```

The database does **NOT** currently claim:

```
Skill × District shortage
Course × Skill gap
Industry job × Skill demand
Sector × Trade shortage
```

Those require additional validated mappings/data.

---

# 13. Data Provenance

Source fields should be retained wherever available.

For imported datasets, preserve:

* original source
* source file
* source period/year where available
* PDF page where applicable

Derived values produced by the project's ML/model code should be clearly identified as derived/modelled values.

---

# 14. Seed / Import Order

Recommended import order:

```
1. districts
2. sectors
3. iti_institutes
4. iti_offerings
5. district_sector_intelligence
6. trade_skill_reference
```

Foreign-key dependencies should be satisfied before child records are inserted.

---

# 15. MVP Principle

Keep the schema small.

Do not add tables for:

* users
* authentication
* employers
* trainers
* equipment
* courses
* job portals
* skill shortages
* forecasting
* recommendations

unless the team obtains the required data and the feature becomes necessary for the MVP.

The current objective is:

```
Real source data
      ↓
  PostgreSQL
      ↓
   FastAPI
      ↓
     JSON
      ↓
 React dashboard
```
