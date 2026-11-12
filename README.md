# Financial realtime dashboard

This Grafana dashboard provides a real-time overview of the Bitcoin (BTC/USD) market, displaying the latest Bitcoin price, daily trading volume, and historical price movements. It uses tick data to generate one-minute OHLC candlestick charts, allowing users to monitor price fluctuations, identify market trends, and analyze trading activity over a selected time period. The dashboard also displays the latest market quotes for different financial instruments, providing a centralized view of market performance.

```text
Twelve Data WebSocket ──► ingest/stream.py ──► crypto_ticks (hypertable)
Twelve Data REST ──────► ingest/backfill.py ─► ohlcv_bars (hypertable)
                                              │
                                              ▼
                                    continuous aggregates
                                    one_min / one_hour / one_day
                                              │
                                              ▼
                                    Grafana (PostgreSQL + TimescaleDB)
```

## Prerequisites

- Python 3.11+
- Docker (for Grafana)
- `.env` with `TWELVE_DATA_API_KEY` (or `TWELVEDATA_API_KEY`) and `TigerDataConnectionString` (or `DATABASE_URL`)

Copy `.env.example` if needed. Keep the API key and connection string out of git.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Load schema, history, and live ticks

```bash
python -m ingest schema
python -m ingest backfill
python -m ingest stream
```

`stream` keeps a WebSocket to `wss://ws.twelvedata.com/v1/quotes/price`, batches price events, and inserts into `crypto_ticks`. Heartbeats go out every 10 seconds. Basic/Grow plans are limited to trial symbols (typically including `BTC/USD`, `ETH/USD`, `AAPL`).

Default symbols: `BTC/USD,ETH/USD,SOL/USD,AAPL,MSFT` (override with `SYMBOLS` in `.env`).

## Grafana

```bash
python -m ingest grafana
docker compose up -d grafana
```

Open http://localhost:3000 (`admin` / `admin`). The **Financial realtime** dashboard is provisioned under the Financial folder.

Datasource settings used: PostgreSQL, TLS `require`, TimescaleDB enabled.

If `TigerDataConnectionString` has no password (postgres://user@host:port/db), set `TIGER_PASSWORD` in `.env` to the Tiger Cloud password. Grafana and `python -m ingest stream` need it; schema was applied through Tiger MCP independently.

## Queries Grafana uses

Minute candles from ticks:

```sql
SELECT bucket AS time, open, high, low, close
FROM one_min_candle
WHERE symbol = 'BTC/USD'
ORDER BY bucket;
```

Historical REST bars:

```sql
SELECT time, open, high, low, close, volume
FROM ohlcv_bars
WHERE symbol = 'BTC/USD' AND interval = '1min'
ORDER BY time;
```
