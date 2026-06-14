# LeadSignal — Local Market Opportunity Scanner

A PulseWatch-style commercial product for local market signals.

## MVP Scope
- Geography: Omaha, Nebraska (proof of market; expansion later)
- Signals:
  - Hiring spikes (job postings)
  - Negative review clusters
  - Permit filings
- Buyers / tiers:
  - Local sales / lead gen
  - Service providers
  - Investors / real estate
  - Enterprise / API access
- Delivery: email alerts, web dashboard, Slack/Discord/webhook, CSV export, API

## Architecture
- Python scrapers + Postgres + FastAPI backend + Next.js dashboard + Stripe subscriptions + cron alerts
- Sources: official APIs first; careful scraping fallback with rate limiting

## Repo Layout
- `backend/` — FastAPI app, models, API routes, auth, billing
- `frontend/` — Next.js dashboard
- `scraper/` — signal collection pipelines
- `scripts/` — cron/utility scripts
- `data/` — local seed/sample data
- `docs/` — product docs

## Status
Initial scaffold created 2026-06-14.
