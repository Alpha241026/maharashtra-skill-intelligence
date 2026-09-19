import csv
from pathlib import Path
from collections import defaultdict
from fastapi import HTTPException

ITI_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "processed" / "iti" / "maharashtra_iti_trade_supply_2026.csv"


def get_iti_supply_by_district(district: str):
    norm_input  = district.strip().lower()
    if norm_input == "nasik":
        target_name = "Nashik"
    elif norm_input == "mumbai":
        target_name = "Mumbai City"
    else:
        target_name = district.strip()

    # ── Primary: PostgreSQL via DATABASE_URL ──────────────────────────────
    try:
        from backend.db.connection import get_conn

        district_q = """
            SELECT name FROM districts
            WHERE LOWER(name) = LOWER(%s)
               OR (LOWER(%s) IN ('nasik', 'nashik') AND LOWER(name) IN ('nasik', 'nashik'))
        """
        total_q = """
            SELECT COALESCE(SUM(o.intake), 0)
            FROM iti_offerings o
            JOIN iti_institutes i ON o.iti_id    = i.id
            JOIN districts      d ON i.district_id = d.id
            WHERE LOWER(d.name) = LOWER(%s)
               OR (LOWER(%s) IN ('nasik', 'nashik') AND LOWER(d.name) IN ('nasik', 'nashik'))
        """
        trade_q = """
            SELECT o.trade_name, COALESCE(SUM(o.intake), 0) AS total_intake
            FROM iti_offerings o
            JOIN iti_institutes i ON o.iti_id    = i.id
            JOIN districts      d ON i.district_id = d.id
            WHERE LOWER(d.name) = LOWER(%s)
               OR (LOWER(%s) IN ('nasik', 'nashik') AND LOWER(d.name) IN ('nasik', 'nashik'))
            GROUP BY o.trade_name
            ORDER BY total_intake DESC
        """

        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(district_q, (target_name, target_name))
                district_row = cur.fetchone()

                if district_row is not None:
                    cur.execute(total_q, (target_name, target_name))
                    total_intake = int(cur.fetchone()[0])

                    cur.execute(trade_q, (target_name, target_name))
                    trades = [
                        {"trade": trade_name, "intake": int(intake)}
                        for trade_name, intake in cur.fetchall()
                    ]

                    return {
                        "district":     district_row[0],
                        "total_intake": total_intake,
                        "trades":       trades,
                    }
    except Exception:
        pass

    # ── Fallback: local CSV dataset ───────────────────────────────────────
    if not ITI_CSV.exists():
        raise HTTPException(
            status_code=404,
            detail=f"District {district} not found in database or dataset",
        )

    trade_intake     = defaultdict(int)
    total_intake     = 0
    display_district = target_name.title()
    matched          = False

    with open(ITI_CSV, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            d = row.get("district", "").strip().lower()
            if (norm_input in ("nasik", "nashik") and d in ("nasik", "nashik")) or d == norm_input:
                matched          = True
                display_district = row.get("district", display_district).strip()
                trade            = row.get("trade_name", "").strip()
                try:
                    intake = int(float(row.get("intake", "").strip()))
                except (ValueError, TypeError):
                    intake = 0
                trade_intake[trade] += intake
                total_intake        += intake

    if not matched:
        raise HTTPException(
            status_code=404,
            detail=f"District {district} not found in ITI directory",
        )

    sorted_trades = sorted(
        [{"trade": t, "intake": cnt} for t, cnt in trade_intake.items()],
        key=lambda x: x["intake"],
        reverse=True,
    )

    return {
        "district":     display_district,
        "total_intake": total_intake,
        "trades":       sorted_trades,
    }
