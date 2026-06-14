# LeadSignal — Project Status

**Last updated:** June 14, 2026 04:31 CDT

## Live Links
- GitHub (private): https://github.com/darioandyoshi-tech/leadsignal
- Dashboard: https://leadsignal-dme1.vercel.app
- Backend API: not yet deployed (currently localhost:8000)

## What's Working
- Full MVP codebase in `/home/dario/.openclaw/workspace/leadsignal/`
- FastAPI backend: auth, billing, signals, alerts
- Scraper pipelines: Indeed, Google Places reviews, Omaha permits (seed)
- Next.js dashboard: deployed to Vercel
- Git repo synced to GitHub

## What's Not Done
- [ ] Backend hosting
- [ ] Postgres + Redis provisioned
- [ ] Stripe products/prices created
- [ ] Live Omaha permit feed
- [ ] Frontend login/register pages
- [ ] API env var wired in Vercel

## Credentials & Secrets
- Google Maps API key: stored in `backend/.env`, `backend/.env.example`, `scraper/.env`
- GitHub token and Vercel token: used for deployment; should be rotated after setup if desired

## Immediate Next Steps
1. Host backend (Render/Railway/Fly.io)
2. Create Stripe products via `scripts/setup_stripe.sh`
3. Set `NEXT_PUBLIC_API_URL` in Vercel
4. Provision Postgres and run migrations
5. Wire real permit feed
