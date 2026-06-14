
"""Run all scraper sources and produce a summary report."""

import sys
import os

# Make backend models importable from scraper directory
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scraper.sources import indeed, google_reviews, permits_omaha


def main():
    results = []
    for source in [indeed, google_reviews, permits_omaha]:
        print(f"Running {source.__name__}...")
        try:
            result = source.run()
            results.append(result)
            print(result)
        except Exception as e:
            print(f"ERROR in {source.__name__}: {e}")
            results.append({"source": source.__name__, "error": str(e)})

    total_created = sum(r.get("signals_created", 0) for r in results)
    print(f"\nTotal signals created: {total_created}")
    return results


if __name__ == "__main__":
    main()
