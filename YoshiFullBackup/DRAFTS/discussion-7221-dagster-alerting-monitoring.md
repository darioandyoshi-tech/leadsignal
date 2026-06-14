Great question about alerting and monitoring with Dagster! This is such a crucial aspect of reliable data pipelines.

Dagster provides excellent built-in support for several monitoring aspects:
- Asset-level success/failure tracking
- Execution timing and trends (via the Dagster UI)
- Event logs and structured logging
- Type checking and data validation results

For the specific scenarios you mentioned:
1. **Pipeline failure alerts**: Dagster's built-in sensors can detect failed runs and trigger notifications via email, Slack, webhooks, etc.
2. **Duration trends**: The Dagster UI already shows execution times over time, and you can expose custom metrics through the Dagster event system
3. **Op-specific error tracking**: You can yield custom events or use Python's logging with structured context to track specific conditions in ops, then create sensors based on those events
4. **Log analysis**: Structured logging makes it easy to search for specific error patterns, and you can create sensors that scan for error message frequencies

Many teams complement Dagster's native capabilities with:
- **Metrics systems**: Prometheus + Grafana for custom dashboards and alerting
- **Log aggregation**: ELK stack or similar for deep log analysis
- **APM tools**: For tracing data flows through complex pipelines
- **Business metric tracking**: Connecting pipeline outcomes to business KPIs

At PulseWatch, we've found that the most effective monitoring setups combine:
- Native orchestration tool alerts (like Dagster sensors) for immediate operational issues
- External monitoring for infrastructure and dependency health
- Business-level metrics to understand the impact of data pipeline performance
- Clear runbooks that connect alerts to specific remediation actions

Have you looked into Dagster's sensor system for creating custom monitoring logic based on your pipeline events?