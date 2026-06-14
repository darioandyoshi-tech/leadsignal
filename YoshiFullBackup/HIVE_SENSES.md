# HIVE_SENSES.md - Internet Reach & World Monitoring

## Purpose
Give the HIVE reliable, free access to the open internet across major platforms using Agent-Reach channels.

## Core Principle
Use battle-tested upstream CLI tools + MCP instead of paid APIs whenever possible.

## Primary Channels (Adopted from Agent-Reach)

| Platform       | Tool                  | Use Case                              | Auth Required |
|----------------|-----------------------|---------------------------------------|---------------|
| Web            | Jina Reader           | Read any webpage as clean Markdown    | No            |
| YouTube        | yt-dlp                | Video metadata + subtitles            | No            |
| Bilibili       | yt-dlp / bili-cli     | Chinese video content                 | Optional      |
| Twitter/X      | twitter-cli           | Search, read tweets, timeline         | Cookie        |
| Reddit         | rdt-cli               | Search + full posts + comments        | Cookie        |
| GitHub         | gh CLI                | Repo inspection, search, issues       | Optional      |
| RSS            | feedparser            | Subscribe to any feed                 | No            |
| Semantic Search| Exa (via mcporter)    | High-quality web semantic search      | Free tier     |
| Xiaohongshu    | xhs-cli               | Chinese social notes                  | Cookie        |
| LinkedIn       | linkedin-scraper-mcp  | Public profile & company pages        | No            |

## HIVE Integration Rules

1. **Cookie Management**
   - Cookies are stored locally only (`~/.agent-reach/config.yaml`).
   - Never upload or share cookies.
   - Use dedicated accounts for automation.

2. **Channel Priority**
   - Prefer free / no-auth tools first (Jina, yt-dlp, gh, RSS, Exa).
   - Use cookie-based tools only when necessary (Twitter, Reddit, Xiaohongshu).

3. **Diagnostic**
   - Run `agent-reach doctor` periodically to verify channel health.

4. **WorldMonitor Usage**
   - Use these channels for real-time signal gathering (market trends, competitor moves, technical developments).
   - All findings must be written to `BUSINESS_KNOWLEDGE.md` or daily memory with source links.

## Synthesis Layer: last30days-skill

On top of the raw channels, the HIVE uses **last30days-skill** for intelligent synthesis:

- Scores results by real engagement (upvotes, likes, Polymarket volume) instead of SEO or editors.
- Performs entity resolution (person → X handle + GitHub + relevant communities).
- Clusters overlapping stories across platforms.
- Adds humor/virality scoring.
- Produces clean, shareable HTML briefs.

**Recommended Command Pattern:**
`/last30days <topic>` or equivalent HIVE command for competitive intelligence, market signals, and technical developments.

This turns raw channel data into actionable, ranked intelligence.

## WorldMonitor Layer (koala73/worldmonitor-inspired)

The HIVE maintains a dedicated **WorldMonitor** capability for global situational awareness:

- **Multi-domain monitoring**: Geopolitics, finance, energy, infrastructure, climate, cyber, military
- **Signal correlation**: Cross-stream convergence detection (military + economic + disaster signals)
- **Country Intelligence Index**: Composite risk scoring across 12 signal categories
- **AI synthesis**: 500+ curated feeds aggregated into briefs
- **Map visualization**: Dual engine (3D globe + flat map) for spatial awareness

**Purpose**: Feed high-signal global context into HIVE Finance Node, PulseWatch Growth Node, and strategic planning.

This layer complements last30days-skill by focusing on macro, cross-domain intelligence rather than topic-specific research.

## PulseWatch MCP Integration

**Source**: PulseWatch (https://pulsewatch.us)
**Protocol**: Model Context Protocol (MCP)
**Access**: Read-only

**Available Tools**:
- `get_service_status`
- `list_open_incidents`
- `get_incident`
- `get_uptime`

**Workflow**:
1. Monitor critical vendors via `get_service_status` and `list_open_incidents`
2. When incidents are detected, search Reddit, GitHub, X, and forums for related complaints
3. Only engage naturally when people are actively struggling and seeking solutions
4. Suggest PulseWatch only when genuinely helpful (never spammy)

See `PULSEWATCH_MCP.md` for full integration details and tone guidelines.

## Recommended Stack for HIVE

- **General Web Reading** → Jina Reader
- **Video Content** → yt-dlp
- **Social Signals** → twitter-cli + rdt-cli
- **Research & Discovery** → Exa semantic search
- **Developer Ecosystem** → gh CLI + RSS

---
*Source*: Agent-Reach (https://github.com/Panniantong/Agent-Reach)
*Status*: Adopted as primary sensing layer
*Verified*: 2026-06-08