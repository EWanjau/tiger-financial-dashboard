"""Poll Twelve Data REST quotes into the crypto_ticks hypertable."""

from __future__ import annotations

import signal
import time
from datetime import datetime, timezone

import requests
from psycopg2.extras import execute_values

from ingest.config import load_settings
from ingest.db import apply_schema, connect

QUOTE_URL = "https://api.twelvedata.com/quote"


def parse_quote_time(raw: str) -> datetime:
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return datetime.now(timezone.utc)


def fetch_quotes(api_key: str, symbols: tuple[str, ...]) -> list[tuple]:
    rows: list[tuple] = []
    for symbol in symbols:
        response = requests.get(
            QUOTE_URL,
            params={"symbol": symbol, "apikey": api_key},
            timeout=20,
        )
        response.raise_for_status()
        payload = response.json()
        if payload.get("status") == "error" or "close" not in payload:
            print(f"quote skip {symbol}: {payload.get('message', payload)}")
            continue
        ts = parse_quote_time(str(payload.get("datetime") or ""))
        volume = payload.get("volume")
        rows.append(
            (
                ts,
                symbol,
                float(payload["close"]),
                float(volume) if volume not in (None, "") else None,
                None,
                None,
            )
        )
    return rows


def seed_ticks_from_bars(conn) -> int:
    sql = """
        INSERT INTO crypto_ticks (time, symbol, price, day_volume)
        SELECT time, symbol, close, volume
        FROM ohlcv_bars
        WHERE NOT EXISTS (
            SELECT 1 FROM crypto_ticks t
            WHERE t.time = ohlcv_bars.time AND t.symbol = ohlcv_bars.symbol
        )
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        count = cur.rowcount
    conn.commit()
    return count


def refresh_caggs(conn) -> None:
    previous = conn.autocommit
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            for view in ("one_min_candle", "one_hour_candle", "one_day_candle"):
                cur.execute(f"CALL refresh_continuous_aggregate('{view}', NULL, NULL)")
    finally:
        conn.autocommit = previous


def insert_ticks(conn, rows: list[tuple]) -> None:
    if not rows:
        return
    sql = """
        INSERT INTO crypto_ticks (time, symbol, price, day_volume, bid, ask)
        VALUES %s
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows)
    conn.commit()


def main(loop: bool = True) -> None:
    settings = load_settings()
    apply_schema(settings)
    conn = connect(settings)
    seeded = seed_ticks_from_bars(conn)
    print(f"seeded {seeded} ticks from ohlcv_bars")
    refresh_caggs(conn)

    stop = False

    def handle_stop(_signum, _frame):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)

    while not stop:
        try:
            rows = fetch_quotes(settings.api_key, settings.symbols)
            insert_ticks(conn, rows)
            print(f"inserted {len(rows)} quotes at {datetime.now(timezone.utc).isoformat()}")
            refresh_caggs(conn)
        except Exception as exc:
            print(f"poll error: {exc}")
        if not loop:
            break
        for _ in range(15):
            if stop:
                break
            time.sleep(1)
    conn.close()


if __name__ == "__main__":
    main()
