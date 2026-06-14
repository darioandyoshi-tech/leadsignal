#!/usr/bin/env python3
"""Set required env vars on the Render LeadSignal service."""

import argparse
import json
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


def list_env_vars():
    url = f"https://api.render.com/v1/services/{SRV}/env-vars"
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {TOKEN}", "Accept": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.loads(resp.read().decode())
            for item in data:
                ev = item.get("envVar", item)
                print(json.dumps({"key": ev.get("key"), "value": ev.get("value")}))
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code}: {e.read().decode()[:500]}")


def set_env_var(key: str, value: str):
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


def main():
    parser = argparse.ArgumentParser(description="Manage Render env vars for LeadSignal")
    parser.add_argument("--list", action="store_true", help="List current env vars")
    parser.add_argument("--set", action="append", nargs=2, metavar=("KEY", "VALUE"), help="Set an env var")
    args = parser.parse_args()

    if args.list:
        list_env_vars()
    if args.set:
        for key, value in args.set:
            set_env_var(key, value)
    if not args.list and not args.set:
        # Default: set base vars if not already present
        defaults = {
            "PYTHON_VERSION": "3.12.0",
            "DATABASE_URL": "sqlite+aiosqlite:///./leadsignal.db",
            "SYNC_DATABASE_URL": "sqlite:///./leadsignal.db",
            "SECRET_KEY": "818c472758002ef877100977c650583a21973e011df04020fb07f40637586998",
            "ADMIN_SECRET": "leadsignal-admin-2026",
        }
        for key, value in defaults.items():
            set_env_var(key, value)


if __name__ == "__main__":
    main()
