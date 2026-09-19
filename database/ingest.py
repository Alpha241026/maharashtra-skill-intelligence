import os
import pandas as pd
import psycopg
from pathlib import Path
from dotenv import load_dotenv

# Load .env from repository root so DATABASE_URL is available when running locally
_env = Path(__file__).resolve().parent.parent / ".env"
if _env.exists():
    load_dotenv(dotenv_path=_env)
else:
    load_dotenv()

# ── Connection ───────────────────────────────────────────────────────────────
DATABASE_URL = os.environ.get("DATABASE_URL")
if not DATABASE_URL:
    raise SystemExit(
        "ERROR: DATABASE_URL environment variable is not set.\n"
        "Set it in your .env file or shell before running ingest.py."
    )

BASE_DIR   = Path(__file__).resolve().parent.parent
MSSDS_FILE = str(BASE_DIR / "data" / "outputs"   / "mssds_district_sector_intelligence.csv")
ITI_FILE   = str(BASE_DIR / "data" / "processed" / "iti"      / "maharashtra_iti_trade_supply_2026.csv")
TRADE_FILE = str(BASE_DIR / "data" / "processed" / "training" / "official_trade_skills_reference.csv")


def clean(value):
    if pd.isna(value):
        return None
    return value


def main():
    print(f"Reading CSV datasets from {BASE_DIR / 'data'}...")
    mssds = pd.read_csv(MSSDS_FILE)
    iti = pd.read_csv(ITI_FILE)
    trade = pd.read_csv(TRADE_FILE)

    print(f"Connecting to database...")
    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # -------------------------------------------------
            # 1. DISTRICTS
            # -------------------------------------------------
            districts = set(mssds["district"].dropna())
            districts.update(iti["district"].dropna())
            district_tuples = [(d,) for d in sorted(districts)]

            cur.executemany(
                """
                INSERT INTO districts (name)
                VALUES (%s)
                ON CONFLICT (name) DO NOTHING
                """,
                district_tuples
            )
            conn.commit()

            cur.execute("SELECT name, id FROM districts")
            district_map = dict(cur.fetchall())
            print(f"[1/6] Ingested {len(district_map)} districts.")

            # -------------------------------------------------
            # 2. SECTORS
            # -------------------------------------------------
            sectors = sorted(mssds["sector"].dropna().unique())
            sector_tuples = [(s,) for s in sectors]

            cur.executemany(
                """
                INSERT INTO sectors (name)
                VALUES (%s)
                ON CONFLICT (name) DO NOTHING
                """,
                sector_tuples
            )
            conn.commit()

            cur.execute("SELECT name, id FROM sectors")
            sector_map = dict(cur.fetchall())
            print(f"[2/6] Ingested {len(sector_map)} sectors.")

            # -------------------------------------------------
            # 3. ITI INSTITUTES
            # -------------------------------------------------
            unique_itis = iti[
                [
                    "district",
                    "taluka",
                    "iti_type",
                    "iti_name",
                    "source",
                    "source_file",
                ]
            ].drop_duplicates()

            iti_insert_tuples = []
            for row in unique_itis.itertuples(index=False):
                d_id = district_map.get(row.district)
                iti_insert_tuples.append((
                    d_id,
                    clean(row.taluka),
                    clean(row.iti_type),
                    row.iti_name,
                    clean(row.source),
                    clean(row.source_file),
                ))

            cur.executemany(
                """
                INSERT INTO iti_institutes
                (district_id, taluka, iti_type, iti_name, source, source_file)
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                iti_insert_tuples
            )
            conn.commit()

            cur.execute(
                """
                SELECT district_id, taluka, iti_type, iti_name, source_file, id
                FROM iti_institutes
                """
            )
            iti_cache = {}
            for row in cur.fetchall():
                key = (row[0], row[1], row[2], row[3], row[4])
                iti_cache[key] = row[5]
            print(f"[3/6] Ingested {len(unique_itis)} ITI institutes.")

            # -------------------------------------------------
            # 4. ITI OFFERINGS
            # -------------------------------------------------
            offerings_tuples = []
            for row in iti.itertuples(index=False):
                d_id = district_map.get(row.district)
                key = (
                    d_id,
                    clean(row.taluka),
                    clean(row.iti_type),
                    row.iti_name,
                    clean(row.source_file),
                )
                iti_id = iti_cache.get(key)
                if not iti_id:
                    continue

                intake = clean(row.intake)
                if intake is not None:
                    intake = int(intake)

                pdf_page = clean(row.pdf_page)
                if pdf_page is not None:
                    pdf_page = int(pdf_page)

                offerings_tuples.append((
                    iti_id,
                    row.trade_name,
                    clean(row.admission_year),
                    intake,
                    pdf_page,
                    clean(row.source),
                ))

            cur.executemany(
                """
                INSERT INTO iti_offerings
                (
                    iti_id,
                    trade_name,
                    admission_year,
                    intake,
                    pdf_page,
                    source
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                offerings_tuples
            )
            conn.commit()
            print(f"[4/6] Ingested {len(offerings_tuples)} ITI offerings.")

            # -------------------------------------------------
            # 5. MSSDS DISTRICT-SECTOR INTELLIGENCE
            # -------------------------------------------------
            dsi_tuples = []
            for row in mssds.itertuples(index=False):
                district_id = district_map.get(row.district)
                sector_id = sector_map.get(row.sector)
                if not district_id or not sector_id:
                    continue

                dsi_tuples.append((
                    district_id,
                    sector_id,
                    clean(row.industry_opportunity_score),
                    clean(row.training_pressure_score),
                    clean(row.evidence_confidence),
                    clean(row.projection_available),
                    clean(row.industry_size),
                    clean(row.organization_count),
                    clean(row.candidate_aspiration),
                    clean(row.mssds_trained_2022_23),
                    clean(row.dsdp_training),
                    clean(row.projected_training),
                    clean(row.source),
                ))

            cur.executemany(
                """
                INSERT INTO district_sector_intelligence
                (
                    district_id,
                    sector_id,
                    industry_opportunity_score,
                    training_pressure_score,
                    evidence_confidence,
                    projection_available,
                    industry_size,
                    organization_count,
                    candidate_aspiration,
                    mssds_trained_2022_23,
                    dsdp_training,
                    projected_training,
                    source
                )
                VALUES
                (
                    %s, %s, %s, %s, %s, %s,
                    %s, %s, %s, %s, %s, %s, %s
                )
                ON CONFLICT (district_id, sector_id)
                DO UPDATE SET
                    industry_opportunity_score = EXCLUDED.industry_opportunity_score,
                    training_pressure_score = EXCLUDED.training_pressure_score,
                    evidence_confidence = EXCLUDED.evidence_confidence,
                    projection_available = EXCLUDED.projection_available,
                    industry_size = EXCLUDED.industry_size,
                    organization_count = EXCLUDED.organization_count,
                    candidate_aspiration = EXCLUDED.candidate_aspiration,
                    mssds_trained_2022_23 = EXCLUDED.mssds_trained_2022_23,
                    dsdp_training = EXCLUDED.dsdp_training,
                    projected_training = EXCLUDED.projected_training,
                    source = EXCLUDED.source
                """,
                dsi_tuples
            )
            conn.commit()
            print(f"[5/6] Ingested {len(dsi_tuples)} district-sector intelligence records.")

            # -------------------------------------------------
            # 6. TRADE SKILL REFERENCE
            # -------------------------------------------------
            trade_tuples = []
            for row in trade.itertuples(index=False):
                trade_tuples.append((
                    row.trade,
                    clean(row.competency_summary),
                    clean(row.official_source),
                    clean(row.source_url),
                    clean(row.source_type),
                    clean(row.evidence),
                ))

            cur.executemany(
                """
                INSERT INTO trade_skill_reference
                (
                    trade,
                    competency_summary,
                    official_source,
                    source_url,
                    source_type,
                    evidence
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                ON CONFLICT (trade)
                DO UPDATE SET
                    competency_summary = EXCLUDED.competency_summary,
                    official_source = EXCLUDED.official_source,
                    source_url = EXCLUDED.source_url,
                    source_type = EXCLUDED.source_type,
                    evidence = EXCLUDED.evidence
                """,
                trade_tuples
            )
            conn.commit()
            print(f"[6/6] Ingested {len(trade_tuples)} trade skill references.")

    print("\n✅ Data ingestion completed successfully into Supabase PostgreSQL!")


if __name__ == "__main__":
    main()