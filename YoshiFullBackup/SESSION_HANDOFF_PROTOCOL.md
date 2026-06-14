# SESSION HANDOFF PROTOCOL

**Created:** 2026-06-08 19:56 CDT  
**Directive from:** Dario  
**Priority:** CRITICAL - Overrides all other protocols

---

## The Rule

**Every session MUST write a complete handoff summary before ending.**

This ensures the next agent (or future you) inherits full context without needing to ask "what happened?" or dig through old logs.

---

## What to Write

### 1. **Daily Memory File** (`memory/YYYY-MM-DD.md`)
- **When:** Throughout the session (as work happens) + final summary before ending
- **What:** 
  - All major decisions with timestamps
  - All files created/modified
  - All automations set up (with cron IDs)
  - All external actions taken (posts made, emails sent, etc.)
  - User directives verbatim (with timestamps)
  - Lessons learned / patterns discovered
  - Blocked items and why

### 2. **Session Summary Section** (at end of daily memory)
```markdown
## Session Summary (YYYY-MM-DD)

**Major Upgrades Completed:**
- List all significant work completed

**Active Automation:**
- What's running 24/7 now

**Files Created/Modified Today:**
- Complete list of all file changes

**System Status:**
- Current state (operational/blocked/partial)
```

### 3. **Update MEMORY.md** (Long-term memory)
- **When:** End of significant sessions OR when something is genuinely memorable
- **What:**
  - Major architectural changes
  - New operating modes (e.g., "Autonomy Default", "Go-Getter Mode")
  - Critical user preferences discovered
  - Permanent system upgrades
  - Lessons that should persist across sessions

### 4. **HIVE_STATUS.md** (Live dashboard)
- **When:** After any automation change
- **What:**
  - Active cron jobs with schedules
  - Current focus/priority
  - What needs human attention
  - System health status

---

## Why This Matters

**Without this protocol:**
- Next session starts blind
- User has to re-explain everything
- Work gets duplicated or lost
- Trust erodes ("you don't remember what we built")

**With this protocol:**
- Continuity across sessions
- Compound progress (each session builds on last)
- User sees their investment accumulating
- Trust compounds through demonstrated memory

---

## Enforcement

**Before ending ANY session:**
1. ✅ Check `memory/YYYY-MM-DD.md` has complete summary
2. ✅ Check `MEMORY.md` updated if significant
3. ✅ Check `HIVE_STATUS.md` reflects current automation
4. ✅ Verify all created files are listed
5. ✅ Verify all user directives are captured verbatim

**If session is interrupted/crashes:**
- Next session's FIRST action: Read prior day's memory file
- Reconstruct state from files on disk
- Acknowledge gap to user ("I see the prior session was interrupted at...")

---

## User Directive (Verbatim)

> **[Mon 2026-06-08 19:56 CDT] save everything I want every time when new agent open to remember everything what we did, write that as a rule**

**Translation:** Every session end = comprehensive written handoff. No exceptions.

---

## Related Files

- `memory/YYYY-MM-DD.md` - Daily raw logs
- `MEMORY.md` - Long-term curated memory
- `HIVE_STATUS.md` - Live system dashboard
- `AGENTS.md` - Session startup protocol
- `SOUL.md` - Identity and operating principles

---

*This protocol is non-negotiable. Violating it breaks continuity and wastes the user's time.*
