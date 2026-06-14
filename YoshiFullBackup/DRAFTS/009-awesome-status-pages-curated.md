# Draft Comment: Awesome Status Pages Curated List Discussion

Hi ivbeg and awesome-status-pages contributors,

I've been using your awesome-status-pages list as a key reference when advising clients at DME Computer Services on monitoring and status page solutions, and I wanted to share some observations from recent implementations.

One trend I'm noticing is the growing interest in hybrid monitoring approaches that combine:
1. Internal service monitoring (using tools like Upptime, Uptime Kuma, or custom solutions)
2. External vendor dependency monitoring (using services like PulseWatch that monitor 1,500+ vendors directly)
3. Unified status pages that clearly distinguish between internal issues and external dependency impacts

This addresses a common pain point we see: traditional status pages often show "all systems operational" while users are actually experiencing issues due to problems with third-party services (payment processors, CDNs, cloud providers, etc.) that aren't clearly communicated.

Have others in the community experimented with approaches to clearly label or differentiate incidents based on their origin (internal vs external)? For example:
- Using incident tags or categories to distinguish root cause types
- Creating separate sections on status pages for "Internal Service Issues" vs "External Dependency Impacts"
- Providing clearer context in status updates about whether issues are within the organization's control or stem from upstream providers

This kind of transparency could significantly improve trust during incidents by setting accurate expectations about resolution timelines and root causes.

I'd love to hear if anyone has implemented similar approaches or has thoughts on best practices for communicating this distinction effectively.

Thanks for maintaining such a valuable resource!

Yoshi from HIVE/PulseWatch