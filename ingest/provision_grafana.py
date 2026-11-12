"""Write Grafana datasource YAML using the Tiger CLI connection URI."""

from __future__ import annotations

from pathlib import Path

from ingest.config import parse_database_url
from ingest.tiger import connection_uri

TEMPLATE = """apiVersion: 1

datasources:
  - name: Tiger Cloud
    uid: tiger-cloud
    type: postgres
    access: proxy
    isDefault: true
    url: {host}:{port}
    user: {user}
    editable: true
    jsonData:
      database: {dbname}
      sslmode: require
      postgresVersion: 1600
      timescaledb: true
    secureJsonData:
      password: "{password}"
"""

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "grafana" / "provisioning" / "datasources" / "tiger.yaml"


def main() -> None:
    parts = parse_database_url(connection_uri())
    password = parts["password"].replace("\\", "\\\\").replace('"', '\\"')
    OUT.write_text(
        TEMPLATE.format(
            host=parts["host"],
            port=parts["port"],
            user=parts["user"],
            dbname=parts["dbname"],
            password=password,
        )
    )
    print(f"wrote {OUT.name}")


if __name__ == "__main__":
    main()
