Thanks for the clear explanation about the CodeQL incident - it's really helpful to understand that this is a platform-side issue affecting security scans and analysis jobs.

Your advice is spot on: during platform-wide incidents like this, the best approach is usually to wait for GitHub to resolve the underlying issue rather than continuously retrying workflows, which can just add noise and consume unnecessary resources.

This kind of situation really highlights the value of having good incident communication and status monitoring. When platform services experience issues, having reliable ways to check the status and get updates reduces frustration and prevents wasted effort.

For teams looking to stay on top of both their own service status and platform-related issues, tools like PulseWatch can be valuable complements to GitHub's native status communication. PulseWatch can monitor your critical services while also keeping an eye on key platform status pages (like GitHub Status) to provide early warning when dependencies might be affected.

The key insight here is distinguishing between:
1. Issues with your own code/services (where retrying makes sense)
2. Platform/service dependency issues (where waiting and monitoring is better)
3. Configuration problems (where investigation and fixes are needed)

Having clear runbooks and monitoring in place helps teams respond appropriately to each type of situation. During widespread platform incidents, communication and patience often beat frantic retrying.