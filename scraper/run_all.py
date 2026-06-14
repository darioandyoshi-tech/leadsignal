"""Run all scraper sources and produce a summary report."""

import sys
import os

# Make backend models importable from scraper directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scraper.sources import (
    apify_jobs_reviews,
    google_reviews,
    permits_omaha,
    accela_omaha,
    dcgis_parcels,
    ne_dor_delinquency,
    sarpy_delinquency,
    douglas_bids,
    civicdata_permits,
    nlcc_licenses,
    usaspending_omaha,
    odr_feeds,
    ne_sos_batch,
    ne_ucc,
    ne_hhs_licenses,
    bbb_omaha,
    osha_omaha,
    landmarkweb_deeds,
    permitstack_omaha,
)


SOURCES = [
    apify_jobs_reviews,
    odr_feeds,
    dcgis_parcels,
    douglas_bids,
    ne_dor_delinquency,
    sarpy_delinquency,
    nlcc_licenses,
    usaspending_omaha,
    permits_omaha,
    accela_omaha,
    civicdata_permits,
    google_reviews,
    ne_sos_batch,
    ne_ucc,
    ne_hhs_licenses,
    bbb_omaha,
    osha_omaha,
    landmarkweb_deeds,
    permitstack_omaha,
]


def main():
    results = []
    for source in SOURCES:
        name = getattr(source, "__name__", str(source))
        print(f"Running {name}...")
        try:
            result = source.run()
            results.append(result)
            print(result)
        except Exception as e:
            print(f"ERROR in {name}: {e}")
            results.append({"source": name, "error": str(e)})

    total_created = sum(r.get("signals_created", 0) for r in results)
    print(f"\nTotal signals created: {total_created}")
    return results


if __name__ == "__main__":
    main()
