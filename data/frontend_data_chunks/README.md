# Frontend Data Chunks

Derived from the four AI data CSVs supplied to the project. The original datasets are preserved unchanged under `source_originals/`.

## What to use

- `districts.json` — district selector/index.
- `district_intelligence/json/<District>.json` — sector intelligence for one district.
- `district_intelligence/csv/<District>.csv` — same data for easy Excel scanning.
- `state/indicators.json` — state-level indicators.
- `trades/trade_competencies.json` — the supplied trade-to-competency reference.
- `jobs/ncs_job_listings.json` — complete supplied NCS snapshot.
- `jobs/by_district/<District>.csv` — small district-specific job-listing chunks.

## Recommended frontend flow

1. Load `districts.json` for the dropdown.
2. On district selection, load that district's JSON from `district_intelligence/json/`.
3. Use the returned records for sector cards/charts.
4. Use `state/indicators.json` only for statewide context.
5. Use `trades/trade_competencies.json` only where the UI explicitly shows the supplied competency reference.
6. Treat the NCS listings as a snapshot, not a live job feed.

## Important

These are **derived frontend chunks**, not a replacement for the project's PostgreSQL/API source of truth. Keep the source CSVs and backend data pipeline authoritative. The chunking only makes the supplied data easier to scan and consume.

No missing values were invented, inferred, or silently corrected.
