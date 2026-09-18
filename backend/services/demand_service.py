import os

import psycopg
from fastapi import HTTPException


def get_demand_by_district(district: str):
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
        ORDER BY s.name
    """

    with psycopg.connect(**db_config) as conn:
        with conn.cursor() as cursor:
            cursor.execute(query, (district.strip(),))
            rows = cursor.fetchall()

    if not rows:
        raise HTTPException(
            status_code=404,
            detail="District not found",
        )

    sectors = []

    for row in rows:
        _, sector, projected_training, evidence_confidence = row

        # skip sectors where a projected training value is not available
        if projected_training is None:
            continue

        if projected_training >= 300:
            demand_band = "High"
        elif projected_training >= 100:
            demand_band = "Moderate"
        else:
            demand_band = "Low"

        sectors.append(
            {
                "sector": sector,
                "projected_training": float(projected_training),
                "demand_band": demand_band,
                "evidence_confidence": float(evidence_confidence),
            }
        )

    return {
        "district": rows[0][0],
        "sectors": sectors,
    }