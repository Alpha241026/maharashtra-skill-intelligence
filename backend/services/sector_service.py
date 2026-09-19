import csv
from pathlib import Path

DATA_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "outputs" / "mssds_district_sector_intelligence.csv"


def get_all_sectors():
    # ── Primary: PostgreSQL via DATABASE_URL ──────────────────────────────
    try:
        from backend.db.connection import get_conn

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT id, name FROM sectors ORDER BY name")
                rows = cur.fetchall()

        if rows:
            return {
                "sectors": [{"id": sector_id, "name": name} for sector_id, name in rows]
            }
    except Exception:
        pass

    # ── Fallback: derive sector list from local CSV ───────────────────────
    sectors = []
    if DATA_CSV.exists():
        names = set()
        with open(DATA_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                s = row.get("sector", "").strip()
                if s:
                    names.add(s)
        sectors = [{"id": i + 1, "name": name} for i, name in enumerate(sorted(names))]

    return {"sectors": sectors}
