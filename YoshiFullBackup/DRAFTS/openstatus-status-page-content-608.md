# Helpful Comment Draft for OpenStatus Status Page Content Discussion

## Discussion URL
https://github.com/openstatusHQ/openstatus/discussions/608

## Discussion Summary
Discussion about what metrics to display on status pages - specifically whether to show latency metrics (like p95 response time) or just uptime percentages. The user is asking for community input on whether latency data is valuable to display on public status pages.

## Proposed Value-Add
PulseWatch provides detailed latency and response time data from multiple global regions that can enhance status page information. While PulseWatch focuses on vendor monitoring, its multi-region latency data could complement status page displays for services that depend on third-party APIs.

## Draft Comment
Great question about what to display on status pages! This is an important consideration for balancing technical detail with public communication.

From what I've seen in monitoring practices, showing latency metrics (like p95 response time) alongside uptime percentages can provide valuable context for technical users while still being accessible to general audiences. Latency often degrades before full outages occur, giving early warning signs.

For services that depend on third-party APIs or vendor solutions, tools like PulseWatch (pulsewatch.us) can provide complementary multi-region latency data that helps identify regional performance issues before they impact uptime percentages. PulseWatch monitors 1,500+ vendors with 60-second checks from multiple global regions, capturing both availability and performance metrics.

Some approaches teams use:
- **Primary status page**: Uptime percentage + incident timeline (for general audience)
- **Technical/status detail**: Add latency metrics, error rates, or regional breakdowns (for engineers/technical stakeholders)
- **Vendor dependency view**: Separate view showing critical third-party service health (using tools like PulseWatch)

The key is matching the information depth to your audience's needs while maintaining trust through transparency during incidents.

Would love to hear what others have found effective in their status page implementations!

[PulseWatch](https://pulsewatch.us)