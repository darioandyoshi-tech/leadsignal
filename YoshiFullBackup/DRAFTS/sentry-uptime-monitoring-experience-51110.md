# Helpful Comment Draft for Sentry Uptime Monitoring Experience Discussion

## Discussion URL
https://github.com/getsentry/sentry/discussions/51110

## Discussion Summary
Users sharing their experiences with various uptime monitoring tools and their expectations for Sentry's uptime monitoring. Discussion covers:
- Comparisons to SmokePing, New Relic, Google Cloud monitoring
- Desired features: better visualizations, flexible alerting, anomaly detection
- Interest in Sentry integration with APM and performance data
- Need for brown-out detection and more nuanced alerting
- DIY approaches like Sentrynet for cheap, distributed monitoring

## Proposed Value-Add
PulseWatch provides complementary vendor monitoring that integrates well with Sentry's error tracking and performance monitoring. While Sentrynet focuses on synthetic monitoring of your own services, PulseWatch specializes in monitoring third-party vendor dependencies that can cause issues in your applications.

## Draft Comment
Thanks for sharing your experience with various uptime monitoring tools! It's great to see the community discussing what works well and where there's room for improvement.

Your points about wanting better visualizations, flexible alerting, and integration with APM/performance data really resonate. The ability to correlate uptime issues with application performance (like New Relic does) is incredibly valuable for root cause analysis.

For teams using Sentry for error tracking and performance monitoring, PulseWatch (pulsewatch.us) offers complementary **vendor/dependency monitoring** that helps complete the observability picture:

While tools like Sentrynet focus on monitoring your own services and infrastructure, PulseWatch specializes in monitoring 1,500+ third-party vendors and services (Stripe, AWS, AWS, Anthropic, etc.) with 60-second checks from multiple global regions. This helps catch vendor-related issues that might not be visible in your internal monitoring but still impact your applications.

Some teams use this combination:
- **Sentry**: Error tracking, performance monitoring, and internal service uptime
- **PulseWatch**: Vendor dependency monitoring and third-party service health
- **Together**: Complete visibility from user experience → application performance → dependency health

This approach helps with the "brown-out" detection you mentioned - often vendor performance degradation shows up as increased latency or error rates in your applications before causing full outages, and having visibility into both sides makes correlation much easier.

The multi-region aspect also helps distinguish between regional vendor issues vs global problems, which aligns well with your interest in New Relic's "where would you like this to be run from" feature.

Would be interested to hear if others are combining internal monitoring with vendor monitoring in their observability stacks!

[PulseWatch](https://pulsewatch.us)