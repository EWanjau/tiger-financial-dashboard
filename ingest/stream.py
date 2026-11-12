"""Stream Twelve Data WebSocket ticks into the crypto_ticks hypertable."""

from __future__ import annotations

import signal
import threading
import time
from datetime import datetime, timezone

import psycopg2
from psycopg2.extras import execute_values
from twelvedata import TDClient

from ingest.config import load_settings
from ingest.db import apply_schema, connect


class TickPipeline:
    columns = ("time", "symbol", "price", "day_volume", "bid", "ask")

    def __init__(self, conn, api_key: str, batch_size: int):
        self.conn = conn
        self.api_key = api_key
        self.batch_size = batch_size
        self.current_batch: list[tuple] = []
        self.lock = threading.Lock()
        self.insert_counter = 0
        self.stop = threading.Event()

    def _insert(self, rows: list[tuple]) -> None:
        sql = f"""
            INSERT INTO crypto_ticks ({",".join(self.columns)})
            VALUES %s
        """
        with self.conn.cursor() as cur:
            execute_values(cur, sql, rows)
        self.conn.commit()
        self.insert_counter += 1
        print(f"inserted {len(rows)} ticks (batch #{self.insert_counter})")

    def flush(self) -> None:
        with self.lock:
            if not self.current_batch:
                return
            rows = self.current_batch
            self.current_batch = []
        try:
            self._insert(rows)
        except psycopg2.Error as exc:
            print(f"insert failed: {exc}")
            self.conn.rollback()

    def on_event(self, event: dict) -> None:
        if event.get("event") != "price":
            if event.get("event") in {"subscribe-status", "heartbeat"}:
                print(event)
            return
        ts = datetime.fromtimestamp(int(event["timestamp"]), tz=timezone.utc)
        row = (
            ts,
            event["symbol"],
            float(event["price"]),
            event.get("day_volume"),
            event.get("bid"),
            event.get("ask"),
        )
        should_flush = False
        with self.lock:
            self.current_batch.append(row)
            print(f"queued {event['symbol']} @ {event['price']} (batch {len(self.current_batch)})")
            should_flush = len(self.current_batch) >= self.batch_size
        if should_flush:
            self.flush()

    def start(self, symbols: tuple[str, ...]) -> None:
        td = TDClient(apikey=self.api_key)
        ws = td.websocket(on_event=self.on_event)
        ws.subscribe(list(symbols))
        ws.connect()
        print(f"streaming {', '.join(symbols)}")
        try:
            while not self.stop.is_set():
                ws.heartbeat()
                self.flush()
                self.stop.wait(10)
        finally:
            self.flush()
            ws.disconnect()


def main() -> None:
    settings = load_settings()
    apply_schema(settings)
    conn = connect(settings)
    pipeline = TickPipeline(conn, settings.api_key, settings.batch_size)

    def handle_stop(_signum, _frame):
        pipeline.stop.set()

    signal.signal(signal.SIGINT, handle_stop)
    signal.signal(signal.SIGTERM, handle_stop)
    pipeline.start(settings.symbols)
    time.sleep(0.2)
    conn.close()


if __name__ == "__main__":
    main()
