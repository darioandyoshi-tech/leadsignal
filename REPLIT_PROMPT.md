# LeadSignal — Replit Rebuild Prompt

## What This Is

Rebuild **LeadSignal**, a local-market opportunity scanner for **Omaha, Nebraska metro**. It detects business-triggering events from public records before competitors find them. The MVP is already built in Python/FastAPI + Next.js and deployed on Render + Vercel. This prompt gives you everything needed to reconstruct, improve, and extend it in Replit.

---

## Core Value Proposition

Detect local market signals for B2B sales, service providers, investors, and lead-gen:

- Hiring spikes
- Negative review clusters
- Permit filings (building, electrical, plumbing, mechanical, wrecking, inspections)
- Parcel/property changes
- Tax-delinquent properties
- Government contract awards
- Business licenses
- UCC filings
- New business registrations

Sell subscriptions by tier: Starter / Pro / Growth / Enterprise. Deliver via email, dashboard, Slack, Discord, webhook, CSV, API.

---

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy (SQLite default, Postgres optional), Pydantic
- **Frontend:** Next.js 14 (App Router), TypeScript, Tailwind, shadcn/ui-style Card/Button
- **Payments:** Stripe (products/prices not yet created)
- **Scrapers:** Python modules under `scraper/sources/`, run via `python -m scraper.run_all`
- **Deployment:** Replit (frontend + backend or frontend-only pointing at Render backend)
- **Browser automation:** Playwright (for Accela portal)

---

## Backend API Structure

- `GET  /health`
- `POST /auth/login`, `POST /auth/register`
- `GET  /signals`, `GET /signals/stats`
- `POST /alerts/send`, `POST /alerts/digest`
- `POST /billing/checkout`, `GET /billing/subscription`
- `POST /admin/run-scrapers` (admin only, triggers `scraper.run_all`)

---

## Signal Types

```python
hiring_spike
negative_review_cluster
permit_filing
parcel_change
tax_delinquency
gov_contract_award
business_license
ucc_filing
new_business_registration
```

Add later:
- `health_inspection_failure`
- `business_incident`
- `code_enforcement_case`
- `rental_property_registration`

---

## Live Data Sources (verified)

| Source | Signal Type | URL / API |
|---|---|---|
| Apify Indeed scraper | hiring_spike | `https://api.apify.com/v2/acts/borderline~indeed-scraper` |
| Apify Google Maps Reviews | negative_review_cluster | `https://api.apify.com/v2/acts/compass~Google-Maps-Reviews-Scraper` |
| Google Places API | negative_review_cluster | `https://maps.googleapis.com/maps/api/place/textsearch/json` |
| CivicData inspection history | permit_filing | `https://www.civicdata.com/api/3/action/datastore_search?id=2483a53a-b400-4f25-bac7-1bb7045e70b2` |
| CivicData historical permits | permit_filing | `https://www.civicdata.com/api/3/action/datastore_search?id=efecb9f2-b254-4e34-90ce-4097fbe82322` |
| DCGIS Parcels | parcel_change | `https://dcgis.org/server/rest/services/vector/Parcels_public/FeatureServer/0` |
| Douglas County Purchasing | gov_contract_award | `https://douglascountypurchasing.ionwave.net/SourcingEvents.aspx?SourceType=3` |
| Nebraska DOR delinquency | tax_delinquency | `https://revenue.nebraska.gov/sites/default/files/doc/pad/delinquent_real_prop/2026/` |
| NLCC liquor licenses | business_license | `https://lcc.nebraska.gov/sites/default/files/licensing/Active%20Licensing/Active%20Roster%206.12.26.xlsx` |
| USASpending Omaha awards | gov_contract_award | `https://api.usaspending.gov/api/v2/search/spending_by_award/` |
| PermitStack API | permit_filing | `https://api.permit-stack.com/v1/permits/search` |
| Omaha Daily Record RSS | mixed | `https://www.omahadailyrecord.com` (27 RSS feeds under `/taxonomy/term/.../all/feed`) |
| Nebraska DOL contractors | business_license | `https://dol.nebraska.gov/conreg/Search` |
| NADC bulk ZIP | gov_contract_award | `https://www.nebraska.gov/nadc_data/nadc_data.zip` |

---

## Placeholder / Hard Sources

| Source | Why Hard | Workaround |
|---|---|---|
| Nebraska SOS entity search | reCAPTCHA | Paid batch portal `$15/1000 records` |
| Nebraska UCC | Paid interactive | Subscriber account |
| Sarpy County SmartGov | JS portal | Playwright/Apify |
| Accela live permits | JS portal | Playwright |
| BBB Omaha | Blocks scraping | Apify actor or Parse.bot |
| OSHA establishment search | Oracle APEX | Apify actor |
| Douglas County Sheriff sales | 403 to bot IP | Residential proxy/browser |
| LandmarkWeb deeds | JS disclaimer + paid | Use ODR/DGIS instead |

---

## New High-Value Sources to Add First

These are the edge sources competitors miss:

1. **Douglas County Health food inspections** — easiest win
   - REST: `https://services1.arcgis.com/79kfd2K6fskCAkyg/arcgis/rest/services/FoodServiceData/FeatureServer/0`
   - Map: `https://www.douglascountyhealth.com/food-safety-compliance?view=article&id=553:food-establishment-rating-map`
   - Signal: `health_inspection_failure` → leads for pest control, equipment, HVAC, legal

2. **Omaha Police incident data** — real-time distress signals
   - REST: `https://services2.arcgis.com/qvkbeam7Wirps6zC/ArcGIS/rest/services/RMS_Crime_Incidents/FeatureServer/0`
   - Download: `https://police.cityofomaha.org/crime-information/incident-data-download`
   - Signal: `business_incident` → security, insurance, legal, repair leads

3. **City of Omaha Accela code enforcement + rental registration** — distressed property & owner inventory
   - Enforcement: `https://aca-prod.accela.com/OMAHA/Cap/CapHome.aspx?TabName=Home&module=Enforcement`
   - Rentals: `https://aca-prod.accela.com/OMAHA/Cap/CapHome.aspx?TabName=Home&module=Rentals`
   - Signals: `code_enforcement_case`, `rental_property_registration`

---

## Required Environment Variables

```env
# Backend
DATABASE_URL=sqlite+aiosqlite:///./leadsignal.db
SYNC_DATABASE_URL=sqlite:///./leadsignal.db
SECRET_KEY=change-me-in-production
ADMIN_SECRET=leadsignal-admin-2026

# Stripe
STRIPE_SECRET_KEY=sk_...
STRIPE_PUBLISHABLE_KEY=pk_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_GROWTH=price_...

# Data sources
APIFY_TOKEN=...
GOOGLE_PLACES_API_KEY=...
PERMITSTACK_API_KEY=...

# Frontend
NEXT_PUBLIC_API_URL=https://your-backend-url
```

---

## Replit Setup Instructions

1. Create new Replit from GitHub: `https://github.com/darioandyoshi-tech/leadsignal`
2. The repo contains `.replit` and `replit.nix` for frontend-only mode.
3. For full-stack Replit:
   - Set backend root to `backend/`
   - Install Python 3.12 deps from `backend/requirements.txt`
   - Install frontend deps from `frontend/package.json`
   - Set `NEXT_PUBLIC_API_URL` to the Replit backend URL (or keep pointing at Render)
4. Run scrapers manually or via cron:
   ```bash
   cd backend && python -m scraper.run_all
   ```
5. Make dashboard public for MVP demo; gate paid features later.

---

## Key Architectural Rules

- SQLite is the MVP default. Postgres support exists for scale.
- Scrapers use **synchronous** SQLAlchemy to avoid async/greenlet conflicts.
- The FastAPI app uses **async** SQLAlchemy but sync DB URL resolves to the same absolute SQLite file path.
- All scraper modules expose a `run()` function and return a dict with `source`, `signals_created`, etc.
- `scraper/run_all.py` iterates every source module and prints a summary.
- Use official public APIs first; only fall back to browser automation where necessary.
- All sources must be traceable to official City/County/State URLs (not just ODR).

---

## Dashboard Features to Keep

- Public stat cards for all signal types
- Permit subtype breakdown: Building, Electrical, Mechanical, Plumbing, Wrecking/Demo, Inspection, Other
- Latest signals feed with source links
- Optional auth for paid alerts/subscriptions

---

## Next Priority Actions

1. Build `scraper/sources/dchd_food_inspections.py` (ArcGIS REST)
2. Build `scraper/sources/omaha_police_incidents.py` (ArcGIS REST)
3. Extend `scraper/sources/accela_omaha.py` to scrape `Enforcement` and `Rentals` modules
4. Create Stripe products/prices and wire `/billing`
5. Add alert engine (email/Slack/Discord/webhook) once signals are reliable
6. Rotate exposed tokens (Apify, PermitStack, Google) after setup

---

## Files That Matter

- `backend/app/main.py` — FastAPI app
- `backend/app/models.py` — SQLAlchemy models
- `backend/app/routers/signals.py` — signal list + stats
- `backend/app/routers/admin.py` — run scrapers endpoint
- `scraper/run_all.py` — orchestrator
- `scraper/db_client.py` — shared sync DB helper
- `scraper/sources/*.py` — individual scrapers
- `frontend/app/page.tsx` — dashboard
- `frontend/lib/api.ts` — API client

---

## Competitive Moat

LeadSignal wins by combining **many orthogonal public signals** into one timeline, classified by business intent. ODR charges for public notices; we go straight to the official sources. Generic lead tools miss local public-record velocity. The edge is in the **breadth + recency + classification** of Omaha-specific signals.
