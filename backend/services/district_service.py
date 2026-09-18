import os

import psycopg


def get_all_districts():
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