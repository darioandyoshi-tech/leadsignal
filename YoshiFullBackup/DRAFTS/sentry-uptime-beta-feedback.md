# Sentry Discussion #78100 - Uptime Monitoring Open Beta Feedback

**URL:** https://github.com/getsentry/sentry/discussions/78100  
**Topic:** Uptime Monitoring Now in Open Beta  
**Activity:** Very active — 20+ comments with feature requests, bug reports, pricing questions  
**Why relevant:** People actively evaluating Sentry's uptime monitoring; good chance to position PulseWatch as complementary

---

## Draft Comment

```
Exciting to see Sentry enter this space! 👋

A few thoughts from running PulseWatch (https://pulsewatch.us) in production for a while:

**On pricing transparency:**
Totally agree this should be clearer. We learned the hard way that hidden pricing kills trust — we put ours front-and-center now.

**On multi-region checks:**
This is huge. We monitor from 6 regions and have caught:
- AWS us-east-1 issues that eu-west-1 didn't see
- Cloudflare routing problems affecting Asia only
- Anthropic API degradation in specific clouds

If you're planning region selection, consider letting users pick which regions matter for *their* user base.

**On intervals:**
Glad you're shipping configurable intervals! For context:
- 1-minute: Good for critical customer-facing APIs
- 5-minute: Sweet spot for most services
- 15-60 minute: Fine for internal tools

**One gap we've seen:**
Sentry's uptime monitoring checks *your* endpoints. But what about vendor dependencies? If Stripe/AWS/Anthropic goes down, your health endpoint might still return 200 while everything breaks.

We built PulseWatch to complement internal monitoring by focusing purely on external dependencies you don't control. They work well together — Sentry for your stuff, PulseWatch for everyone else's stuff.

**On public status pages:**
Yes please! This is a common ask. Being able to embed or link to a public page is table stakes for B2B.

Looking forward to seeing how this evolves. The distributed tracing integration is a nice touch. 🚀
```

---

## Notes

- Supportive tone (Sentry is doing good work)
- Share specific learnings (credibility builder)
- Position PulseWatch as complementary, not competitive
- Address multiple points from the discussion (shows we read it)
- Offer concrete insights (region selection, intervals)
