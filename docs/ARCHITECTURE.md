# LeadSignal Architecture

## High-level Flow

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│  Sources    │ → │  Scraper    │ → │  Postgres   │
│  (APIs/web) │   │  Pipelines  │   │  (signals)  │
└─────────────┘   └─────────────┘   └──────┬──────┘
                                           │
                    ┌──────────────────────┼──────────────────────┐
                    ↓                      ↓                      ↓
              ┌─────────┐           ┌──────────┐            ┌─────────┐
              │ Alerts  │           │ Dashboard│            │  API    │
              │ (cron)  │           │(Next.js) │            │(FastAPI)│
              └─────────┘           └──────────┘            └─────────┘
```

## Data Model (Postgres)

### `companies`
- `id` UUID PK
- `name`, `domain`, `website`, `industry`
- `location` (city, state, zip, lat, lon)
- `external_ids` JSONB (google_place_id, indeed_employer_id, etc.)
- `created_at`, `updated_at`

### `signals`
- `id` UUID PK
- `company_id` FK
- `signal_type` ENUM: `hiring_spike`, `negative_review_cluster`, `permit_filing`
- `severity` INT (1-5)
- `source_url`, `source_api`
- `metadata` JSONB (raw-ish normalized data)
- `detected_at`, `published_at`
- `is_alerted` BOOL

### `subscriptions`
- `id` UUID PK
- `user_id` FK
- `tier` ENUM: `starter`, `pro`, `growth`, `enterprise`
- `stripe_subscription_id`
- `status`, `current_period_end`
- `settings` JSONB (signal types, geography, delivery channels)

### `alerts`
- `id` UUID PK
- `subscription_id` FK
- `signal_ids` ARRAY UUID
- `channel` ENUM: `email`, `slack`, `discord`, `webhook`, `dashboard`
- `status`, `sent_at`, `opened_at`

## Signal Scoring

- Hiring spike: jobs posted in last 7 days vs baseline; threshold > 2σ or > 3 new listings in 7 days.
- Negative review cluster: ≥3 reviews ≤2 stars within 14 days for same company.
- Permit filing: any new commercial permit in target zip codes; scored by project value if available.

## Tiers (MVP)

| Tier | Price | Geography | Signals | Delivery | API/CSV |
|------|-------|-----------|---------|----------|---------|
| Starter | $49/mo | 1 city (Omaha) | Weekly digest | Email + dashboard | CSV export |
| Pro | $149/mo | 3 cities | Real-time | Email + Slack/Discord + dashboard | CSV + API (100 req/mo) |
| Growth | $399/mo | State/regional | Real-time | All channels + webhooks | API + white-glove setup |
| Enterprise | custom | Custom | Custom | All + dedicated | Unlimited + SLA |

## Sources

1. Hiring
   - Indeed RSS / scraping
   - LinkedIn job search (limited)
   - ZipRecruiter / CareerBuilder where available
   - Company career pages (fallback)
2. Reviews
   - Google Places API
   - Yelp Fusion API
   - BBB (public pages)
   - G2/Capterra for tech companies
3. Permits
   - City of Omaha open data / Accela
   - Douglas County permits
   - Socrata / OpenDataSoft portals
   - Neighbor city APIs (Papillion, Bellevue, etc.)

## Tech Stack
- Python 3.12
- FastAPI + SQLAlchemy 2 + Alembic
- PostgreSQL 16
- Next.js 15 + Tailwind + shadcn/ui
- Stripe Checkout + Customer Portal
- Celery or APScheduler for cron alerts
- AgentMail or SMTP for email delivery
