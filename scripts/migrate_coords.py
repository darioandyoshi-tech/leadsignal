#!/usr/bin/env python3
"""Background geocode migration for signals without lat/lng.

Run from repo root as a module:
    python -m scripts.migrate_coords [--signal-type=TYPE] [--limit=500]
"""

import argparse
import os
import sys
import time

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

# Add backend so app imports work when run as a module from repo root.
repo_root = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
sys.path.insert(0, repo_root)
sys.path.insert(0, os.path.join(repo_root, "backend"))

from app.models import Signal, SignalType  # noqa: E402


def ensure_columns(engine):
    with engine.connect() as conn:
        conn.execute(
            text(
                "ALTER TABLE signals ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION, "
                "ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION"
            )
        )
        conn.commit()


def main():
    parser = argparse.ArgumentParser(description="Geocode signals without lat/lng")
    parser.add_argument("--signal-type", default=None, help="Signal type to geocode")
    parser.add_argument("--limit", type=int, default=500, help="Max rows to process")
    parser.add_argument("--sleep", type=float, default=0.05, help="Seconds between API calls")
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL_SYNC") or os.getenv("DATABASE_URL")
    if not database_url:
        print("ERROR: DATABASE_URL or DATABASE_URL_SYNC not set")
        sys.exit(1)

    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_PLACES_API_KEY not set")
        sys.exit(1)

    engine = create_engine(database_url)
    ensure_columns(engine)

    with Session(engine) as session:
        stmt = session.query(Signal).filter(
            (Signal.lat == None) | (Signal.lng == None),
            Signal.location_name != None,
        )
        if args.signal_type:
            try:
                target = SignalType(args.signal_type)
            except ValueError:
                print(f"ERROR: Invalid signal_type: {args.signal_type}")
                sys.exit(1)
            stmt = stmt.filter(Signal.signal_type == target)
        stmt = stmt.order_by(Signal.id).limit(args.limit)
        rows = stmt.all()

    print(f"Processing {len(rows)} rows (signal_type={args.signal_type or 'all'}, limit={args.limit})")

    updated = 0
    failed = 0
    skipped = 0
    for i, s in enumerate(rows, 1):
        address = s.location_name
        if not address:
            skipped += 1
            continue
        try:
            res = requests.get(
                "https://maps.googleapis.com/maps/api/geocode/json",
                params={"address": f"{address}, Omaha, NE", "key": api_key},
                timeout=15,
            )
            data = res.json()
            if data.get("status") == "OK" and data.get("results"):
                loc = data["results"][0]["geometry"]["location"]
                s.lat = loc["lat"]
                s.lng = loc["lng"]
                updated += 1
                print(f"[{i}/{len(rows)}] OK {s.id}: {address} -> {s.lat},{s.lng}")
            else:
                failed += 1
                print(f"[{i}/{len(rows)}] FAIL {s.id}: {address} ({data.get('status')})")
        except Exception as exc:
            failed += 1
            print(f"[{i}/{len(rows)}] ERR {s.id}: {address} ({exc})")
        if i < len(rows):
            time.sleep(args.sleep)

    with Session(engine) as session:
        session.add_all(rows)
        session.commit()

    print(f"DONE processed={len(rows)} updated={updated} failed={failed} skipped={skipped}")


if __name__ == "__main__":
    main()
