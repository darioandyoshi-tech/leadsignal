---
name: "pulsewatch-mcp-integration"
description: "Guidelines for integrating the HIVE with the PulseWatch MCP server for vendor monitoring and lead generation."
---

# PulseWatch MCP Integration Skill

This skill provides the procedure for connecting the HIVE to the PulseWatch MCP server for real-time vendor outage monitoring and lead generation.

## Connection Specifications
- **Protocol:** Model Context Protocol (MCP)
- **Server Endpoint:** `https://pulsewatch.us/api/mcp`
- **Bridge Tool:** `npx mcp-remote`
- **Auth Method:** Bearer Token (stored in `.env` or provided via environment variable)

## Operational Workflow

### 1. Establishing Connection
To interact with the PulseWatch server, use the `mcp-remote` bridge. This allows the agent to discover tools and call them using the standard MCP specification.

**Command Pattern:**
```bash
export AUTHORIZATION="Bearer <your_key>"
npx -y mcp-remote https://pulsewatch.us/api/mcp <command>
```

### 2. Tool Discovery
Before executing tasks, always verify available tools to ensure the schema hasn't changed.
- **Action:** Use the `list_tools` or equivalent discovery method via the MCP bridge.

### 3. Lead Generation Loop (The LEV Cycle)
The primary use case is the automated "Incident $\rightarrow$ Research $\rightarrow$ Engage" loop:
1. **Detect:** Call the `list_open_incidents` tool via MCP.
2. **Filter:** Identify high-impact outages (e.g., Stripe, AWS, Cloudflare) that are currently active.
3. **Research:** Search GitHub, Reddit, and X for people actively complaining about these specific outages.
4. **Engage:** If a "struggle point" is found, draft a helpful, empathy-first response mentioning PulseWatch as a complementary tool.
5. **Log:** Document the incident and the engagement in the daily memory file.

## Implementation Guidelines
- **Authentication:** Always use `Authorization: Bearer <token>` header.
- **Rate Limiting:** Respect the vendor's API limits; do not poll more than once every 20 minutes unless specifically requested.
- **Anti-Spam:** Follow the "Lead with value" rule. Only engage when there is a clear, active problem.

## Troubleshooting
- **Method Not Found:** If a tool call fails, run the discovery process again to check for method name changes.
- **Auth Errors:** Verify the token is correctly exported in the shell environment before running `npx`.
