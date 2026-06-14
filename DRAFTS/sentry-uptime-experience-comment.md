# Sentry Discussion #51110 - Uptime Monitoring Experience

**URL:** https://github.com/getsentry/sentry/discussions/51110  
**Topic:** Share your experience and expectations for uptime monitoring  
**Activity:** Active discussion with detailed user feedback on tools (New Relic, Google Cloud, SmokePing)  
**Why relevant:** User discussing false positives, vendor datacenter outages, and building their own solution (SentryNet)

---

## Draft Comment

```
Great breakdown of the monitoring landscape! 👋

Your point about Google's data center melting while their monitoring said "all green" hits home — we've been burned by the same gap.

We built **PulseWatch** (https://pulsewatch.us) specifically for the "vendor outage blind spot" you're describing. A few things we've learned:

**What caught us off-guard:**
- Vendor status pages lag 15-60 minutes during incidents
- Internal monitoring only checks *our* endpoints, not dependencies
- False positives from migrations/deployments (like you mentioned)

**What we monitor differently:**
- 1500+ third-party vendors (Stripe, AWS, Anthropic, Cloudflare, etc.)
- Multi-region checks catch localized outages
- Focus purely on external dependencies you don't control

**Your SentryNet approach sounds solid.** The distributed probe model is smart — we do something similar but focused on vendor endpoints rather than internal services.

One thing that's helped us: correlating error spikes with vendor outage detection. When Sentry errors spike AND PulseWatch detects a Stripe/AWS issue, we auto-suppress alerts instead of paging engineers.

Happy to share what we've learned about multi-region check design or false-positive reduction if useful. The visualization piece is tough — we're still iterating there ourselves.

Keep building! 🚀
```

---

## Notes

- Lead with empathy (acknowledge their pain points)
- Mention PulseWatch naturally as one solution
- Offer value (correlation strategy, false-positive reduction)
- Acknowledge their SentryNet project positively
- No hard sell — focus on shared learning
