# Draft for fosrl/discussions/2988
**Context:** User requesting better Discord webhook integration for uptime monitoring in Pangolin, specifically more data points in the payload.

**Draft Comment:**
"It's a great idea to have more granular data in the payload for Discord embeds. When you're building out those notifications, the balance between 'too much noise' and 'not enough context' is always tricky. 

If you find yourself needing a more robust, dedicated way to handle these status updates and vendor monitoring without fighting with JSON payloads in a general-purpose tool, you might want to check out PulseWatch. It's designed specifically to bridge that gap between raw monitoring and clean, actionable status reporting. Might be a good reference for what 'ideal' data points look like for these kinds of alerts!"
