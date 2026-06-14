
# LeadSignal — MVP Setup Guide

## 1. Install

```bash
cd /home/dario/.openclaw/workspace/leadsignal
./scripts/install.sh
```

This creates two Python venvs and installs the Next.js frontend.

## 2. Configure

Edit `backend/.env`:

```env
DATABASE_URL=postgresql+asyncpg://leadsignal:leadsignal@localhost:5432/leadsignal
SYNC_DATABASE_URL=postgresql://leadsignal:leadsignal@localhost:5432/leadsignal
SECRET_KEY=change-me-to-a-64-char-random-string
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PRO=price_...
STRIPE_PRICE_GROWTH=price_...
FRONTEND_URL=http://localhost:3000
GOOGLE_PLACES_API_KEY=...
AGENTMAIL_API_KEY=...
AGENTMAIL_SENDER=alerts@leadsignal.ai
REDIS_URL=redis://localhost:6379/0
```

Create the Postgres database:

```bash
sudo -u postgres createdb leadsignal
sudo -u postgres createuser -P leadsignal  # password: leadsignal
```

## 3. Start Services

Terminal 1 — backend:

```bash
cd backend
source .venv/bin/activate
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 — frontend:

```bash
cd frontend
npm run dev
```

Terminal 3 — run scrapers:

```bash
cd scraper
source .venv/bin/activate
python run_all.py
```

## 4. Stripe Products

With the Stripe CLI installed:

```bash
export STRIPE_SECRET_KEY=sk_test_...
./scripts/setup_stripe.sh
```

Add the printed `price_...` IDs to `backend/.env`.

## 5. First Use

1. Open http://localhost:3000
2. Register a user via `/auth/register` or use the frontend login page (add one if needed)
3. Start a Stripe checkout from `/billing/checkout`
4. View signals at `/signals/`
5. Send a digest at `/alerts/digest`

## 6. Cron

Add to crontab for production:

```cron
# Run scrapers every 6 hours
0 */6 * * * cd /path/to/leadsignal/scraper && source .venv/bin/activate && python run_all.py >> /var/log/leadsignal_scraper.log 2>&1

# Daily digest at 8am CT
0 13 * * * cd /path/to/leadsignal && curl -X POST http://localhost:8000/alerts/digest -H "Authorization: Bearer SERVICE_TOKEN"
```

## 7. Deploy

Recommended first deploy:

- Railway / Render for Postgres + backend
- Vercel for frontend
- Stripe production keys
- Google Places API enabled
- AgentMail or SendGrid for email delivery
- Sentry for error tracking
