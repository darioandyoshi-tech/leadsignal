
# LeadSignal Roadmap

## MVP (Done / Scaffolded)
- [x] FastAPI backend with auth, billing, signals, alerts
- [x] Postgres data model for companies, signals, subscriptions, alerts
- [x] Scraper pipelines: Indeed, Google Places reviews, Omaha permits (seed)
- [x] Stripe checkout + customer portal + webhook handling
- [x] Next.js dashboard with signal list and stats
- [x] Email / Slack / Discord / webhook alert engine
- [x] Install script + setup docs

## Next 2 Weeks
- [ ] Add real Omaha permit feed (Accela / Socrata / open data portal)
- [ ] Build public marketing page + pricing table
- [ ] Add CSV export and API key management for Pro/Growth tiers
- [ ] Frontend login/register pages
- [ ] Add company detail page with signal history
- [ ] Alert preference UI (channels, frequency, signal types)
- [ ] Seed real target company list for Omaha
- [ ] Add review sources: Yelp, BBB, G2/Capterra
- [ ] Hiring: add ZipRecruiter + LinkedIn limited search
- [ ] Add basic tests (pytest + backend API tests)

## Month 1
- [ ] Launch paid beta with 5-10 Omaha businesses
- [ ] Cron automation for scrapers + digests
- [ ] Webhook reliability / retry logic
- [ ] Signal scoring refinement based on customer feedback
- [ ] Add more Nebraska metros: Lincoln, Council Bluffs
- [ ] Sales outreach tracker (who was alerted, who signed up)

## Month 3
- [ ] Expand to 10 Midwest metros
- [ ] White-glove onboarding for Growth tier
- [ ] Industry-specific signal packs
- [ ] Chrome extension for one-click signal capture
- [ ] Affiliate / referral program

## Ongoing
- [ ] Compliance review (scraping ToS, CFAA, data retention)
- [ ] Rate limiting and proxy rotation at scale
- [ ] Customer success playbooks by buyer persona
