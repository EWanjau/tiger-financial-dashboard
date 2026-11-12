"""Resolve a writable Postgres DSN via the Tiger CLI (keyring password)."""

from __future__ import annotations

import subprocess

SERVICE_ID = "pjohz0vjjl"


def connection_uri() -> str:
    result = subprocess.run(
        ["tiger", "db", "uri", SERVICE_ID, "--with-password"],
        check=True,
        capture_output=True,
        text=True,
    )
    uri = result.stdout.strip().splitlines()[-1].strip()
    if "://" not in uri:
        raise RuntimeError("tiger db uri did not return a connection string")
    return uri
