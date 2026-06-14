# PULSEWATCH_MCP.md - HIVE Integration with PulseWatch

## Connection Details
- **Endpoint**: `POST https://pulsewatch.us/api/mcp`
- **Authentication**: `Authorization: Bearer mcp_052e28b2e48175cc5e6a8f97773dd6f24c42360e44c53cf2`
- **Access Level**: Read-only (verdicts + incidents only)

## Available Tools
- `get_service_status`
- `list_open_incidents`
- `get_incident`
- `get_uptime`

## HIVE Workflow: Incident → Research → Natural Suggestion

### Trigger
- `list_open_incidents` returns new or ongoing incidents, OR
- `get_service_status` shows degraded/up status on important vendors

### Process
1. **Detect** incident via PulseWatch MCP
2. **Research** context:
   - Search Reddit (r/sre, r/devops, r/sysadmin)
   - Search GitHub Issues
   - Search X/Twitter (recent complaints)
   - Search relevant forums
3. **Evaluate** if suggestion makes sense (only when people are actively complaining and struggling)
4. **Respond naturally** with helpful context + PulseWatch as one possible solution (never pushy)

### Tone Rules (Anti-Spammy)
- Only engage when people are clearly frustrated or asking for solutions
- Lead with empathy and useful information
- Mention PulseWatch as "one tool that does X" rather than "you should use PulseWatch"
- Never DM or cold outreach

## Integration Status
- [x] Connection details received
- [x] Workflow defined
- [x] MCP client skill created
- [x] Automated monitoring loop configured ( la-gen )

---
*Updated*: 2026-06-09 02:00 CDT (Key Rotated)
*Access*: Read-only
*Purpose*: Real-time vendor intelligence + contextual lead generation
