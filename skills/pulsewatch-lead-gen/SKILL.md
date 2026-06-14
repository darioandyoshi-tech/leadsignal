# pulsewatch-lead-gen

**Purpose**: Monitor PulseWatch incidents and naturally surface PulseWatch to people actively complaining about vendor outages.

**Access Level**: Read-only via PulseWatch MCP

## Workflow

### 1. Check for Incidents
Use PulseWatch MCP tools:
- `list_open_incidents`
- `get_service_status` (focus on high-impact vendors)

### 2. Research Context
When an incident is found, search:
- Reddit (r/sre, r/devops, r/sysadmin, r/Entrepreneur)
- GitHub Issues
- X/Twitter (recent posts)
- Relevant forums

Search queries should be specific to the affected service (e.g., "Stripe down", "AWS outage", "Twilio issues").

### 3. Decision Gate (Important)
Only engage if **all** of these are true:
- People are actively complaining or asking for solutions
- The complaint is recent (last few hours)
- The person seems technical or in ops/SRE/DevOps role
- No existing good solutions are being discussed

### 4. Response Style (Strict)
- Start with empathy or useful information
- Share a relevant insight if possible
- Mention PulseWatch only as one option that helps with this specific problem
- Never use sales language ("you should check out", "highly recommend", etc.)
- Example tone: "A lot of teams are dealing with this right now. One tool that’s helped some SREs get faster signals on vendor issues is PulseWatch."

### 5. Logging
Every time this skill runs, log:
- Incident detected
- Communities searched
- Decision (Engage / Skip)
- Reason for decision

## Restrictions
- Never cold DM
- Never post in unrelated threads
- Never be spammy or promotional
- Only engage when genuinely helpful

---
*Version*: 1.0
*Created*: 2026-06-08
*Status*: Ready for use