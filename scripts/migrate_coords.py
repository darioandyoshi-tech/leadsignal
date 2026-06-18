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

from app.models import Signal, SignalType, Company  # noqa: E402


def ensure_columns(engine):
    with engine.connect() as conn:
        conn.execute(
            text(
                "ALTER TABLE signals ADD COLUMN IF NOT EXISTS lat DOUBLE PRECISION, "
                "ADD COLUMN IF NOT EXISTS lng DOUBLE PRECISION"
            )
        )
        conn.execute(
            text(
                "ALTER TABLE companies ADD COLUMN IF NOT EXISTS latitude DOUBLE PRECISION, "
                "ADD COLUMN IF NOT EXISTS longitude DOUBLE PRECISION"
            )
        )
        conn.commit()


def geocode_rows(session, rows, address_attr, lat_attr, lng_attr, limit, sleep):
    api_key = os.getenv("GOOGLE_PLACES_API_KEY")
    if not api_key:
        print("ERROR: GOOGLE_PLACES_API_KEY not set")
        sys.exit(1)

    rows = list(rows)[:limit]
    updated = 0
    failed = 0
    skipped = 0
    for i, row in enumerate(rows, 1):
        address = getattr(row, address_attr, None)
        lat = getattr(row, lat_attr, None)
        lng = getattr(row, lng_attr, None)
        if lat is not None and lng is not None:
            skipped += 1
            continue
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
                setattr(row, lat_attr, loc["lat"])
                setattr(row, lng_attr, loc["lng"])
                updated += 1
                print(f"[{i}/{len(rows)}] OK {row.id}: {address} -> {loc['lat']},{loc['lng']}")
            else:
                failed += 1
                print(f"[{i}/{len(rows)}] FAIL {row.id}: {address} ({data.get('status')})")
        except Exception as exc:
            failed += 1
            print(f"[{i}/{len(rows)}] ERR {row.id}: {address} ({exc})")
        if i < len(rows):
            time.sleep(sleep)
    return updated, failed, skipped


def main():
    parser = argparse.ArgumentParser(description="Geocode signals without lat/lng")
    parser.add_argument("--signal-type", default=None, help="Signal type to geocode")
    parser.add_argument("--limit", type=int, default=500, help="Max rows to process")
    parser.add_argument("--sleep", type=float, default=0.1, help="Seconds between API calls")
    parser.add_argument("--geocode-companies", action="store_true", help="Also geocode companies missing coordinates")
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

    signal_updated = signal_failed = signal_skipped = 0
    company_updated = company_failed = company_skipped = 0

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
        signal_rows = stmt.order_by(Signal.id).limit(args.limit).all()

    print(f"Processing {len(signal_rows)} signal rows (signal_type={args.signal_type or 'all'}, limit={args.limit})")
    with Session(engine) as session:
        signal_updated, signal_failed, signal_skipped = geocode_rows(
            session, signal_rows, "location_name", "lat", "lng", args.limit, args.sleep
        )
        session.add_all(signal_rows)
        session.commit()
    print(f"SIGNALS done updated={signal_updated} failed={signal_failed} skipped={signal_skipped}")

    if args.geocode_companies:
        with Session(engine) as session:
            company_rows = (
                session.query(Company)
                .filter(
                    (Company.latitude == None) | (Company.longitude == None),
                    Company.city.ilike("%omaha%"),
                )
                .order_by(Company.id)
                .limit(args.limit)
                .all()
            )
        print(f"Processing {len(company_rows)} company rows")
        with Session(engine) as session:
            company_updated, company_failed, company_skipped = geocode_rows(
                session, company_rows, "name", "latitude", "longitude", args.limit, args.sleep
            )
            session.add_all(company_rows)
            session.commit()
        print(f"COMPANIES done updated={company_updated} failed={company_failed} skipped={company_skipped}")

    print(
        f"DONE signals(updated={signal_updated},failed={signal_failed},skipped={signal_skipped}) "
        f"companies(updated={company_updated},failed={company_failed},skipped={company_skipped})"
    )


if __name__ == "__main__":
    main()
