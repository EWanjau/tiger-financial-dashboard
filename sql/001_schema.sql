-- Financial time-series schema for Twelve Data ticks + OHLCV bars.
-- Hypertables use Tiger Cloud CREATE TABLE ... WITH (tsdb.hypertable, ...).

CREATE TABLE IF NOT EXISTS crypto_assets (
    symbol TEXT PRIMARY KEY,
    name TEXT,
    asset_type TEXT,
    exchange TEXT
);

INSERT INTO crypto_assets (symbol, name, asset_type, exchange) VALUES
    ('BTC/USD', 'Bitcoin', 'crypto', NULL),
    ('ETH/USD', 'Ethereum', 'crypto', NULL),
    ('SOL/USD', 'Solana', 'crypto', NULL),
    ('AAPL', 'Apple Inc.', 'stock', 'NASDAQ'),
    ('MSFT', 'Microsoft Corp.', 'stock', 'NASDAQ')
ON CONFLICT (symbol) DO NOTHING;

CREATE TABLE IF NOT EXISTS crypto_ticks (
    "time" TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    price DOUBLE PRECISION NOT NULL,
    day_volume NUMERIC,
    bid DOUBLE PRECISION,
    ask DOUBLE PRECISION
) WITH (
    tsdb.hypertable,
    tsdb.segmentby = 'symbol',
    tsdb.orderby = 'time DESC'
);

CREATE INDEX IF NOT EXISTS crypto_ticks_symbol_time_idx
    ON crypto_ticks (symbol, "time" DESC);

CREATE TABLE IF NOT EXISTS ohlcv_bars (
    "time" TIMESTAMPTZ NOT NULL,
    symbol TEXT NOT NULL,
    "interval" TEXT NOT NULL,
    open DOUBLE PRECISION,
    high DOUBLE PRECISION,
    low DOUBLE PRECISION,
    close DOUBLE PRECISION,
    volume DOUBLE PRECISION
) WITH (
    tsdb.hypertable,
    tsdb.segmentby = 'symbol',
    tsdb.orderby = 'time DESC'
);

CREATE UNIQUE INDEX IF NOT EXISTS ohlcv_bars_time_symbol_interval_idx
    ON ohlcv_bars ("time", symbol, "interval");

CREATE OR REPLACE VIEW latest_quotes AS
SELECT DISTINCT ON (symbol)
    "time",
    symbol,
    price,
    day_volume,
    bid,
    ask
FROM crypto_ticks
ORDER BY symbol, "time" DESC;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.continuous_aggregates
        WHERE view_name = 'one_min_candle'
    ) THEN
        EXECUTE $sql$
            CREATE MATERIALIZED VIEW one_min_candle
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 minute', "time") AS bucket,
                symbol,
                FIRST(price, "time") AS open,
                MAX(price) AS high,
                MIN(price) AS low,
                LAST(price, "time") AS close,
                LAST(day_volume, "time") AS day_volume
            FROM crypto_ticks
            GROUP BY bucket, symbol
            WITH NO DATA
        $sql$;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.continuous_aggregates
        WHERE view_name = 'one_hour_candle'
    ) THEN
        EXECUTE $sql$
            CREATE MATERIALIZED VIEW one_hour_candle
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 hour', "time") AS bucket,
                symbol,
                FIRST(price, "time") AS open,
                MAX(price) AS high,
                MIN(price) AS low,
                LAST(price, "time") AS close,
                LAST(day_volume, "time") AS day_volume
            FROM crypto_ticks
            GROUP BY bucket, symbol
            WITH NO DATA
        $sql$;
    END IF;
END $$;

DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM timescaledb_information.continuous_aggregates
        WHERE view_name = 'one_day_candle'
    ) THEN
        EXECUTE $sql$
            CREATE MATERIALIZED VIEW one_day_candle
            WITH (timescaledb.continuous) AS
            SELECT
                time_bucket('1 day', "time") AS bucket,
                symbol,
                FIRST(price, "time") AS open,
                MAX(price) AS high,
                MIN(price) AS low,
                LAST(price, "time") AS close,
                LAST(day_volume, "time") AS day_volume
            FROM crypto_ticks
            GROUP BY bucket, symbol
            WITH NO DATA
        $sql$;
    END IF;
END $$;

DO $$
BEGIN
    PERFORM add_continuous_aggregate_policy(
        'one_min_candle',
        start_offset => INTERVAL '6 hours',
        end_offset => INTERVAL '1 minute',
        schedule_interval => INTERVAL '1 minute'
    );
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'one_min_candle policy: %', SQLERRM;
END $$;

DO $$
BEGIN
    PERFORM add_continuous_aggregate_policy(
        'one_hour_candle',
        start_offset => INTERVAL '7 days',
        end_offset => INTERVAL '1 hour',
        schedule_interval => INTERVAL '15 minutes'
    );
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'one_hour_candle policy: %', SQLERRM;
END $$;

DO $$
BEGIN
    PERFORM add_continuous_aggregate_policy(
        'one_day_candle',
        start_offset => INTERVAL '30 days',
        end_offset => INTERVAL '1 hour',
        schedule_interval => INTERVAL '1 hour'
    );
EXCEPTION WHEN OTHERS THEN
    RAISE NOTICE 'one_day_candle policy: %', SQLERRM;
END $$;
