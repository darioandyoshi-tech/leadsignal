# Draft Comment: Keep (keephq/keep) AIOps Alert Management Discussion

Hi Keep team,

I've been evaluating Keep as a potential alert management layer for our monitoring infrastructure at PulseWatch, and the concept of "GitHub Actions for monitoring tools" really resonates with our approach to workflow automation.

The declarative YAML workflows for automating alerts, incident management, and integrations across monitoring sources seem like they could solve a significant pain point we see with our clients: alert fatigue and inconsistent incident response across different monitoring tools.

One question I have: how does Keep handle deduplication and correlation of alerts from multiple sources? For example, if we're monitoring a service through both internal checks (like Uptime Kuma or Upptime) and external vendor monitoring (like PulseWatch), we might get duplicate alerts for the same underlying issue.

Have you implemented intelligent alert grouping or correlation features that could help reduce noise while ensuring critical incidents don't get missed?

Additionally, I'm interested in how Keep integrates with status page generators. Could workflows be designed to automatically update status pages based on alert resolutions or incident closures?

This kind of orchestration layer could be invaluable for creating cohesive monitoring experiences that combine the best of internal and external monitoring perspectives.

Looking forward to learning more about your approach!

Yoshi from HIVE/PulseWatch