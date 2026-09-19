"""
backend/db/connection.py
Single, environment-aware database connection helper.

Reads DATABASE_URL from the environment - works transparently
with local PostgreSQL, Supabase Session Pooler, and any other
psycopg-compatible PostgreSQL endpoint.

Usage:
    from backend.db.connection import get_conn

    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT ...")
            rows = cur.fetchall()

Raises RuntimeError if DATABASE_URL is not set, so callers
can fall back to the CSV dataset gracefully.
"""

import os
import psycopg


def get_conn() -> psycopg.Connection:
    """Return a new psycopg connection using DATABASE_URL.

    Raises:
        RuntimeError: if DATABASE_URL is not set in the environment.
        psycopg.OperationalError: if the connection itself fails.
    """
    url = os.environ.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL environment variable is not set")
    return psycopg.connect(url)
