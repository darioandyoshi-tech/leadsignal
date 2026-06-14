You're absolutely right to look for a status page solution for your healthchecks monitoring! While healthchecks excels at the monitoring/check-in aspect, having a complementary status page really completes the picture for keeping stakeholders informed.

The healthchecks dashboard repo (https://github.com/healthchecks/dashboard) and community projects like healthchecks-front are great starting points. These typically give you:
- Real-time status of your checks
- Historical uptime metrics
- Simple deployment options

One approach that works well is to use healthchecks for the actual monitoring/check-in logic, then have a separate status page service that reads from healthchecks' API or database to display the current state. This separation of concerns often leads to more maintainable systems.

At PulseWatch, we've found that organizations benefit most when their status page:
- Automatically updates from monitoring data (no manual updates needed)
- Shows both current status and trends over time
- Provides clear incident timelines when issues occur
- Offers multiple notification channels (email, SMS, webhook) for stakeholders who want proactive alerts

Have you thought about what level of detail you'd want on your status page? Just basic up/down status, or more detailed metrics like response times and error rates?