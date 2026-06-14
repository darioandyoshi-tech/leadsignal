#!/usr/bin/env python3
"""Set required env vars on the Render LeadSignal service."""

import json
import secrets
import urllib.request
import urllib.error

ENV_FILE = "/home/dario/.openclaw/workspace/leadsignal/.env.render"
SRV = "srv-d8n8df6rnols73dea2sg"


def get_token() -> str:
    with open(ENV_FILE) as f:
        for line in f:
            if line.startswith("RENDER_API_TOKEN="):
                return line.strip().split("=", 1)[1]
    raise RuntimeError("No RENDER_API_TOKEN found")


TOKEN = get_token()

vars_to_set = {
    "PYTHON_VERSION": "3.12.0",
    "DATABASE_URL": "sqlite+aiosqlite:///./leadsignal.db",
    "SYNC_DATABASE_URL": "sqlite:///./leadsignal.db",
    "SECRET_KEY": secrets.token_hex(32),
}

for key, value in vars_to_set.items():
    payload = json.dumps({"key": key, "value": value}).encode()
    url = f"https://api.render.com/v1/services/{SRV}/env-vars/{key}"
    req = urllib.request.Request(
        url,
        data=payload,
        method="PUT",
        headers={
            "Authorization": f"Bearer {TOKEN}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            print(f"=== {key} ===")
            print(resp.read().decode()[:500])
    except urllib.error.HTTPError as e:
        print(f"=== {key} HTTP {e.code} ===")
        print(e.read().decode()[:500])
    except Exception as e:
        print(f"=== {key} ERROR ===")
        print(str(e)[:500])
