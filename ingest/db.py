from __future__ import annotations

from pathlib import Path

import psycopg2

from ingest.config import Settings
from ingest.tiger import connection_uri

ROOT = Path(__file__).resolve().parent.parent


def connect(_settings: Settings | None = None):
    return psycopg2.connect(connection_uri())


def apply_schema(settings: Settings) -> None:
    sql_path = ROOT / "sql" / "001_schema.sql"
    conn = connect(settings)
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(sql_path.read_text())
            for view in ("one_min_candle", "one_hour_candle", "one_day_candle"):
                cur.execute(f"CALL refresh_continuous_aggregate('{view}', NULL, NULL)")
    finally:
        conn.close()
