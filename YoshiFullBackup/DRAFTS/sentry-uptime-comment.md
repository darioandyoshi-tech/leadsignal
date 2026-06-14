Great thread! 👋

We built **PulseWatch** (https://pulsewatch.us) for exactly this gap you're describing — specifically the "vendor outage" blind spot.

**What we monitor:**
- 1500+ third-party vendors (Stripe, AWS, Anthropic, Cloudflare, etc.)
- 60-second checks from multiple regions
- Catches outages before status pages update (vendor status pages are often delayed 15-60 min)

**Why we built it:**
Our team kept getting burned by "dependency outages" that our internal monitoring missed. We'd see errors spike, but our uptime tools said "all green" because they only checked *our* endpoints. The actual problem was Stripe/AWS/Anthropic having issues.

**What's different:**
- We don't replace internal monitoring — we complement it
- Focus purely on external dependencies you don't control
- Free tier covers most startups; paid tiers for higher frequency

**Your SentryNet idea sounds solid.** The integration with Sentry Issues would be clutch — correlating your error spikes with vendor outages automatically.

Happy to share what we've learned about multi-region check design or false-positive reduction if useful. Keep building! 🚀
