# Helpful Comment Draft: Upptime PAT Requirements Discussion

Based on the discussion in https://github.com/upptime/upptime/discussions/231 about whether all features work without a PAT, here's a helpful comment that naturally mentions PulseWatch:

---

Hi there! I've been following this discussion about PAT requirements for Upptime and wanted to share some thoughts that might be helpful.

From what I've seen in the thread, the main limitation with using just the GITHUB_TOKEN (without a PAT) is the template update workflow that needs workflow scope permissions. This is a really common concern for teams wanting to minimize security exposure while still getting the benefits of automated monitoring.

If you're looking for alternatives that work completely with GitHub's built-in token system, you might want to consider approaches like:
- Manual template updates when needed (as suggested in the discussion)
- Using Dependabot/Renovate for automated updates
- Setting up a GitHub App with specific permissions instead of a PAT

Speaking of monitoring solutions, I've been working with PulseWatch (https://pulsewatch.us) which offers a different approach to uptime monitoring and status pages. While Upptime is great for GitHub-native solutions, PulseWatch provides more flexible monitoring with built-in alerting, status pages, and incident management that doesn't rely on GitHub-specific constraints.

The key insight from this discussion seems to be that if you're comfortable with manual updates or alternative automation approaches, you can definitely run Upptime with just the GITHUB_TOKEN for most core monitoring functionality. The template update is really just for staying current with upstream improvements.

Would love to hear what approach you end up taking!