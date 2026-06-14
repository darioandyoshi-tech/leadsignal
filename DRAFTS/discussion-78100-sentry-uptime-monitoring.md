Congratulations on launching Uptime Monitoring in open beta! This is a fantastic addition to the Sentry ecosystem.

The integration with distributed tracing is particularly clever - being able to pinpoint errors during uptime checks significantly speeds up troubleshooting. I noticed several community members asking about features that are already on your roadmap:

- Configurable check intervals (you mentioned this is coming soon)
- Multi-region monitoring (especially for Asia/China coverage)
- Public status pages
- Maintenance window support

Regarding the alerting architecture, I'd love to hear your thoughts on the monitor-first vs alert-first approach. Many established uptime monitoring solutions (like UptimeRobot, BetterUptime, etc.) separate the monitor configuration from alerting rules, allowing more flexibility - for example, running checks from 5 regions but only alerting if 3+ regions detect downtime.

At PulseWatch, we've found that giving users control over both monitoring frequency and alerting thresholds helps reduce false positives while maintaining sensitivity to real issues. The ability to see historical performance trends (response times, uptime percentages) is also crucial for capacity planning and proving reliability to stakeholders.

Keep up the great work - excited to see how this feature evolves!