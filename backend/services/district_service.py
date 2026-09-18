import os
import csv
from pathlib import Path

DATA_CSV = Path(__file__).resolve().parent.parent.parent / "data" / "outputs" / "mssds_district_sector_intelligence.csv"


def get_all_districts():
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
            SELECT id, name
            FROM districts
            ORDER BY name
        """

        with psycopg.connect(**db_config) as conn:
            with conn.cursor() as cursor:
                cursor.execute(query)
                rows = cursor.fetchall()

        if rows:
            districts = []
            for district_id, name in rows:
                districts.append(
                    {
                        "id": district_id,
                        "name": name,
                    }
                )
            return {
                "districts": districts
            }
    except Exception:
        # Fallback to local verified dataset
        pass

    districts = []
    if DATA_CSV.exists():
        names = set()
        with open(DATA_CSV, newline="", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                d = row.get("district", "").strip()
                if d:
                    names.add(d)
        districts = [{"id": i + 1, "name": name} for i, name in enumerate(sorted(names))]

    return {
        "districts": districts
    }