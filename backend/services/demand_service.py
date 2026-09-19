import csv
from pathlib import Path
from fastapi import HTTPException

DATA_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "outputs" / "mssds_district_sector_intelligence.csv"


def _demand_band(pt: float) -> str:
    if pt >= 300:
        return "High"
    elif pt >= 100:
        return "Moderate"
    return "Low"


def get_demand_by_district(district: str):
    norm_input = district.strip().lower()
    # Normalise alternative spellings
    if norm_input == "nasik":
        target_name = "Nashik"
    else:
        target_name = district.strip()

    # ── Primary: PostgreSQL via DATABASE_URL ──────────────────────────────
    try:
        from backend.db.connection import get_conn

        query = """
            SELECT
                d.name  AS district,
                s.name  AS sector,
                dsi.projected_training,
                dsi.evidence_confidence
            FROM district_sector_intelligence dsi
            JOIN districts d ON dsi.district_id = d.id
            JOIN sectors   s ON dsi.sector_id   = s.id
            WHERE LOWER(d.name) = LOWER(%s)
               OR (LOWER(%s) IN ('nasik', 'nashik') AND LOWER(d.name) IN ('nasik', 'nashik'))
            ORDER BY dsi.projected_training DESC NULLS LAST
        """

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(query, (target_name, target_name))
                rows = cur.fetchall()

        if rows:
            sectors = []
            for row in rows:
                _, sector, pt_raw, conf_raw = row
                if pt_raw is None:
                    continue
                pt   = float(pt_raw)
                conf = float(conf_raw) if conf_raw is not None else 0.0
                sectors.append({
                    "sector":             sector,
                    "projected_training": pt,
                    "demand_band":        _demand_band(pt),
                    "evidence_confidence": conf,
                })
            return {"district": rows[0][0], "sectors": sectors}

    except Exception:
        # Fall through to CSV fallback (no DB or DB unavailable)
        pass

    # ── Fallback: local CSV dataset ───────────────────────────────────────
    if not DATA_CSV.exists():
        raise HTTPException(
            status_code=404,
            detail=f"No projection baseline found for district: {district}",
        )

    matched_rows     = []
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

                try:
                    conf = float(row.get("evidence_confidence", "").strip())
                except ValueError:
                    conf = 0.0

                matched_rows.append({
                    "sector":             row.get("sector", "").strip(),
                    "projected_training": pt,
                    "evidence_confidence": conf,
                })

    if not matched_rows:
        raise HTTPException(
            status_code=404,
            detail=f"No projection baseline found for district: {district}",
        )

    for r in matched_rows:
        r["demand_band"] = _demand_band(r["projected_training"])

    matched_rows.sort(key=lambda x: x["projected_training"], reverse=True)
    return {"district": display_district, "sectors": matched_rows}
