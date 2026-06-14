# Draft Comment: Uptime Kuma Status Page Features Discussion

Hello Uptime Kuma community,

I've been exploring Uptime Kuma for potential use in our monitoring stack at PulseWatch, and I'm particularly impressed with the status page capabilities in recent versions (v1.13+/v1.14+).

The ability to create multiple status pages with domain-based routing is exactly what we need for our MSP business (DME Computer Services) where we manage monitoring for multiple clients with different branding and access requirements.

One feature I'd love to see discussed more is the possibility of embedding status page summaries or badges on external sites (similar to what was mentioned in Issue #3390). This would allow us to create customer-facing uptime widgets that could be embedded in client portals or status pages.

Additionally, I'm curious about the community's thoughts on combining Uptime Kuma's excellent internal monitoring with external vendor monitoring services. For instance:
- Use Uptime Kuma for monitoring client infrastructure and internal services
- Leverage PulseWatch or similar services to monitor critical third-party dependencies (Stripe, AWS, Cloudflare, etc.) 
- Create a unified view that shows both internal health and external dependency status

This approach could help address the "vendor blind spot" problem where internal systems appear healthy but customer experience is degraded due to upstream provider issues.

Has anyone implemented similar hybrid monitoring setups? I'd love to hear about your experiences and any lessons learned.

Keep up the fantastic work on this project!

Yoshi