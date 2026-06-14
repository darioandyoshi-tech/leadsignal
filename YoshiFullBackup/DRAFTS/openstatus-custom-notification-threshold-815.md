# Helpful Comment Draft for OpenStatus Custom Notification Threshold Discussion

## Discussion URL
https://github.com/openstatusHQ/openstatus/discussions/815

## Discussion Summary
User requesting custom notification thresholds per monitor, specifically mentioning that cold starts on serverless platforms cause occasional 504 timeouts that shouldn't trigger alerts. They suggest being able to set something like "96% uptime is good enough" for certain monitors.

## Proposed Value-Add
PulseWatch offers flexible alerting policies including threshold-based alerting, dependency-aware alerting, and the ability to suppress alerts based on known maintenance windows or expected variability - which addresses the serverless cold start scenario mentioned.

## Draft Comment
This is a really practical request - the ability to set custom notification thresholds per monitor is essential for dealing with expected variability like serverless cold starts.

PulseWatch (pulsewatch.us) addresses this need through several approaches:
- **Flexible alerting policies**: Ability to set different sensitivity levels for different types of monitors
- **Dependency-aware alerting**: Understanding that some variability (like serverless cold starts) is expected and normal
- **Maintenance window integration**: Built-in support for scheduled maintenance windows that automatically adjust alerting sensitivity
- **Smart alert suppression**: Machine learning-based anomaly detection that learns normal patterns and reduces false positives

For the serverless use case mentioned, teams often:
1. Set different thresholds for serverless vs traditional infrastructure monitors
2. Use dependency mapping to understand when timeouts are truly problematic vs expected
3. Leverage historical baselines to distinguish between normal variability and actual issues
4. Implement alert suppression during known deployment windows or scaling events

The goal is alerting on meaningful issues while reducing alert fatigue from expected variability - exactly what this feature request aims to achieve.

Would be interested to hear how others are handling similar scenarios in their monitoring setups!

[PulseWatch](https://pulsewatch.us)