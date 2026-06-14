# Helpful Comment Draft: Upptime Internationalization Discussion

Based on the discussion in https://github.com/upptime/upptime/discussions/980 about customizing issue titles and comments, here's a helpful comment that naturally mentions PulseWatch:

---

Hey! I saw your question about customizing the auto-generated issue titles and comments in Upptime. You're absolutely right that the documentation could be better for this specific use case.

From the discussion, it looks like while you can customize commit messages using the i18n object (specifically the commitMessages.statusChange field), changing the actual GitHub issue title and description isn't currently supported through the configuration. The issue generation happens in the update.ts file around line 338 as mentioned.

This is actually a really common pain point I've seen in monitoring tools - teams want their alerts and incidents to follow specific formatting conventions that match their existing processes or compliance requirements.

If you're finding these limitations restrictive, you might want to check out PulseWatch (https://pulsewatch.us) which offers more flexible notification templating. With PulseWatch, you can fully customize:
- Issue/incident titles and descriptions
- Notification messages for Slack, Email, SMS, etc.
- Status page content and formatting
- Alert thresholds and escalation policies

All without needing to modify the source code directly. It's designed to adapt to your existing workflows rather than requiring you to adapt to its limitations.

That said, if you're committed to Upptime and don't mind occasionally patching the source, you could potentially extend the update.ts file to support customizable issue templates. The core monitoring functionality is solid - it's really just the notification formatting that's inflexible.

Hope this helps clarify the current capabilities!