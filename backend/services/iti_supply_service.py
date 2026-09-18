# import os to read the PostgreSQL password from the environment
import os

# import psycopg to connect to PostgreSQL
import psycopg

# import HTTPException to return API errors
from fastapi import HTTPException


# return ITI trade supply data for the requested district
def get_iti_supply_by_district(district: str):
    # PostgreSQL connection configuration
    db_config = {
        "dbname": "maharashtra_skill_intelligence",
        "user": "postgres",
        "password": os.getenv("PGPASSWORD"),
        "host": "localhost",
        "port": 5432,
    }

    # query to verify that the requested district exists
    district_query = """
        SELECT name
        FROM districts
        WHERE LOWER(name) = LOWER(%s)
    """

    # query to calculate total ITI intake for the district
    total_query = """
        SELECT COALESCE(SUM(o.intake), 0)
        FROM iti_offerings o
        JOIN iti_institutes i
            ON o.iti_id = i.id
        JOIN districts d
            ON i.district_id = d.id
        WHERE LOWER(d.name) = LOWER(%s)
    """

    # query to calculate intake grouped by trade
    trade_query = """
        SELECT
            o.trade_name,
            COALESCE(SUM(o.intake), 0) AS total_intake
        FROM iti_offerings o
        JOIN iti_institutes i
            ON o.iti_id = i.id
        JOIN districts d
            ON i.district_id = d.id
        WHERE LOWER(d.name) = LOWER(%s)
        GROUP BY o.trade_name
        ORDER BY total_intake DESC
    """

    # open a PostgreSQL connection
    with psycopg.connect(**db_config) as conn:
        # create a cursor for executing SQL queries
        with conn.cursor() as cursor:

            # check whether the requested district exists
            cursor.execute(district_query, (district.strip(),))
            district_row = cursor.fetchone()

            # return 404 when the district does not exist
            if district_row is None:
                raise HTTPException(
                    status_code=404,
                    detail="District not found",
                )

            # get total intake for the district
            cursor.execute(total_query, (district.strip(),))
            total_intake = cursor.fetchone()[0]

            # get trade-wise intake for the district
            cursor.execute(trade_query, (district.strip(),))
            trade_rows = cursor.fetchall()

    # convert database rows into the API response structure
    trades = []

    for trade_name, intake in trade_rows:
        trades.append(
            {
                "trade": trade_name,
                "intake": int(intake),
            }
        )

    # return the complete response
    return {
        "district": district_row[0],
        "total_intake": int(total_intake),
        "trades": trades,
    }