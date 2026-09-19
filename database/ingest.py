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
# Set DATABASE_URL in your environment (or .env) before running.
# Local PostgreSQL example:
#   DATABASE_URL=postgresql://postgres:password@localhost:5432/maharashtra_skill_intelligence
# Supabase Session Pooler example (from Project Settings → Connect):
#   DATABASE_URL=postgresql://postgres.xxxx:PASSWORD@aws-0-ap-south-1.pooler.supabase.com:5432/postgres
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
    mssds = pd.read_csv(MSSDS_FILE)
    iti = pd.read_csv(ITI_FILE)
    trade = pd.read_csv(TRADE_FILE)

    with psycopg.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:

            # -------------------------------------------------
            # 1. DISTRICTS
            # -------------------------------------------------
            districts = set(mssds["district"].dropna())
            districts.update(iti["district"].dropna())

            for district in sorted(districts):
                cur.execute(
                    """
                    INSERT INTO districts (name)
                    VALUES (%s)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    (district,),
                )

            # -------------------------------------------------
            # 2. SECTORS
            # -------------------------------------------------
            for sector in sorted(mssds["sector"].dropna().unique()):
                cur.execute(
                    """
                    INSERT INTO sectors (name)
                    VALUES (%s)
                    ON CONFLICT (name) DO NOTHING
                    """,
                    (sector,),
                )

            # -------------------------------------------------
            # 3. ITI INSTITUTES
            # -------------------------------------------------
            iti_cache = {}

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

            for row in unique_itis.itertuples(index=False):
                district_id = cur.execute(
                    "SELECT id FROM districts WHERE name = %s",
                    (row.district,),
                )

                district_id = cur.fetchone()[0]

                cur.execute(
                    """
                    INSERT INTO iti_institutes
                    (district_id, taluka, iti_type, iti_name, source, source_file)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        district_id,
                        clean(row.taluka),
                        clean(row.iti_type),
                        row.iti_name,
                        clean(row.source),
                        clean(row.source_file),
                    ),
                )

                iti_id = cur.fetchone()[0]

                key = (
                    row.district,
                    clean(row.taluka),
                    clean(row.iti_type),
                    row.iti_name,
                    clean(row.source_file),
                )

                iti_cache[key] = iti_id

            # -------------------------------------------------
            # 4. ITI OFFERINGS
            # -------------------------------------------------
            for row in iti.itertuples(index=False):

                key = (
                    row.district,
                    clean(row.taluka),
                    clean(row.iti_type),
                    row.iti_name,
                    clean(row.source_file),
                )

                iti_id = iti_cache[key]

                intake = clean(row.intake)
                if intake is not None:
                    intake = int(intake)

                pdf_page = clean(row.pdf_page)
                if pdf_page is not None:
                    pdf_page = int(pdf_page)

                cur.execute(
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
                    (
                        iti_id,
                        row.trade_name,
                        clean(row.admission_year),
                        intake,
                        pdf_page,
                        clean(row.source),
                    ),
                )

            # -------------------------------------------------
            # 5. MSSDS DISTRICT-SECTOR INTELLIGENCE
            # -------------------------------------------------
            for row in mssds.itertuples(index=False):

                cur.execute(
                    "SELECT id FROM districts WHERE name = %s",
                    (row.district,),
                )
                district_id = cur.fetchone()[0]

                cur.execute(
                    "SELECT id FROM sectors WHERE name = %s",
                    (row.sector,),
                )
                sector_id = cur.fetchone()[0]

                cur.execute(
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
                    (
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
                    ),
                )

            # -------------------------------------------------
            # 6. TRADE SKILL REFERENCE
            # -------------------------------------------------
            for row in trade.itertuples(index=False):

                cur.execute(
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
                    (
                        row.trade,
                        clean(row.competency_summary),
                        clean(row.official_source),
                        clean(row.source_url),
                        clean(row.source_type),
                        clean(row.evidence),
                    ),
                )

        conn.commit()

    print("Data ingestion completed successfully.")


if __name__ == "__main__":
    main()