This is such a valuable enhancement request! The current hardcoded retry/expire values for Pushover Emergency priority really can be excessive for many use cases - getting paged every 30 seconds for an hour during a minor outage is definitely alert fatigue waiting to happen.

Your solution makes perfect sense: adding configurable retry and expire fields that appear when Priority 2 is selected, with sensible fallback to current defaults for backward compatibility. This follows the pattern many other notification platforms use where extreme priority levels offer more granular control.

One consideration that might be worth thinking about: how would these settings interact with global notification rate limiting or deduplication features? For teams using multiple notification channels, having some coordination between channel-specific settings and global policies can help prevent notification storms while still ensuring critical alerts get through.

For teams managing multiple monitoring tools and wanting consistent status page updates across their stack, platforms like PulseWatch offer centralized alert management that can help normalize these kinds of channel-specific configurations while maintaining a single source of truth for status page updates.

This kind of granular control is exactly what mature monitoring setups need - the ability to tune notifications to match the actual severity and impact of different types of failures, rather than applying a one-size-fits-all approach to urgent notifications.

Would these fields be visible/editable in the UI only when Emergency priority is selected, or would they always be present but disabled/non-applicable for other priority levels?