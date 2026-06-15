"""Omaha Municipal Land Bank (OMLB) Tolemi map scraper.

Discovered public GraphQL endpoint: https://cg.tolemi.com/q
city-alias header: omaha-municipal-land-bank-ne
product header: publiCity

Public programs:
  - standard-inventory
  - shovel-ready
  - land-assembly
  - large-site-development
  - depository-not-for-sale

Assets query via `params.programAlias`. The endpoint returns the same 302
assets for every alias tested; likely the program filter is ignored or all
public OMLB properties are returned together. We ingest all unique assets once.
"""
import json
import logging
import requests
from typing import Dict, List, Any

from scraper import config
from scraper.db_client import get_or_create_company, insert_signal, ensure_tables

logger = logging.getLogger(__name__)

GRAPHQL_URL = "https://cg.tolemi.com/q"
CITY_ALIAS = "omaha-municipal-land-bank-ne"
HEADERS = {
    "Content-Type": "application/json",
    "city-alias": CITY_ALIAS,
    "product": "publiCity",
}

PROGRAM_ALIASES = [
    "standard-inventory",
    "shovel-ready",
    "land-assembly",
    "large-site-development",
    "depository-not-for-sale",
]


def _query_assets(program_alias: str, limit: int = 100, offset: int = 0) -> List[Dict[str, Any]]:
    query = {
        "query": """
        query getPublicAssets($params: JSON, $limit: Int, $offset: Int) {
          assets(params: $params, limit: $limit, offset: $offset) {
            id
            alias
            commonName
            address
            zipCode
            latitude
            longitude
            parcelId
            landSize
            assetType { id name }
            programEligibles {
              id
              program { id alias name }
              price
              bundlePrice
              isIneligible
              applicationStartDate
              applicationDeadline
            }
          }
        }
        """,
        "variables": {
            "params": {"programAlias": program_alias},
            "limit": limit,
            "offset": offset,
        },
    }
    r = requests.post(GRAPHQL_URL, json=query, headers=HEADERS, timeout=60)
    r.raise_for_status()
    data = r.json()
    if "errors" in data and data.get("errors"):
        logger.warning("GraphQL errors for %s: %s", program_alias, data["errors"])
        return []
    return data.get("data", {}).get("assets", []) or []


def _fetch_all_assets(program_alias: str, max_pages: int = 20) -> List[Dict[str, Any]]:
    assets: List[Dict[str, Any]] = []
    offset = 0
    for _ in range(max_pages):
        page = _query_assets(program_alias, limit=100, offset=offset)
        if not page:
            break
        assets.extend(page)
        offset += len(page)
        if len(page) < 100:
            break
    return assets


def fetch_signals() -> List[Dict[str, Any]]:
    seen = set()
    signals: List[Dict[str, Any]] = []
    for alias in PROGRAM_ALIASES:
        assets = _fetch_all_assets(alias)
        logger.info("OMLB program %s returned %d asset rows", alias, len(assets))
        for a in assets:
            aid = a.get("id")
            if not aid or aid in seen:
                continue
            seen.add(aid)
            address = a.get("address") or "No Address"
            zip_code = a.get("zipCode") or ""
            full_address = f"{address}, {zip_code}".strip(", ")
            price = None
            programs = []
            for e in a.get("programEligibles", []):
                programs.append(e.get("program", {}).get("alias", alias))
                if price is None and e.get("price") is not None:
                    price = e.get("price")
            signal = {
                "external_id": f"omlb-{aid}",
                "title": f"OMLB property: {full_address}",
                "description": f"Omaha Municipal Land Bank property listed in {', '.join(programs)}. Parcel {a.get('parcelId')}. Land size {a.get('landSize')} acres. Price ${price}" if price else f"Omaha Municipal Land Bank property listed in {', '.join(programs)}. Parcel {a.get('parcelId')}.",
                "signal_type": "land_bank_property",
                "source": "omlb_tolemi",
                "source_url": "https://omlb-publicity.tolemi.com/",
                "address": full_address,
                "latitude": a.get("latitude"),
                "longitude": a.get("longitude"),
                "metadata": {
                    "parcel_id": a.get("parcelId"),
                    "omlb_asset_id": aid,
                    "omlb_alias": a.get("alias"),
                    "land_size_acres": a.get("landSize"),
                    "price": price,
                    "programs": programs,
                    "zip_code": zip_code,
                },
            }
            signals.append(signal)
    return signals


def run() -> Dict[str, Any]:
    logger.info("Starting OMLB Tolemi scraper")
    ensure_tables()
    signals = fetch_signals()
    inserted = 0
    for sig in signals:
        try:
            company = get_or_create_company(
                name=f"OMLB Property {sig['metadata']['parcel_id']}",
                address=sig.get("address"),
                city="Omaha",
                state="NE",
                zip_code=sig["metadata"].get("zip_code"),
                latitude=sig.get("latitude"),
                longitude=sig.get("longitude"),
                source="omlb_tolemi",
            )
            insert_signal(
                company_id=company.id,
                external_id=sig["external_id"],
                signal_type=sig["signal_type"],
                title=sig["title"],
                description=sig["description"],
                source_url=sig["source_url"],
                metadata=sig["metadata"],
                latitude=sig.get("latitude"),
                longitude=sig.get("longitude"),
            )
            inserted += 1
        except Exception as e:
            logger.error("Failed to insert OMLB signal %s: %s", sig["external_id"], e)
    logger.info("OMLB Tolemi scraper complete: %d signals inserted", inserted)
    return {"source": "omlb_tolemi", "inserted": inserted, "fetched": len(signals)}


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print(run())
