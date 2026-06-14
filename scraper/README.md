
# LeadSignal Scraper

Python collection pipelines for local market signals.

## Signals
- Hiring spikes (`hiring_spike`)
- Negative review clusters (`negative_review_cluster`)
- Permit filings (`permit_filing`)

## Run

```bash
cd scraper
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_all.py
```

## Design
- `sources/` — one module per source
- `detectors/` — signal detection logic
- `db_client.py` — inserts into Postgres via SQLAlchemy sync engine
- `config.py` — geography, keywords, thresholds
