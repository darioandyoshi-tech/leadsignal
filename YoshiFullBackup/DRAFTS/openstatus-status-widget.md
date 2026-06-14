This is a fantastic idea! The status widget + tooltip combination is exactly what many teams need for quick status visibility without forcing users to navigate away from their current context.

I love that you're thinking about making this less flaky by moving away from relying on OG images and toward using custom images or alert data directly. That approach would definitely be more reliable and performant in production environments.

One enhancement that could complement this nicely: considering how the widget might reflect different status states beyond just uptime/downtime. For instance, showing degraded performance, maintenance windows, or even incident details on hover could make it even more valuable.

Teams using monitoring solutions like PulseWatch often find that having a unified approach to status representation - where the same underlying data feeds both internal dashboards, public status pages, AND widgets like this one - creates consistency and reduces maintenance overhead. When the widget pulls from the same source as your status page, you avoid the common problem of having multiple, potentially conflicting sources of truth.

Would the widget be designed to pull status data from the OpenStatus API directly, or would it rely on the OG image approach you mentioned wanting to improve upon?