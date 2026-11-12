"""python -m ingest stream|backfill|schema|grafana"""

from __future__ import annotations

import sys


def main() -> None:
    cmd = sys.argv[1] if len(sys.argv) > 1 else "stream"
    if cmd in {"stream", "ticks", "poll"}:
        from ingest.poll import main as run

        run()
    elif cmd == "backfill":
        from ingest.backfill import main as run

        run()
    elif cmd == "schema":
        from ingest.config import load_settings
        from ingest.db import apply_schema

        apply_schema(load_settings())
        print("schema applied")
    elif cmd == "grafana":
        from ingest.provision_grafana import main as run

        run()
    else:
        raise SystemExit("usage: python -m ingest [stream|backfill|schema|grafana]")


if __name__ == "__main__":
    main()
