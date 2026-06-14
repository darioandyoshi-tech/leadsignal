Draft comment for OpenStatus latency vs uptime discussion:

This is such an important question for status page design! From our experience building PulseWatch, we've found that the most effective status pages actually show both latency AND uptime metrics - they serve different but complementary purposes.

Uptime gives you the big-picture reliability picture (is the service working or not), while latency reveals the user experience quality (how well is it working). Many teams we work with start with basic uptime monitoring but quickly realize their users care just as much about performance as availability.

For example, a service might show 99.9% uptime but have p95 latency of 5+ seconds during peak hours - technically "up" but practically degraded from a user perspective. Conversely, showing only latency without uptime context can miss complete outages.

In PulseWatch, we provide both metrics by default because we've seen teams need to answer different questions:
- "Is my service available?" → Uptime percentage
- "Is my service performing well?" → Latency distributions (p50, p95, p99)

The approach you're already taking with p95 latency plus daily request counts is solid! Teams often find that showing latency trends over time (hourly/daily) alongside current values helps them spot degradation patterns before they become full outages.

Would love to hear how you're thinking about alerting thresholds for latency vs uptime - that's another area where we've seen teams benefit from flexible, multi-level alerting.