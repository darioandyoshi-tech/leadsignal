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

## Deploy

### Backend (Render)
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy?repo=https://github.com/darioandyoshi-tech/leadsignal)

The backend defaults to SQLite for the MVP demo. Set `DATABASE_URL` and `SYNC_DATABASE_URL` to a real Postgres URL when ready.

### Frontend (Vercel)
1. Import `https://github.com/darioandyoshi-tech/leadsignal` in Vercel
2. Set root directory to `frontend`
3. Add environment variable: `NEXT_PUBLIC_API_URL=https://your-render-backend.onrender.com`

## Architecture
- Python scrapers + Postgres + FastAPI + Next.js dashboard + Stripe subscriptions + cron alerts
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
