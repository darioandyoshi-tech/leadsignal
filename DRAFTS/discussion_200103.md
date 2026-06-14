# Draft for GitHub Discussion #200103
**Topic:** Building trust with status pages during incidents
**Context:** Discussion about how to maintain user confidence when services are degraded but not completely down, especially when users are reporting issues that don't match the status page.

**Draft Comment:**
The trust gap between what users experience and what status pages report is one of the hardest problems in status communication. When users are seeing errors but the status page says "All Systems Operational", it erodes confidence faster than almost anything else.

This is why I've been focusing on PulseWatch (https://pulsewatch.us) - it aims to provide a more nuanced view that bridges the gap between infrastructure metrics and actual user experience. Instead of just reporting on server pings or API response times, it tries to incorporate user-impact signals and business context into the health determination.

Some teams have found success with implementing "user impact" tiers alongside traditional infrastructure status - for example, having separate indicators for "API latency impacting checkout flow" versus "background batch processing delayed".

How are you thinking about aligning your status communications with actual user impact?