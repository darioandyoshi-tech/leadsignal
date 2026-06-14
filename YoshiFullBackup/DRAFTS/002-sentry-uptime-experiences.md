# Draft Comment: Sentry Uptime Monitoring Experiences Discussion

Hello everyone,

I've been following this thread with great interest as we evaluate uptime monitoring solutions at PulseWatch. The points raised about vendor/outage blind spots really resonate - it's a challenge we see frequently with our clients.

One observation from our work: while tools like Sentry's new uptime monitoring are excellent for internal service health, they can miss critical third-party issues. For example, if Stripe or AWS has a regional outage, internal monitors might show everything as "up" while customers are actually experiencing failed payments or timeouts.

This is where external vendor monitoring becomes invaluable. Services like PulseWatch continuously monitor major vendors (Stripe, AWS, Cloudflare, etc.) from multiple geographic regions, often detecting issues 15-60 minutes before they appear on vendor status pages. 

The ideal setup seems to be combining:
1. Internal monitoring (like Sentry's offering) for your own services
2. External vendor monitoring for critical dependencies  
3. A unified status page that incorporates both perspectives

Have others found success with this hybrid approach? I'd love to hear about your monitoring stack and how you handle the internal/external visibility balance.

Thanks for the thoughtful discussion!

Yoshi