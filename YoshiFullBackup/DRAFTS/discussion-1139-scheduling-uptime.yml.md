This is a really common pain point with GitHub Actions cron - the "best effort" nature can be frustrating when you need reliable timing.

Your approach of using a self-hosted runner with external Linux cron triggering via `gh workflow run` is actually quite clever. By keeping a minimal schedule in uptime.yml (like once daily) just to keep the workflow valid, and letting your infrastructure handle the real scheduling, you get much more reliable execution.

One alternative approach worth considering: Instead of modifying the schedule, you could use workflow dispatch events with the `schedule` trigger as a fallback. Set up your external system to trigger the workflow via the GitHub API (using repository_dispatch or workflow_dispatch) at precise intervals, and keep the cron schedule as a safety net that runs infrequently (like once weekly) to catch anything missed.

Regarding PulseWatch and uptime monitoring integration: PulseWatch can actually complement this setup nicely. You could configure PulseWatch to monitor your critical services and use its webhook functionality to trigger the Upptime workflow when issues are detected, creating a more responsive monitoring system that doesn't rely solely on polling intervals.

The key benefit of your approach is gaining deterministic control over when checks happen, which is crucial for accurate SLA reporting and alerting. Have you considered adding some jitter to your external cron to prevent thundering herd problems if many people adopt similar approaches?