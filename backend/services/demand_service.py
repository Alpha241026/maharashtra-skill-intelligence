import os
import csv
from pathlib import Path
from fastapi import HTTPException

DATA_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "outputs" / "mssds_district_sector_intelligence.csv"


def get_demand_by_district(district: str):
    norm_input = district.strip().lower()
    # Normalize alternative spellings (e.g. Nasik -> Nashik)
    if norm_input == "nasik":
        target_name = "Nashik"
    else:
        target_name = district.strip()

    try:
        import psycopg
        db_config = {
            "dbname": "maharashtra_skill_intelligence",
            "user": "postgres",
            "password": os.getenv("PGPASSWORD"),
            "host": "localhost",
            "port": 5432,
        }

        query = """
            SELECT
                d.name AS district,
                s.name AS sector,
                dsi.projected_training,
                dsi.evidence_confidence
            FROM district_sector_intelligence dsi
            JOIN districts d
                ON dsi.district_id = d.id
            JOIN sectors s
                ON dsi.sector_id = s.id
            WHERE LOWER(d.name) = LOWER(%s)
               OR (LOWER(%s) IN ('nasik', 'nashik') AND LOWER(d.name) IN ('nasik', 'nashik'))
            ORDER BY s.name
        """

        with psycopg.connect(**db_config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query, (target_name, target_name))
                rows = cursor.fetchall()

        if rows:
            sectors = []
            for row in rows:
                _, sector, projected_training, evidence_confidence = row
                if projected_training is None:
                    continue

                pt = float(projected_training)
                if pt >= 300:
                    demand_band = "High"
                elif pt >= 100:
                    demand_band = "Moderate"
                else:
                    demand_band = "Low"

                sectors.append(
                    {
                        "sector": sector,
                        "projected_training": pt,
                        "demand_band": demand_band,
                        "evidence_confidence": float(evidence_confidence) if evidence_confidence is not None else 0.0,
                    }
                )

            sectors.sort(key=lambda s: s["projected_training"], reverse=True)
            return {
                "district": rows[0][0],
                "sectors": sectors,
            }
    except Exception:
        # Fall back to dataset file in data/outputs
        pass

    if not DATA_CSV.exists():
        raise HTTPException(
            status_code=404,
            detail=f"District {district} not found in database or dataset",
        )

    matched_rows = []
    display_district = target_name.title()

    with open(DATA_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d_norm = row.get("normalized_district", "").strip().lower()
            if (norm_input in ("nasik", "nashik") and d_norm in ("nasik", "nashik")) or d_norm == norm_input:
                display_district = row.get("district", display_district).strip()

                if row.get("projection_available", "").strip() != "True":
                    continue

                pt_raw = row.get("projected_training", "").strip()
                if not pt_raw:
                    continue

                try:
                    pt = float(pt_raw)
                except ValueError:
                    continue

                conf_raw = row.get("evidence_confidence", "").strip()
                try:
                    conf = float(conf_raw)
                except ValueError:
                    conf = 0.0

                matched_rows.append(
                    {
                        "sector": row.get("sector", "").strip(),
                        "projected_training": pt,
                        "evidence_confidence": conf,
                    }
                )

    if not matched_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No projection baseline found for district: {district}",
        )

    for r in matched_rows:
        pt = r["projected_training"]
        if pt >= 300:
            r["demand_band"] = "High"
        elif pt >= 100:
            r["demand_band"] = "Moderate"
        else:
            r["demand_band"] = "Low"

    matched_rows.sort(key=lambda x: x["projected_training"], reverse=True)

    return {
        "district": display_district,
        "sectors": matched_rows,
    }