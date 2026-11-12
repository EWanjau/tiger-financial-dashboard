from __future__ import annotations

import os
from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import unquote, urlparse

from dotenv import load_dotenv

load_dotenv()


def _first_env(*names: str) -> str:
    for name in names:
        value = os.getenv(name, "").strip()
        if value:
            return value
    return ""


def _require(*names: str) -> str:
    value = _first_env(*names)
    if not value:
        joined = ", ".join(names)
        raise RuntimeError(
            f"Missing {joined}. Put one of these in .env (see .env.example)."
        )
    return value


@dataclass(frozen=True)
class Settings:
    api_key: str
    database_url: str
    tiger_host: str
    tiger_port: str
    tiger_user: str
    tiger_password: str
    tiger_db: str
    symbols: tuple[str, ...]
    backfill_interval: str
    backfill_outputsize: int
    batch_size: int


def parse_database_url(url: str) -> dict[str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgres", "postgresql"}:
        raise RuntimeError("DATABASE_URL must be a postgres:// URI")
    return {
        "host": parsed.hostname or "",
        "port": str(parsed.port or 5432),
        "user": unquote(parsed.username or ""),
        "password": unquote(parsed.password or ""),
        "dbname": (parsed.path or "/tsdb").lstrip("/") or "tsdb",
    }


def load_settings() -> Settings:
    database_url = _require(
        "DATABASE_URL",
        "TigerDataConnectionString",
        "TIGER_CONNECTION_STRING",
        "TIMESCALE_URL",
    )
    if "sslmode=" not in database_url:
        sep = "&" if "?" in database_url else "?"
        database_url = f"{database_url}{sep}sslmode=require"
    parts = parse_database_url(database_url)
    symbols = tuple(
        s.strip()
        for s in os.getenv("SYMBOLS", "BTC/USD,ETH/USD,SOL/USD,AAPL,MSFT").split(",")
        if s.strip()
    )
    settings = Settings(
        api_key=_require(
            "TWELVEDATA_API_KEY",
            "TWELVE_DATA_API_KEY",
            "TD_API_KEY",
        ),
        database_url=database_url,
        tiger_host=os.getenv("TIGER_HOST", "").strip() or parts["host"],
        tiger_port=os.getenv("TIGER_PORT", "").strip() or parts["port"],
        tiger_user=os.getenv("TIGER_USER", "").strip() or parts["user"],
        tiger_password=os.getenv("TIGER_PASSWORD", "").strip() or parts["password"],
        tiger_db=os.getenv("TIGER_DB", "").strip() or parts["dbname"],
        symbols=symbols,
        backfill_interval=os.getenv("BACKFILL_INTERVAL", "1min"),
        backfill_outputsize=int(os.getenv("BACKFILL_OUTPUTSIZE", "500")),
        batch_size=int(os.getenv("BATCH_SIZE", "50")),
    )
    if not settings.tiger_password:
        creds = Path(__file__).resolve().parent.parent / "tiger-cloud-db-timeseries-credentials.txt"
        if creds.exists():
            for line in creds.read_text().splitlines():
                if "postgres://" in line and "@" in line:
                    url = line.split("Service URL:", 1)[-1].strip()
                    password = parse_database_url(url).get("password", "")
                    if password:
                        settings = replace(settings, tiger_password=password)
                    break
    return settings
