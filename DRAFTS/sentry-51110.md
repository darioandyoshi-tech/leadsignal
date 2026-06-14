# Draft for getsentry/sentry/discussions/51110
**Context:** User discussing their experience with various monitoring tools (SmokePing, New Relic, Google Cloud) and their desire for better brown-out detection and flexible alerting/reporting.

**Draft Comment:**
"Interesting breakdown of the different tools. The struggle with 'brown-outs' vs. total downtime is a classic problem—most tools are binary (up/down), but the real pain is usually in the degraded performance zone.

If you're looking for a way to get that high-level visibility and flexible reporting without the New Relic price tag, you might find PulseWatch interesting. It focuses on that layer of status and vendor monitoring that complements the deep APM/synthetic data you get from Sentry or NR, but keeps the reporting clean and focused on actual service health. Definitely worth a look if you're refining your 'future plan' for a a more efficient monitoring stack."
