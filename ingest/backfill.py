"""Load historical OHLCV bars from Twelve Data REST /time_series."""

from __future__ import annotations

from datetime import datetime, timezone

import requests
from psycopg2.extras import execute_values

from ingest.config import load_settings
from ingest.db import apply_schema, connect

TIME_SERIES_URL = "https://api.twelvedata.com/time_series"


def fetch_bars(api_key: str, symbol: str, interval: str, outputsize: int) -> list[tuple]:
    response = requests.get(
        TIME_SERIES_URL,
        params={
            "symbol": symbol,
            "interval": interval,
            "outputsize": outputsize,
            "order": "ASC",
            "apikey": api_key,
        },
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    if payload.get("status") == "error":
        raise RuntimeError(f"{symbol}: {payload.get('message')}")

    rows: list[tuple] = []
    for bar in payload.get("values") or []:
        raw = bar["datetime"]
        if " " in raw:
            ts = datetime.strptime(raw, "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
        else:
            ts = datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        volume = bar.get("volume")
        rows.append(
            (
                ts,
                symbol,
                interval,
                float(bar["open"]),
                float(bar["high"]),
                float(bar["low"]),
                float(bar["close"]),
                float(volume) if volume not in (None, "") else None,
            )
        )
    return rows


def upsert_bars(conn, rows: list[tuple]) -> int:
    if not rows:
        return 0
    sql = """
        INSERT INTO ohlcv_bars (time, symbol, interval, open, high, low, close, volume)
        VALUES %s
        ON CONFLICT (time, symbol, interval) DO UPDATE SET
            open = EXCLUDED.open,
            high = EXCLUDED.high,
            low = EXCLUDED.low,
            close = EXCLUDED.close,
            volume = EXCLUDED.volume
    """
    with conn.cursor() as cur:
        execute_values(cur, sql, rows, page_size=500)
    conn.commit()
    return len(rows)


def main() -> None:
    settings = load_settings()
    apply_schema(settings)
    with connect(settings) as conn:
        for symbol in settings.symbols:
            rows = fetch_bars(
                settings.api_key,
                symbol,
                settings.backfill_interval,
                settings.backfill_outputsize,
            )
            count = upsert_bars(conn, rows)
            print(f"backfilled {count} {settings.backfill_interval} bars for {symbol}")


if __name__ == "__main__":
    main()
