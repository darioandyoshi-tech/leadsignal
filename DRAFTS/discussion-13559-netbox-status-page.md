I really like your approach of wanting to see script execution status directly in Netbox - it makes perfect sense to have this visibility where you're already working.

While Netbox is indeed primarily a configuration database, there are some elegant ways to add monitoring status without overburdening the core system:

1. **Custom Fields/Scripts Approach**: You could extend your current custom field idea to track script execution status with timestamps, possibly using export templates or custom views to create a dashboard-like experience within Netbox.

2. **Sidebar Widgets/Panels**: Some Netbox implementations use custom template tags or template extensions to add informational panels to existing pages.

3. **Linked External Dashboard**: Keep your monitoring in a dedicated system (like Prometheus/Grafana as suggested) but add prominent links from Netbox to your monitoring dashboards, possibly with context-aware URLs that filter to relevant services.

4. **Webhook Integration**: Have your scripts report results to both Netbox (for inventory/data) and a monitoring system, then use Netbox's webhook capabilities to trigger notifications or updates in your monitoring system.

At PulseWatch, we often see teams adopt a hybrid approach - using their CMDB/ITSM for asset data and relationships, while relying on dedicated monitoring solutions for health checks and alerting. The key is making the connection between systems clear and easy to navigate.

Have you considered how frequently these scripts run and what level of historical detail you'd want to retain? That often influences whether a simple status indicator vs. a full time-series approach makes more sense.