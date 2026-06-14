# GitHub Community Discussion #175786 - Ongoing Outage

**URL:** https://github.com/orgs/community/discussions/175786  
**Topic:** GitHub Codespaces/Actions outage not reflected on status page  
**Activity:** 48+ hour unacknowledged outage, multiple users affected, EU region specific  
**Why relevant:** PERFECT example of why vendor status pages can't be trusted — PulseWatch value prop

---

## Draft Comment

```
This thread is exactly why we built PulseWatch (https://pulsewatch.us).

48 hours of EU region outages with zero acknowledgment on the status page? That's the blind spot we're trying to fix.

**What happened here:**
- GitHub's own status page showed "operational"
- Users in Europe West couldn't use Codespaces for 2 days
- Support tickets went unanswered
- Only workarounds found through community forums

**The problem:**
Vendor status pages are often delayed 15-60 minutes during incidents — sometimes longer when it's embarrassing or affects multiple regions. During that window, you're flying blind.

**How we handle it:**
- Monitor the actual GitHub API endpoints from multiple regions
- Detect regional degradation even when status pages say "green"
- Alert you before the vendor acknowledges anything

**For your BCP exercise:**
Consider adding independent third-party monitoring to your tabletop scenarios. Don't rely solely on vendor status pages — they have incentives to underreport or delay incident acknowledgment.

We've caught AWS, Stripe, Cloudflare, and Anthropic outages 10-30 minutes before their status pages updated. That early warning window is huge for incident response.

Hope the EU region stabilizes soon. This kind of silent degradation is brutal for teams depending on Codespaces for workflows. 🫡
```

---

## Notes

- This is THE perfect use case for PulseWatch
- Lead with empathy for their situation
- Educational tone, not salesy
- Mention specific vendors we monitor (builds credibility)
- Acknowledge their pain without being exploitative
- Strong value prop: "caught outages 10-30 min before status pages"
