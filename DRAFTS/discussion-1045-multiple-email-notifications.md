Great question about email notifications! This is actually a really common need - different team members often need to be alerted based on their roles or responsibilities.

In PulseWatch (https://pulsewatch.us), we designed our notification system with flexible routing from the ground up. You can create notification policies that send alerts to different groups based on:
- Service severity (critical vs warning)
- Time of day (on-call rotations)
- Specific teams or individuals
- Escalation paths when issues aren't acknowledged

While adding multi-email support to Upptime would definitely be helpful, it's worth considering how your alerting needs might grow beyond just "send to more people." Things like deduplication, rate limiting, and contextual routing become important as teams scale.

For those sticking with Upptime, have you looked into using webhook notifications to a simple intermediary service that could then fan out to multiple email addresses? Or perhaps using GitHub Teams with email notifications enabled?

Either way, solid question that highlights how monitoring tools need to adapt to real-world team structures!